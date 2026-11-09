"""Decisões puras de animação; nenhum acesso ao Jira ou ao cronômetro."""
from dataclasses import dataclass
from datetime import datetime, date, timedelta


def easter_sunday(year):
    """Páscoa gregoriana pelo algoritmo Meeus/Jones/Butcher."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def effective_theme(value, now=None):
    if value in ("normal", "halloween", "natal", "ano_novo", "pascoa"):
        return value
    if value != "auto":
        return "normal"
    now = now or datetime.now()
    today = now.date() if isinstance(now, datetime) else now
    if (today.month == 10 and today.day >= 20) or (today.month == 11 and today.day <= 2):
        return "halloween"
    if today.month == 12 and today.day <= 26:
        return "natal"
    if (today.month == 12 and today.day >= 27) or (today.month == 1 and today.day <= 5):
        return "ano_novo"
    easter = easter_sunday(today.year)
    if easter - timedelta(days=7) <= today <= easter + timedelta(days=2):
        return "pascoa"
    return "normal"


def mascot_theme(preferences, now=None):
    """Preferência explícita tem prioridade; automático usa as datas sazonais."""
    value = preferences.get("theme", "auto")
    if value != "auto":
        return effective_theme(value, now)
    web = preferences.get("web_theme", "auto")
    return effective_theme(web, now)


@dataclass
class Reaction:
    action: str
    message: str
    until: float
    priority: int


class Behavior:
    """Estado contínuo e reações temporárias, com relógio monotônico injetado."""
    REACTIONS = {
        "hello": ("idle", "Olá! Vamos acompanhar o expediente.", 3, 10),
        "ticket": ("backpack", "Ticket alterado no JiraBot.", 3, 30),
        "worklog_start": ("backpack", "Enviando apontamentos...", 8, 40),
        "jira_activity": ("backpack", "Atualizando apontamentos...", 4, 40),
        "worklog_success": ("idle", "Apontamentos enviados com sucesso.", 5, 60),
        "worklog_error": ("sit", "Envio pendente. Confira o painel do JiraBot.", 8, 70),
        "exit_warning": ("drink", "Hora de revisar o expediente no painel.", 8, 50),
        "break_reminder": ("drink", "Hora de uma pausa.", 8, 50),
    }

    def __init__(self):
        self.status = "IDLE"
        self.day = None
        self.ticket = None
        self.reaction = None
        self.seen = set()
        self.dragging = False
        self.locked = False
        self.session_locked = False
        self.active_requests = {}

    def snapshot(self, state, now):
        day = state.get("date_str")
        if day != self.day:
            self.day = day
            self.reaction = None
            self.ticket = None
            self.seen.clear()
        status = state.get("status", "IDLE")
        self.status = status if status in {"RUNNING", "IDLE", "PAUSED_LUNCH", "PAUSED_AWAY", "COMPLETED"} else "IDLE"
        ticket = state.get("target_issue", "")
        if self.ticket is not None and ticket != self.ticket:
            self.trigger("ticket", now)
        self.ticket = ticket

    def trigger(self, name, now, event_id=None, activity_id=None):
        if name in ("Windows_Lock", "Windows_Unlock"):
            self.session_locked = name == "Windows_Lock"
            return True
        if name == "jira_request_start" and activity_id:
            self.active_requests[activity_id] = now
            self.trigger("jira_activity", now)
            return True
        if name == "jira_request_end" and activity_id:
            self.active_requests.pop(activity_id, None)
            return True
        if event_id is not None:
            if event_id in self.seen:
                return False
            self.seen.add(event_id)
            if len(self.seen) > 256:
                self.seen = {event_id}
        spec = self.REACTIONS.get(name)
        if not spec:
            return False
        action, message, duration, priority = spec
        if self.reaction and self.reaction.until > now and self.reaction.priority > priority:
            return False
        self.reaction = Reaction(action, message, now + duration, priority)
        return True

    def current(self, now):
        if self.locked or self.session_locked:
            return "sit", "Sessão bloqueada."
        if self.dragging:
            return "walk", "Solte para posicionar."
        self.active_requests = {key: start for key, start in self.active_requests.items() if now - start < 60}
        if self.active_requests:
            return "backpack", "Consultando apontamentos no Jira."
        if self.reaction and self.reaction.until > now:
            return self.reaction.action, self.reaction.message
        self.reaction = None
        return {
            "RUNNING": ("idle", "Acompanhando seu trabalho."),
            "PAUSED_LUNCH": ("drink", "Intervalo de almoço."),
            "PAUSED_AWAY": ("sit", "Cronômetro pausado."),
            "COMPLETED": ("sit", "Expediente concluído. Confira os envios no painel."),
        }.get(self.status, ("idle", "Aguardando o JiraBot."))
