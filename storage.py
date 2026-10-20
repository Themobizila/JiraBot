"""
Modulo de persistencia local de estado, fila de contingencia e historico para o JiraBot.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config import get_default_config_dir


@dataclass
class TimeInterval:
    """Intervalo continuo de trabalho associado a um ticket especifico."""
    start: str  # ISO 8601
    end: Optional[str] = None  # ISO 8601 ou None se estiver em andamento
    issue_key: Optional[str] = None  # Ticket associado a este intervalo
    comment: Optional[str] = None  # Descricao da atividade realizada

    def get_duration_seconds(self) -> int:
        start_dt = datetime.fromisoformat(self.start)
        if self.end:
            end_dt = datetime.fromisoformat(self.end)
        else:
            end_dt = datetime.now()
        return max(0, int((end_dt - start_dt).total_seconds()))

    def to_dict(self) -> Dict[str, Any]:
        return {"start": self.start, "end": self.end, "issue_key": self.issue_key, "comment": self.comment}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TimeInterval:
        return cls(start=data["start"], end=data.get("end"), issue_key=data.get("issue_key"), comment=data.get("comment"))


@dataclass
class DailyState:
    """Estado do cronometro do dia atual."""
    date_str: str = field(default_factory=lambda: date.today().isoformat())
    status: str = "IDLE"  # IDLE, RUNNING, PAUSED_LUNCH, PAUSED_AWAY, COMPLETED
    intervals: List[TimeInterval] = field(default_factory=list)
    target_issue: str = ""
    issue_comments: Dict[str, str] = field(default_factory=dict)
    prompted_exit_review: bool = False
    no_comment: bool = False
    is_logged: bool = False
    jira_worklog_ids: List[str] = field(default_factory=list)
    last_event: str = "INITIALIZED"
    last_event_time: str = field(default_factory=lambda: datetime.now().isoformat())

    def close_previous_day_intervals(self) -> None:
        """Fecha com seguranca qualquer intervalo em aberto que pertenca a um dia anterior."""
        if not self.intervals:
            return
        for inter in self.intervals:
            if inter.end is None:
                try:
                    start_dt = datetime.fromisoformat(inter.start)
                    # Se o ultimo evento registrado no dia anterior foi posterior ao inicio, usa esse evento
                    if self.last_event_time:
                        last_dt = datetime.fromisoformat(self.last_event_time)
                        if last_dt.date() == start_dt.date() and last_dt > start_dt:
                            inter.end = last_dt.isoformat()
                            continue
                    # Senao, fecha no final da tarde do proprio dia anterior (sem vazar para a madrugada/hoje)
                    inter.end = datetime(start_dt.year, start_dt.month, start_dt.day, 15, 30, 0).isoformat()
                except Exception:
                    inter.end = inter.start
        self.status = "COMPLETED"

    def get_total_seconds(self) -> int:
        """Calcula o total geral de segundos liquidos trabalhados no dia."""
        return sum(i.get_duration_seconds() for i in self.intervals)

    def get_seconds_by_issue(self, default_issue: str = "") -> Dict[str, int]:
        """Calcula o total de segundos acumulados agrupados por cada ticket trabalhado."""
        totals: Dict[str, int] = {}
        for interval in self.intervals:
            issue = interval.issue_key or self.target_issue or default_issue or "SEM_TICKET"
            totals[issue] = totals.get(issue, 0) + interval.get_duration_seconds()
        return totals

    def get_issue_comment(self, issue_key: str, default: str = "") -> str:
        """Retorna o comentario/descricao associado ao ticket."""
        return self.issue_comments.get(issue_key, "").strip() or default

    def set_issue_comment(self, issue_key: str, comment: str) -> None:
        """Define ou atualiza a descricao de um ticket trabalhado hoje."""
        clean_key = issue_key.strip().upper()
        if clean_key:
            self.issue_comments[clean_key] = comment.strip()
            # Atualiza tambem nos intervalos daquele ticket se aplicavel
            for inter in self.intervals:
                if inter.issue_key == clean_key and not inter.comment:
                    inter.comment = comment.strip()

    def transfer_hours(self, source_issue: str, target_issue: str, seconds: Optional[int] = None) -> int:
        """
        Transfere o tempo acumulado de um ticket para outro nos intervalos do dia atual.
        Se seconds for None ou >= ao total da origem, transfere todos os intervalos da origem.
        Se seconds for parcial, transfere intervalos inteiros ou fatia o intervalo correspondente.
        Retorna a quantidade de segundos transferidos.
        """
        src = source_issue.strip().upper()
        tgt = target_issue.strip().upper()
        if not src or not tgt or src == tgt:
            return 0

        # Identifica os intervalos associados ao ticket de origem
        matching_intervals: List[TimeInterval] = []
        for inter in self.intervals:
            assigned = (inter.issue_key or self.target_issue).strip().upper()
            if assigned == src:
                matching_intervals.append(inter)

        if not matching_intervals:
            return 0

        total_available = sum(i.get_duration_seconds() for i in matching_intervals)
        if total_available <= 0:
            return 0

        transfer_all = (seconds is None or seconds >= total_available)
        to_transfer = total_available if transfer_all else max(0, seconds)

        if transfer_all:
            for inter in matching_intervals:
                inter.issue_key = tgt
            transferred = total_available
        else:
            # Transferencia parcial: processa os intervalos e fatia quando necessario
            remaining = to_transfer
            transferred = 0
            for inter in list(matching_intervals):
                dur = inter.get_duration_seconds()
                if dur <= 0:
                    continue
                if dur <= remaining:
                    inter.issue_key = tgt
                    remaining -= dur
                    transferred += dur
                    if remaining <= 0:
                        break
                else:
                    # Fatia o intervalo:
                    # Parte 1 (inicio ate dur - remaining) permanece no ticket de origem
                    # Parte 2 ((dur - remaining) ate fim) vai para o ticket de destino
                    st_dt = datetime.fromisoformat(inter.start)
                    split_dt = st_dt + timedelta(seconds=(dur - remaining))
                    split_iso = split_dt.isoformat()
                    original_end = inter.end

                    inter.end = split_iso
                    inter.issue_key = src

                    idx = self.intervals.index(inter)
                    new_inter = TimeInterval(
                        start=split_iso,
                        end=original_end,
                        issue_key=tgt,
                        comment=inter.comment
                    )
                    self.intervals.insert(idx + 1, new_inter)
                    transferred += remaining
                    remaining = 0
                    break

        # Migra ou combina descricoes cadastradas
        src_comment = self.issue_comments.get(src)
        if src_comment and tgt not in self.issue_comments:
            self.issue_comments[tgt] = src_comment

        # Se o ticket ativo atual era o de origem e transferiu tudo, atualiza o ticket ativo
        if transfer_all and self.target_issue.strip().upper() == src:
            self.target_issue = tgt

        return transferred

    def get_all_issues_worked(self, default_issue: str = "") -> List[str]:
        """Retorna a lista ordenada e sem duplicatas de todos os tickets trabalhados no dia."""
        issues: List[str] = []
        for interval in self.intervals:
            key = (interval.issue_key or self.target_issue or default_issue).strip().upper()
            if key and key not in issues and key != "SEM_TICKET":
                issues.append(key)
        if self.target_issue and self.target_issue.strip().upper() not in issues:
            issues.append(self.target_issue.strip().upper())
        return issues

    def get_first_start_time(self) -> Optional[datetime]:
        """Retorna o datetime do primeiro inicio do dia."""
        if not self.intervals:
            return None
        return datetime.fromisoformat(self.intervals[0].start)

    def get_shift_times_summary(self) -> Dict[str, str]:
        """
        Extrai os horarios consolidados do expediente atual (inicio, pausa_almoco, retorno_almoco, encerramento)
        no formato HH:MM a partir dos intervalos registrados no dia.
        """
        start_hm = ""
        lunch_start_hm = ""
        lunch_end_hm = ""
        end_hm = ""

        if not self.intervals:
            return {
                "start_hm": start_hm,
                "lunch_start_hm": lunch_start_hm,
                "lunch_end_hm": lunch_end_hm,
                "end_hm": end_hm,
            }

        try:
            first_dt = datetime.fromisoformat(self.intervals[0].start)
            start_hm = first_dt.strftime("%H:%M")
        except Exception:
            pass

        if len(self.intervals) == 1:
            inter = self.intervals[0]
            if inter.end:
                try:
                    end_dt = datetime.fromisoformat(inter.end)
                    if self.status == "PAUSED_LUNCH":
                        lunch_start_hm = end_dt.strftime("%H:%M")
                    else:
                        end_hm = end_dt.strftime("%H:%M")
                except Exception:
                    pass
        else:
            # Procura a maior pausa ou a pausa proxima ao horario de almoco entre intervalos consecutivos
            best_gap_idx = 0
            best_gap_sec = -1
            for i in range(len(self.intervals) - 1):
                cur_end_str = self.intervals[i].end
                nxt_start_str = self.intervals[i + 1].start
                if cur_end_str and nxt_start_str:
                    try:
                        ce = datetime.fromisoformat(cur_end_str)
                        ns = datetime.fromisoformat(nxt_start_str)
                        gap = (ns - ce).total_seconds()
                        if gap > best_gap_sec:
                            best_gap_sec = gap
                            best_gap_idx = i
                    except Exception:
                        pass

            try:
                if self.intervals[best_gap_idx].end:
                    ls_dt = datetime.fromisoformat(self.intervals[best_gap_idx].end)
                    lunch_start_hm = ls_dt.strftime("%H:%M")
                le_dt = datetime.fromisoformat(self.intervals[best_gap_idx + 1].start)
                lunch_end_hm = le_dt.strftime("%H:%M")
            except Exception:
                pass

            last_inter = self.intervals[-1]
            if last_inter.end:
                try:
                    end_dt = datetime.fromisoformat(last_inter.end)
                    end_hm = end_dt.strftime("%H:%M")
                except Exception:
                    pass

        return {
            "start_hm": start_hm,
            "lunch_start_hm": lunch_start_hm,
            "lunch_end_hm": lunch_end_hm,
            "end_hm": end_hm,
        }

    def apply_shift_schedule(
        self,
        start_hm: str,
        lunch_start_hm: str = "",
        lunch_end_hm: str = "",
        end_hm: str = "",
        default_issue: str = "",
    ) -> Dict[str, Any]:
        """
        Aplica os horarios de inicio, pausa de almoco, retorno e encerramento ao estado do dia atual,
        recalculando os intervalos e preservando o ticket ativo.
        """
        active_key = (self.target_issue or default_issue or "ATIVDIV-32").strip().upper()
        active_comment = self.get_issue_comment(active_key)

        calc = calculate_shift_schedule(
            date_str=self.date_str,
            start_hm=start_hm,
            lunch_start_hm=lunch_start_hm,
            lunch_end_hm=lunch_end_hm,
            end_hm=end_hm,
            issue_key=active_key,
            comment=active_comment,
        )
        if not calc.get("success"):
            return calc

        self.intervals = calc["intervals"]
        self.status = calc["status"]
        if not self.target_issue and active_key:
            self.target_issue = active_key
        self.last_event = "WEB_SCHEDULE_UPDATED"
        self.last_event_time = datetime.now().isoformat()
        return calc

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date_str": self.date_str,
            "status": self.status,
            "intervals": [i.to_dict() for i in self.intervals],
            "target_issue": self.target_issue,
            "issue_comments": self.issue_comments,
            "prompted_exit_review": self.prompted_exit_review,
            "no_comment": self.no_comment,
            "is_logged": self.is_logged,
            "jira_worklog_ids": self.jira_worklog_ids,
            "last_event": self.last_event,
            "last_event_time": self.last_event_time,
            "total_seconds_calculated": self.get_total_seconds(),
            "seconds_by_issue": self.get_seconds_by_issue(),
            "shift_times": self.get_shift_times_summary(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DailyState:
        intervals_data = data.get("intervals", [])
        intervals = [TimeInterval.from_dict(i) for i in intervals_data]
        worklog_ids = data.get("jira_worklog_ids") or []
        if not worklog_ids and data.get("jira_worklog_id"):
            worklog_ids = [str(data["jira_worklog_id"])]

        return cls(
            date_str=data.get("date_str", date.today().isoformat()),
            status=data.get("status", "IDLE"),
            intervals=intervals,
            target_issue=data.get("target_issue", ""),
            issue_comments=data.get("issue_comments", {}),
            prompted_exit_review=data.get("prompted_exit_review", False),
            no_comment=data.get("no_comment", False),
            is_logged=data.get("is_logged", False),
            jira_worklog_ids=worklog_ids,
            last_event=data.get("last_event", "INITIALIZED"),
            last_event_time=data.get("last_event_time", datetime.now().isoformat()),
        )


def _parse_hm(date_str: str, hm_str: str) -> Optional[datetime]:
    """Converte uma data YYYY-MM-DD e um horario HH:MM em objeto datetime."""
    clean = (hm_str or "").strip()
    if not clean or ":" not in clean:
        return None
    try:
        y, m, d = map(int, date_str[:10].split("-"))
        parts = clean.split(":")
        hh = int(parts[0])
        mm = int(parts[1])
        ss = int(parts[2]) if len(parts) > 2 else 0
        return datetime(y, m, d, hh, mm, ss)
    except Exception:
        return None


def calculate_shift_schedule(
    date_str: str,
    start_hm: str,
    lunch_start_hm: str = "",
    lunch_end_hm: str = "",
    end_hm: str = "",
    issue_key: str = "",
    comment: str = "",
) -> Dict[str, Any]:
    """
    Calcula os intervalos e o tempo liquido total a partir dos horarios de:
    - Inicio (start_hm)
    - Pausa de Almoco (lunch_start_hm)
    - Retorno de Almoco (lunch_end_hm)
    - Encerramento (end_hm)
    Suporta tanto expedientes finalizados quanto em andamento (sem end_hm ou em pausa de almoco).
    """
    target_date = (date_str or date.today().isoformat())[:10]
    start_dt = _parse_hm(target_date, start_hm)
    if not start_dt:
        return {"success": False, "message": "Horário de início inválido. Use o formato HH:MM (ex: 07:45)."}

    lunch_s_dt = _parse_hm(target_date, lunch_start_hm)
    lunch_e_dt = _parse_hm(target_date, lunch_end_hm)
    end_dt = _parse_hm(target_date, end_hm)

    clean_issue = (issue_key or "").strip().upper() or None
    clean_comment = (comment or "").strip() or None

    intervals: List[TimeInterval] = []
    status = "RUNNING"
    morning_sec = 0
    lunch_break_sec = 0
    afternoon_sec = 0

    if lunch_s_dt and lunch_e_dt:
        if lunch_s_dt < start_dt:
            return {"success": False, "message": "A pausa de almoço não pode ser anterior ao horário de início."}
        if lunch_e_dt < lunch_s_dt:
            return {"success": False, "message": "O retorno do almoço não pode ser anterior à saída para almoço."}
        if end_dt and end_dt < lunch_e_dt:
            return {"success": False, "message": "O horário de encerramento não pode ser anterior ao retorno do almoço."}

        intervals.append(
            TimeInterval(
                start=start_dt.isoformat(),
                end=lunch_s_dt.isoformat(),
                issue_key=clean_issue,
                comment=clean_comment,
            )
        )
        morning_sec = int((lunch_s_dt - start_dt).total_seconds())
        lunch_break_sec = int((lunch_e_dt - lunch_s_dt).total_seconds())

        if end_dt:
            intervals.append(
                TimeInterval(
                    start=lunch_e_dt.isoformat(),
                    end=end_dt.isoformat(),
                    issue_key=clean_issue,
                    comment=clean_comment,
                )
            )
            afternoon_sec = int((end_dt - lunch_e_dt).total_seconds())
            status = "COMPLETED"
        else:
            intervals.append(
                TimeInterval(
                    start=lunch_e_dt.isoformat(),
                    end=None,
                    issue_key=clean_issue,
                    comment=clean_comment,
                )
            )
            now_dt = datetime.now()
            afternoon_sec = max(0, int((now_dt - lunch_e_dt).total_seconds())) if target_date == date.today().isoformat() else 0
            status = "RUNNING"

    elif lunch_s_dt and not lunch_e_dt and not end_dt:
        if lunch_s_dt < start_dt:
            return {"success": False, "message": "A pausa de almoço não pode ser anterior ao horário de início."}
        intervals.append(
            TimeInterval(
                start=start_dt.isoformat(),
                end=lunch_s_dt.isoformat(),
                issue_key=clean_issue,
                comment=clean_comment,
            )
        )
        morning_sec = int((lunch_s_dt - start_dt).total_seconds())
        status = "PAUSED_LUNCH"

    else:
        if end_dt:
            if end_dt < start_dt:
                return {"success": False, "message": "O horário de encerramento não pode ser anterior ao horário de início."}
            intervals.append(
                TimeInterval(
                    start=start_dt.isoformat(),
                    end=end_dt.isoformat(),
                    issue_key=clean_issue,
                    comment=clean_comment,
                )
            )
            morning_sec = int((end_dt - start_dt).total_seconds())
            status = "COMPLETED"
        else:
            intervals.append(
                TimeInterval(
                    start=start_dt.isoformat(),
                    end=None,
                    issue_key=clean_issue,
                    comment=clean_comment,
                )
            )
            now_dt = datetime.now()
            morning_sec = max(0, int((now_dt - start_dt).total_seconds())) if target_date == date.today().isoformat() else 0
            status = "RUNNING"

    total_sec = morning_sec + afternoon_sec
    return {
        "success": True,
        "date_str": target_date,
        "started_iso": start_dt.isoformat(),
        "start_hm": start_dt.strftime("%H:%M"),
        "lunch_start_hm": lunch_s_dt.strftime("%H:%M") if lunch_s_dt else "",
        "lunch_end_hm": lunch_e_dt.strftime("%H:%M") if lunch_e_dt else "",
        "end_hm": end_dt.strftime("%H:%M") if end_dt else "",
        "morning_seconds": morning_sec,
        "lunch_break_seconds": lunch_break_sec,
        "afternoon_seconds": afternoon_sec,
        "total_seconds": total_sec,
        "status": status,
        "intervals": intervals,
    }


@dataclass
class QueueItem:
    """Item na fila de sincronizacao de worklog com o Jira."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    issue_key: str = ""
    started_iso: str = ""
    time_spent_seconds: int = 0
    comment: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    retry_count: int = 0
    last_error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> QueueItem:
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            issue_key=data.get("issue_key", ""),
            started_iso=data.get("started_iso", ""),
            time_spent_seconds=data.get("time_spent_seconds", 0),
            comment=data.get("comment", ""),
            created_at=data.get("created_at", datetime.now().isoformat()),
            retry_count=data.get("retry_count", 0),
            last_error=data.get("last_error"),
        )


