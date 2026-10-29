"""
Motor de Negocio do JiraBot (Engine de Maquina de Estados e Calculo de Horas).
"""

from __future__ import annotations

from datetime import datetime, timedelta, time as dtime
import logging
from typing import Callable, Optional

from config import BotConfig, ShiftProfile
from notifier import send_notification
from review_dialog import get_fallback_description, show_pre_exit_popup
from storage import DailyState, StateManager, TimeInterval, clean_jira_issue_key

logger = logging.getLogger("JiraBot.Engine")


def format_duration(seconds: int) -> str:
    """Converte segundos em formato amigavel (ex: 5h 42m 15s)."""
    if seconds < 0:
        seconds = 0
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}h {m:02d}m {s:02d}s"
    elif m > 0:
        return f"{m}m {s:02d}s"
    else:
        return f"{s}s"


class BotEngine:
    """Motor central que governa as transicoes de estado do cronometro e acoes com o Jira."""

    def __init__(
        self,
        config: Optional[BotConfig] = None,
        state_manager: Optional[StateManager] = None,
        on_worklog_trigger: Optional[Callable[[str, int, str, str], bool]] = None,
    ):
        self.config = config or BotConfig.load()
        self.state_manager = state_manager or StateManager()
        self.on_worklog_trigger = on_worklog_trigger
        self.state: DailyState = self.state_manager.load_state()

    def refresh_state(self) -> DailyState:
        """Recarrega o estado mais recente do disco."""
        self.state = self.state_manager.load_state()
        return self.state

    def get_profile(self) -> ShiftProfile:
        """Retorna o perfil de turno ativo na configuracao."""
        return self.config.get_current_profile()

    def get_active_issue(self) -> str:
        """Retorna a tarefa ativa atual (seletor dinamico ou padrao)."""
        raw = self.state.target_issue or self.config.jira.default_issue
        return clean_jira_issue_key(raw) or "SEM_TICKET"

    def switch_ticket(
        self,
        new_issue_key: str,
        comment: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> DailyState:
        """
        Troca a tarefa ativa em tempo real. Se o cronometro estiver rodando,
        fecha o intervalo anterior sob a tarefa antiga e abre um novo sob a nova tarefa.
        Permite tambem definir a descricao do que sera feito.
        """
        now = now or datetime.now()
        now_iso = now.isoformat()
        self.refresh_state()

        old_issue = self.get_active_issue()
        new_issue = clean_jira_issue_key(new_issue_key) or old_issue

        if self.state.status == "RUNNING":
            if self.state.intervals and self.state.intervals[-1].end is None:
                self.state.intervals[-1].end = now_iso
                if not self.state.intervals[-1].issue_key:
                    self.state.intervals[-1].issue_key = old_issue

            # Inicia novo intervalo para o novo ticket
            self.state.intervals.append(TimeInterval(start=now_iso, issue_key=new_issue, comment=comment))

        self.state.target_issue = new_issue
        if comment:
            self.state.set_issue_comment(new_issue, comment)

        self.state.last_event = f"SWITCH_TICKET_{new_issue}"
        self.state.last_event_time = now_iso
        self.state_manager.save_state(self.state)

        desc_info = f" (Descricao: \"{comment}\")" if comment else ""
        msg = f"Ticket de trabalho alterado de {old_issue or 'Padrao'} para {new_issue}{desc_info}."
        logger.info(msg)
        send_notification("JiraBot - Troca de Tarefa", msg, self.config.notifications_enabled)
        return self.state

    def set_comment(self, comment: str, issue_key: Optional[str] = None) -> DailyState:
        """Define ou atualiza a descricao de atividade do ticket atual ou informado."""
        self.refresh_state()
        target = (issue_key or self.get_active_issue()).strip().upper()
        self.state.set_issue_comment(target, comment)
        self.state.last_event = f"SET_COMMENT_{target}"
        self.state.last_event_time = datetime.now().isoformat()
        self.state_manager.save_state(self.state)
        logger.info(f"Descricao do ticket {target} atualizada para: \"{comment}\"")
        return self.state

    def transfer_today_hours(
        self,
        source_issue: str,
        target_issue: str,
        seconds: Optional[int] = None,
    ) -> int:
        """
        Transfere horas acumuladas hoje de source_issue para target_issue.
        Retorna a quantidade de segundos efetivamente transferidos.
        """
        self.refresh_state()
        src = source_issue.strip().upper()
        tgt = target_issue.strip().upper()

        transferred = self.state.transfer_hours(source_issue=src, target_issue=tgt, seconds=seconds)
        if transferred > 0:
            now_iso = datetime.now().isoformat()
            self.state.last_event = f"TRANSFER_{src}_TO_{tgt}"
            self.state.last_event_time = now_iso
            self.state_manager.save_state(self.state)

            dur_str = format_duration(transferred)
            msg = f"Transferido {dur_str} de {src} para {tgt} com sucesso."
            logger.info(msg)
            send_notification("JiraBot - Transferencia de Horas", msg, self.config.notifications_enabled)

        return transferred

    def handle_unlock(self, now: Optional[datetime] = None) -> DailyState:
        """Processa o evento de desbloqueio de tela (WTS_SESSION_UNLOCK)."""
        now = now or datetime.now()
        now_iso = now.isoformat()
        profile = self.get_profile()
        active_issue = self.get_active_issue()

        self.refresh_state()
        logger.info(f"Processando UNLOCK as {now.strftime('%H:%M:%S')}. Estado atual: {self.state.status}")

        if self.state.status == "IDLE":
            # Inicia o dia de trabalho
            self.state.status = "RUNNING"
            self.state.intervals.append(TimeInterval(start=now_iso, issue_key=active_issue))
            self.state.last_event = "STARTED_ON_UNLOCK"
            self.state.last_event_time = now_iso
            self.state_manager.save_state(self.state)

            msg = f"Inicio de expediente registrado as {now.strftime('%H:%M')}. Perfil: {profile.name} (Ticket: {active_issue or 'Nenhum'})"
            logger.info(msg)
            send_notification("JiraBot - Cronometro Iniciado", msg, self.config.notifications_enabled)

        elif self.state.status == "PAUSED_LUNCH":
            current_time = now.time()
            lunch_pause_sec = 0
            if self.state.intervals and self.state.intervals[-1].end:
                try:
                    ls_end_dt = datetime.fromisoformat(self.state.intervals[-1].end)
                    lunch_pause_sec = max(0, int((now - ls_end_dt).total_seconds()))
                except Exception:
                    pass

            # Permite retomar se o horario atingiu a janela de retorno OU se ja decorreram ao menos 35 minutos de almoco
            can_resume = (current_time >= profile.lunch_end_window.start_time) or (lunch_pause_sec >= 2100)
            if not can_resume:
                logger.info(
                    f"Desbloqueio as {now.strftime('%H:%M')} antes da janela de retorno do almoco "
                    f"({profile.lunch_end_window.start_str}) e com apenas {lunch_pause_sec // 60}m de pausa. Cronometro mantido em pausa."
                )
                return self.state

            # Retorno valido do intervalo de almoco
            self.state.status = "RUNNING"
            self.state.intervals.append(TimeInterval(start=now_iso, issue_key=active_issue))
            self.state.last_event = "RESUMED_LUNCH_UNLOCK"
            self.state.last_event_time = now_iso
            self.state_manager.save_state(self.state)

            total_str = format_duration(self.state.get_total_seconds())
            msg = f"Retorno do almoco as {now.strftime('%H:%M')}. Tempo acumulado: {total_str}"
            logger.info(msg)
            send_notification("JiraBot - Retorno do Almoco", msg, self.config.notifications_enabled)

        elif self.state.status == "PAUSED_AWAY":
            # Retorno de pausa curta
            self.state.status = "RUNNING"
            self.state.intervals.append(TimeInterval(start=now_iso, issue_key=active_issue))
            self.state.last_event = "RESUMED_AWAY_UNLOCK"
            self.state.last_event_time = now_iso
            self.state_manager.save_state(self.state)

            logger.info(f"Sessao retomada apos bloqueio intermediario as {now.strftime('%H:%M')}.")

        elif self.state.status == "COMPLETED":
            # Caso o usuario desbloqueie apos ter completado o dia (ex: hora extra), retoma como RUNNING
            self.state.status = "RUNNING"
            self.state.intervals.append(TimeInterval(start=now_iso, issue_key=active_issue))
            self.state.last_event = "RESUMED_AFTER_COMPLETION"
            self.state.last_event_time = now_iso
            self.state.is_logged = False
            self.state_manager.save_state(self.state)
            logger.info(f"Desbloqueio detectado apos dia completado as {now.strftime('%H:%M')}. Retomando contagem de horas extras.")

        return self.state

    def handle_lock(self, now: Optional[datetime] = None) -> DailyState:
        """Processa o evento de bloqueio de tela (WTS_SESSION_LOCK)."""
        now = now or datetime.now()
        current_time = now.time()
        now_iso = now.isoformat()
        profile = self.get_profile()

        self.refresh_state()
        logger.info(f"Processando LOCK as {now.strftime('%H:%M:%S')}. Estado atual: {self.state.status}")

        if self.state.status == "RUNNING":
            # Fecha o intervalo de trabalho corrente
            if self.state.intervals and self.state.intervals[-1].end is None:
                self.state.intervals[-1].end = now_iso
                if not self.state.intervals[-1].issue_key:
                    self.state.intervals[-1].issue_key = self.get_active_issue()

            total_seconds = self.state.get_total_seconds()
            target_seconds = profile.target_hours * 3600

            # Avalia em qual janela de horario o bloqueio ocorreu
            if profile.lunch_start_window.contains(current_time):
                # Pausa para almoco
                self.state.status = "PAUSED_LUNCH"
                self.state.last_event = "PAUSED_LUNCH_LOCK"
                self.state.last_event_time = now_iso
                self.state_manager.save_state(self.state)

                total_str = format_duration(total_seconds)
                msg = f"Intervalo de almoco iniciado as {now.strftime('%H:%M')}. Tempo liquido: {total_str}"
                logger.info(msg)
                send_notification("JiraBot - Pausa para Almoco", msg, self.config.notifications_enabled)

            elif profile.exit_window.contains(current_time) or (current_time >= profile.exit_window.start_time and total_seconds >= int(target_seconds * 0.85)):
                # Fim de expediente (dentro da janela de saida ou apos o horario de saida com carga cumprida)
                self.state.status = "COMPLETED"
                self.state.last_event = "COMPLETED_EXIT_LOCK"
                self.state.last_event_time = now_iso
                self.state_manager.save_state(self.state)

                total_str = format_duration(total_seconds)
                msg = f"Fim de expediente detectado as {now.strftime('%H:%M')}. Total trabalhado hoje: {total_str}"
                logger.info(msg)
                send_notification("JiraBot - Expediente Finalizado", msg, self.config.notifications_enabled)

                if self.config.auto_log_on_exit and not self.state.is_logged:
                    self._trigger_worklog_all_issues()

            else:
                # Bloqueio intermediario fora das janelas planejadas (ex: banheiro, cafe)
                if self.config.intermediate_lock_mode == "pause":
                    self.state.status = "PAUSED_AWAY"
                    self.state.last_event = "PAUSED_AWAY_LOCK"
                    self.state.last_event_time = now_iso
                    self.state_manager.save_state(self.state)
                    logger.info(f"Pausa temporaria registrada as {now.strftime('%H:%M')}.")
                else:
                    # Modo ignore: mantem a contagem continua sem fechar o intervalo
                    if self.state.intervals and self.state.intervals[-1].end == now_iso:
                        self.state.intervals[-1].end = None
                    self.state_manager.save_state(self.state)
                    logger.info("Bloqueio intermediario ignorado conforme configuracao.")

        return self.state

    def handle_shutdown(self, now: Optional[datetime] = None) -> DailyState:
        """
        Processa o evento de desligamento, reinicializacao ou logoff do Windows
        (WM_QUERYENDSESSION, WM_ENDSESSION ou WTS_SESSION_LOGOFF).
        Garante que o intervalo em aberto seja fechado imediatamente em disco e,
        caso o expediente tenha sido concluido, envia (ou enfileira com seguranca)
        o worklog no Jira antes do encerramento do sistema.
        """
        now = now or datetime.now()
        current_time = now.time()
        now_iso = now.isoformat()
        profile = self.get_profile()

        self.refresh_state()
        logger.info(f"Processando SHUTDOWN/LOGOFF as {now.strftime('%H:%M:%S')}. Estado atual: {self.state.status}")

        was_running = (self.state.status == "RUNNING")
        if was_running:
            if self.state.intervals and self.state.intervals[-1].end is None:
                self.state.intervals[-1].end = now_iso
                if not self.state.intervals[-1].issue_key:
                    self.state.intervals[-1].issue_key = self.get_active_issue()

        total_seconds = self.state.get_total_seconds()
        target_seconds = int(profile.target_hours * 3600)

        is_exit_condition = (
            profile.exit_window.contains(current_time)
            or (current_time >= profile.exit_window.start_time and total_seconds >= int(target_seconds * 0.85))
            or (total_seconds >= target_seconds and target_seconds > 0)
        )

        if self.state.status in ("RUNNING", "PAUSED_AWAY", "PAUSED_LUNCH") and is_exit_condition and total_seconds > 0:
            self.state.status = "COMPLETED"
            self.state.last_event = "COMPLETED_EXIT_SHUTDOWN"
            self.state.last_event_time = now_iso
            # Persiste imediatamente em disco antes de qualquer chamada de rede
            self.state_manager.save_state(self.state)

            total_str = format_duration(total_seconds)
            logger.info(f"Fim de expediente por desligamento do PC as {now.strftime('%H:%M')}. Total: {total_str}")

            if self.config.auto_log_on_exit and not self.state.is_logged:
                self._trigger_worklog_all_issues()

        elif was_running:
            if profile.lunch_start_window.contains(current_time):
                self.state.status = "PAUSED_LUNCH"
                self.state.last_event = "PAUSED_LUNCH_SHUTDOWN"
                self.state.last_event_time = now_iso
                self.state_manager.save_state(self.state)
                logger.info(f"Pausa de almoco registrada por desligamento do PC as {now.strftime('%H:%M')}.")
            else:
                self.state.status = "PAUSED_AWAY"
                self.state.last_event = "PAUSED_SHUTDOWN"
                self.state.last_event_time = now_iso
                self.state_manager.save_state(self.state)
                logger.info(f"Cronometro pausado e salvo por desligamento/reinicializacao as {now.strftime('%H:%M')}.")

        return self.state

    def check_scheduled_transitions(self, now: Optional[datetime] = None) -> DailyState:
        """
        Verificacao periodica executada pelo daemon:
        1. Alerta de revisao de descricao configuravel antes do horario nominal de saida.
        """
        now = now or datetime.now()
        self.refresh_state()

        if not getattr(self.config, "exit_warning_enabled", True):
            return self.state

        profile = self.get_profile()

        # Janela de alerta baseada no horario planejado real de saida e minutos configurados
        try:
            today = now.date()
            planned_exit = profile.get_planned_exit_time()
            exit_dt = datetime(today.year, today.month, today.day, planned_exit.hour, planned_exit.minute, 0)
            warn_minutes = max(1, min(60, int(getattr(self.config, "exit_warning_minutes", 5))))
            pre_exit_dt = exit_dt - timedelta(minutes=warn_minutes)

            if self.state.status == "RUNNING" and not self.state.prompted_exit_review:
                if pre_exit_dt <= now <= (exit_dt + timedelta(minutes=15)):
                    self.state.prompted_exit_review = True
                    self.state_manager.save_state(self.state)
                    logger.info(
                        f"Disparando alerta de revisao de descricao {warn_minutes} minutos antes "
                        f"do encerramento planejado ({planned_exit.strftime('%H:%M')})."
                    )
                    show_pre_exit_popup(self.state_manager)
        except Exception as e:
            logger.error(f"Erro ao avaliar alerta pre-saida: {e}")

        return self.state

    def _trigger_worklog_all_issues(self) -> None:
        """Aciona o lancamento do worklog para cada ticket trabalhado no dia com sua descricao especifica."""
        default_issue = self.config.jira.default_issue
        by_issue = self.state.get_seconds_by_issue(default_issue=default_issue)
        first_start = self.state.get_first_start_time()
        started_iso = first_start.isoformat() if first_start else datetime.now().isoformat()

        all_success = True
        for issue_key, seconds in by_issue.items():
            if seconds <= 0:
                continue

            if not issue_key or issue_key == "SEM_TICKET":
                issue_key = default_issue

            if not issue_key:
                logger.warning(f"Horas contabilizadas ({seconds}s) sem nenhum ticket associado ou padrao.")
                all_success = False
                continue

            # Obtem a descricao personalizada daquele ticket ou fallback (a menos que no_comment esteja ativo)
            if self.state.no_comment:
                custom_comment = "__EMPTY__"
            else:
                custom_comment = self.state.get_issue_comment(issue_key)
                if not custom_comment:
                    custom_comment = get_fallback_description(issue_key)

            success = False
            if self.on_worklog_trigger:
                try:
                    success = self.on_worklog_trigger(issue_key, seconds, started_iso, custom_comment)
                except Exception as e:
                    logger.error(f"Erro ao executar callback de worklog para {issue_key}: {e}")
                    success = False

            if not success:
                all_success = False
                self.state_manager.enqueue_worklog(
                    issue_key=issue_key,
                    started_iso=started_iso,
                    time_spent_seconds=seconds,
                    comment="" if self.state.no_comment else custom_comment,
                )

        if all_success:
            self.state.is_logged = True
            self.state_manager.save_state(self.state)
            self.state_manager.save_day_to_history(self.state)
            shift_summary = self.state.get_shift_times_summary()
            if shift_summary.get("start_hm"):
                self.state_manager.save_day_shift_schedule(self.state.date_str, shift_summary)
                for wid in self.state.jira_worklog_ids:
                    self.state_manager.save_worklog_schedule(wid, shift_summary)
            logger.info("Todos os apontamentos de hoje foram transmitidos ao Jira com sucesso.")

    def manual_start(self, now: Optional[datetime] = None) -> DailyState:
        """Inicia manualmente a contagem."""
        now = now or datetime.now()
        now_iso = now.isoformat()
        self.refresh_state()

        active_issue = self.get_active_issue()
        self.state.status = "RUNNING"
        self.state.intervals.append(TimeInterval(start=now_iso, issue_key=active_issue))
        self.state.last_event = "MANUAL_START"
        self.state.last_event_time = now_iso
        self.state_manager.save_state(self.state)
        return self.state

    def manual_pause(self, now: Optional[datetime] = None) -> DailyState:
        """Pausa manualmente o cronometro."""
        now = now or datetime.now()
        now_iso = now.isoformat()
        self.refresh_state()

        if self.state.status == "RUNNING":
            if self.state.intervals and self.state.intervals[-1].end is None:
                self.state.intervals[-1].end = now_iso
                if not self.state.intervals[-1].issue_key:
                    self.state.intervals[-1].issue_key = self.get_active_issue()

            self.state.status = "PAUSED_AWAY"
            self.state.last_event = "MANUAL_PAUSE"
            self.state.last_event_time = now_iso
            self.state_manager.save_state(self.state)
        return self.state

    def manual_log(
        self,
        issue_key: Optional[str] = None,
        comment: Optional[str] = None,
        no_comment: bool = False,
    ) -> int:
        """Forca o encerramento do dia e lancamento imediato de todas as horas no Jira."""
        now = datetime.now()
        now_iso = now.isoformat()
        self.refresh_state()

        if self.state.status == "RUNNING":
            if self.state.intervals and self.state.intervals[-1].end is None:
                self.state.intervals[-1].end = now_iso
                if not self.state.intervals[-1].issue_key:
                    self.state.intervals[-1].issue_key = issue_key or self.get_active_issue()

        if no_comment or comment == "__EMPTY__":
            self.state.no_comment = True
        elif comment:
            self.state.no_comment = False
            target = (issue_key or self.get_active_issue()).strip().upper()
            self.state.set_issue_comment(target, comment)

        self.state.status = "COMPLETED"
        self.state.last_event = "MANUAL_LOG_TRIGGERED"
        self.state.last_event_time = now_iso
        self.state_manager.save_state(self.state)

        total_seconds = self.state.get_total_seconds()
        self._trigger_worklog_all_issues()
        return total_seconds