@dataclass
class DaySummary:
    """Resumo de fechamento de um dia para armazenamento no historico."""
    date_str: str
    total_seconds: int
    by_issue: Dict[str, int]
    is_logged: bool
    worklog_ids: List[str]
    completed_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DaySummary:
        return cls(
            date_str=data["date_str"],
            total_seconds=data.get("total_seconds", 0),
            by_issue=data.get("by_issue", {}),
            is_logged=data.get("is_logged", False),
            worklog_ids=data.get("worklog_ids", []),
            completed_at=data.get("completed_at", datetime.now().isoformat()),
        )


class StateManager:
    """Gerenciador de leitura e gravacao atomica do estado, fila e historico."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or get_default_config_dir()
        self.state_file = self.base_dir / "state.json"
        self.queue_file = self.base_dir / "queue.json"
        self.history_file = self.base_dir / "history.json"
        self.schedules_file = self.base_dir / "worklog_schedules.json"

    def load_state(self) -> DailyState:
        """Carrega o estado atual do dia. Se for de um dia anterior, salva no historico e reseta."""
        today_str = date.today().isoformat()
        if not self.state_file.exists():
            state = DailyState(date_str=today_str)
            self.save_state(state)
            return state

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                state = DailyState.from_dict(data)
                if state.date_str != today_str:
                    # Fecha com precisao qualquer intervalo em aberto do dia anterior
                    state.close_previous_day_intervals()
                    total_sec = state.get_total_seconds()

                    if total_sec > 0:
                        # Se o dia anterior ainda nao havia sido transmitido ao Jira, enfileira na fila offline
                        if not state.is_logged:
                            first_start = state.get_first_start_time()
                            started_iso = first_start.isoformat() if first_start else (state.intervals[0].start if state.intervals else datetime.now().isoformat())
                            for issue_key, sec in state.get_seconds_by_issue().items():
                                if sec > 0 and issue_key and issue_key != "SEM_TICKET":
                                    comment_to_use = "" if state.no_comment else state.get_issue_comment(issue_key, default="Lancamento automatico de expediente via JiraBot")
                                    self.enqueue_worklog(
                                        issue_key=issue_key,
                                        started_iso=started_iso,
                                        time_spent_seconds=sec,
                                        comment=comment_to_use
                                    )
                            state.is_logged = True

                        self.save_day_to_history(state)

                    # Novo dia iniciado limpo
                    state = DailyState(date_str=today_str)
                    self.save_state(state)
                return state
        except Exception:
            state = DailyState(date_str=today_str)
            self.save_state(state)
            return state

    def save_state(self, state: DailyState) -> None:
        """Salva o estado no arquivo com gravacao segura e atomica."""
        temp_file = self.state_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(state.to_dict(), f, indent=2, ensure_ascii=False)
        if temp_file.exists():
            temp_file.replace(self.state_file)

    def load_queue(self) -> List[QueueItem]:
        """Carrega os itens pendentes na fila de sincronizacao."""
        if not self.queue_file.exists():
            return []
        try:
            with open(self.queue_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [QueueItem.from_dict(item) for item in data]
        except Exception:
            return []

    def save_queue(self, queue: List[QueueItem]) -> None:
        """Salva a fila de sincronizacao em disco."""
        temp_file = self.queue_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump([item.to_dict() for item in queue], f, indent=2, ensure_ascii=False)
        if temp_file.exists():
            temp_file.replace(self.queue_file)

    def enqueue_worklog(self, issue_key: str, started_iso: str, time_spent_seconds: int, comment: str) -> QueueItem:
        """Adiciona ou atualiza um lancamento na fila de contingencia evitando duplicatas."""
        queue = self.load_queue()
        work_date = started_iso[:10] if len(started_iso) >= 10 else started_iso

        # Verifica se ja existe um item para o mesmo ticket e mesma data
        existing = None
        for q in queue:
            q_date = q.started_iso[:10] if len(q.started_iso) >= 10 else q.started_iso
            if q.issue_key == issue_key and q_date == work_date:
                existing = q
                break

        if existing:
            # Atualiza os dados com a versao mais recente/consolidada
            existing.time_spent_seconds = max(existing.time_spent_seconds, time_spent_seconds)
            existing.comment = comment or existing.comment
            existing.started_iso = started_iso
            self.save_queue(queue)
            return existing

        item = QueueItem(
            issue_key=issue_key,
            started_iso=started_iso,
            time_spent_seconds=time_spent_seconds,
            comment=comment,
        )
        queue.append(item)
        self.save_queue(queue)
        return item

    def deduplicate_queue(self) -> List[QueueItem]:
        """Varre a fila e elimina quaisquer itens duplicados para o mesmo ticket na mesma data."""
        queue = self.load_queue()
        unique_map: Dict[Tuple[str, str], QueueItem] = {}

        for item in queue:
            work_date = item.started_iso[:10] if len(item.started_iso) >= 10 else item.started_iso
            key = (item.issue_key, work_date)
            if key not in unique_map:
                unique_map[key] = item
            else:
                # Mantem o com maior tempo ou mais recente
                if item.time_spent_seconds >= unique_map[key].time_spent_seconds:
                    unique_map[key] = item

        deduped = list(unique_map.values())
        self.save_queue(deduped)
        return deduped

    def remove_from_queue(self, item_id: str) -> None:
        """Remove um item sincronizado com sucesso da fila."""
        queue = self.load_queue()
        queue = [q for q in queue if q.id != item_id]
        self.save_queue(queue)

    def load_history(self) -> List[DaySummary]:
        """Carrega todo o historico de dias salvos."""
        if not self.history_file.exists():
            return []
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [DaySummary.from_dict(item) for item in data]
        except Exception:
            return []

    def save_day_to_history(self, state: DailyState) -> None:
        """Registra o resumo do dia no historico sem duplicar registros do mesmo dia."""
        history = self.load_history()
        summary = DaySummary(
            date_str=state.date_str,
            total_seconds=state.get_total_seconds(),
            by_issue=state.get_seconds_by_issue(),
            is_logged=state.is_logged,
            worklog_ids=state.jira_worklog_ids,
            completed_at=datetime.now().isoformat(),
        )

        # Remove versao anterior da mesma data se ja existir
        history = [h for h in history if h.date_str != state.date_str]
        history.append(summary)
        history.sort(key=lambda x: x.date_str)

        temp_file = self.history_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump([h.to_dict() for h in history], f, indent=2, ensure_ascii=False)
        if temp_file.exists():
            temp_file.replace(self.history_file)

    def load_worklog_schedules(self) -> Dict[str, Dict[str, Any]]:
        """Carrega os metadados de horarios detalhados (inicio, almoco, retorno, encerramento) dos worklogs."""
        if not self.schedules_file.exists():
            return {}
        try:
            with open(self.schedules_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def save_worklog_schedule(self, worklog_id: str, schedule_data: Dict[str, Any]) -> None:
        """Salva os horarios detalhados de um worklog especifico."""
        if not worklog_id:
            return
        schedules = self.load_worklog_schedules()
        schedules[str(worklog_id)] = {
            "start_hm": schedule_data.get("start_hm", ""),
            "lunch_start_hm": schedule_data.get("lunch_start_hm", ""),
            "lunch_end_hm": schedule_data.get("lunch_end_hm", ""),
            "end_hm": schedule_data.get("end_hm", ""),
            "updated_at": datetime.now().isoformat(),
        }
        temp_file = self.schedules_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(schedules, f, indent=2, ensure_ascii=False)
        if temp_file.exists():
            temp_file.replace(self.schedules_file)

    def delete_worklog_schedule(self, worklog_id: str) -> None:
        """Remove os metadados de horario de um worklog excluido."""
        schedules = self.load_worklog_schedules()
        if str(worklog_id) in schedules:
            del schedules[str(worklog_id)]
            temp_file = self.schedules_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(schedules, f, indent=2, ensure_ascii=False)
            if temp_file.exists():
                temp_file.replace(self.schedules_file)

    def get_or_infer_worklog_schedule(
        self,
        worklog: Dict[str, Any],
        default_lunch_start: str = "12:00",
        default_lunch_end: str = "13:30",
    ) -> Dict[str, str]:
        """
        Retorna os horarios de inicio, pausa de almoco, retorno e encerramento de um worklog.
        Caso nao exista registro explicito salvo em worklog_schedules.json, calcula/infere
        automaticamente com base no horario de inicio (started) e duracao (time_spent_seconds).
        """
        wid = str(worklog.get("id", ""))
        schedules = self.load_worklog_schedules()
        if wid and wid in schedules:
            saved = schedules[wid]
            if saved.get("start_hm"):
                return {
                    "start_hm": saved.get("start_hm", ""),
                    "lunch_start_hm": saved.get("lunch_start_hm", ""),
                    "lunch_end_hm": saved.get("lunch_end_hm", ""),
                    "end_hm": saved.get("end_hm", ""),
                    "is_saved": "true",
                }

        started_str = worklog.get("started", "")
        total_sec = int(worklog.get("time_spent_seconds", 0) or 0)
        date_part = started_str[:10] if len(started_str) >= 10 else date.today().isoformat()
        start_hm = started_str[11:16] if len(started_str) >= 16 else "08:00"

        start_dt = _parse_hm(date_part, start_hm) or datetime(2026, 1, 1, 8, 0)
        ls_dt = _parse_hm(date_part, default_lunch_start) or datetime(start_dt.year, start_dt.month, start_dt.day, 12, 0)
        le_dt = _parse_hm(date_part, default_lunch_end) or datetime(start_dt.year, start_dt.month, start_dt.day, 13, 30)

        # Se o inicio foi antes do almoco e o tempo total ultrapassa o periodo da manha + 30min
        morning_capacity = max(0, int((ls_dt - start_dt).total_seconds()))
        if start_dt < ls_dt and total_sec > (morning_capacity + 1800) and total_sec >= 14400:
            afternoon_sec = total_sec - morning_capacity
            end_dt = le_dt + timedelta(seconds=afternoon_sec)
            return {
                "start_hm": start_dt.strftime("%H:%M"),
                "lunch_start_hm": ls_dt.strftime("%H:%M"),
                "lunch_end_hm": le_dt.strftime("%H:%M"),
                "end_hm": end_dt.strftime("%H:%M"),
                "is_saved": "false",
            }
        else:
            end_dt = start_dt + timedelta(seconds=total_sec)
            return {
                "start_hm": start_dt.strftime("%H:%M"),
                "lunch_start_hm": "",
                "lunch_end_hm": "",
                "end_hm": end_dt.strftime("%H:%M"),
                "is_saved": "false",
            }

