"""
Motor de Negocio do JiraBot (Engine de Maquina de Estados e Calculo de Horas).
"""

from __future__ import annotations

from datetime import datetime, timedelta, time as dtime
import logging
import os
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from config import BotConfig, ShiftProfile
from notifier import send_notification
from review_dialog import get_fallback_description, show_pre_exit_popup
from storage import DailyState, StateManager, TimeInterval, clean_jira_issue_key

logger = logging.getLogger("JiraBot.Engine")

_WORKLOG_SYNC_LOCK = threading.RLock()


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
        on_worklog_trigger: Optional[Callable[[str, int, str, str], Any]] = None,
        on_worklog_update: Optional[Callable[[str, str, int, str, str], bool]] = None,
        auto_reload_config: Optional[bool] = None,
    ):
        self.auto_reload_config = (config is None) if auto_reload_config is None else bool(auto_reload_config)
        self.config = config or BotConfig.load()
        self.state_manager = state_manager or StateManager()
        self.on_worklog_trigger = on_worklog_trigger
        self.on_worklog_update = on_worklog_update
        self.state: DailyState = self.state_manager.load_state()

    def refresh_config(self) -> BotConfig:
        """Recarrega config.json do disco quando habilitado, evitando uso de preferencias em memoria obsoletas."""
        if self.auto_reload_config:
            try:
                self.config = BotConfig.load()
            except Exception:
                pass
        return self.config

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
        *,
        expected_issue: Optional[str] = None,
    ) -> DailyState:
        """
        Troca a tarefa ativa em tempo real. Se o cronometro estiver rodando,
        fecha o intervalo anterior sob a tarefa antiga e abre um novo sob a nova tarefa.
        Permite tambem definir a descricao do que sera feito.
        """
        now = now or datetime.now()
        now_iso = now.isoformat()
        self.refresh_config()
        self.refresh_state()

        old_issue = self.get_active_issue()
        if expected_issue is not None:
            interval = self.state.intervals[-1] if self.state.intervals else None
            if (
                old_issue != expected_issue or self.state.status != "RUNNING" or self.state.is_logged
                or not interval or interval.end is not None or now < datetime.fromisoformat(interval.start)
                or clean_jira_issue_key(interval.issue_key or old_issue) != old_issue
            ):
                raise ValueError("O intervalo ativo mudou. Confira o ticket antes de trocar.")
        new_issue = clean_jira_issue_key(new_issue_key) or old_issue

        # Fixa a chave nos intervalos preexistentes sem ticket antes de trocar target_issue
        for inter in self.state.intervals:
            if not inter.issue_key or clean_jira_issue_key(inter.issue_key) == "SEM_TICKET":
                inter.issue_key = old_issue

        if self.state.status == "RUNNING":
            open_inter = self.state.intervals[-1] if (self.state.intervals and self.state.intervals[-1].end is None) else None
            if open_inter and clean_jira_issue_key(open_inter.issue_key or old_issue) == new_issue:
                if comment:
                    open_inter.comment = comment.strip()
            else:
                if open_inter:
                    open_inter.end = now_iso
                    if not open_inter.issue_key:
                        open_inter.issue_key = old_issue
                # Inicia novo intervalo para o novo ticket exatamente no instante da troca
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

        self.state_manager.create_snapshot(self.state, reason="pre_transfer")
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

        self.refresh_config()
        self.refresh_state()
        profile = self.get_profile()
        active_issue = self.get_active_issue()
        logger.info(f"Processando UNLOCK as {now.strftime('%H:%M:%S')}. Estado atual: {self.state.status}")

        if self.state.status == "IDLE":
            # Inicia o dia de trabalho
            self.state.status = "RUNNING"
            self.state.intervals.append(TimeInterval(start=now_iso, issue_key=active_issue))
            self.state.last_event = "STARTED_ON_UNLOCK"
            self.state.last_event_time = now_iso
            self.state_manager.save_state(self.state)
            self.state_manager.create_snapshot(self.state, reason="shift_start")

            msg = f"Inicio de expediente registrado as {now.strftime('%H:%M')}. Perfil: {profile.name} (Ticket: {active_issue or 'Nenhum'})"
            logger.info(msg)
            send_notification("JiraBot - Cronometro Iniciado", msg, self.config.notifications_enabled)

        elif self.state.status == "PAUSED_LUNCH":
            current_time = now.time()

            # Se o desbloqueio ocorrer antes do inicio da janela de retorno (ex: antes das 13:25 para retorno as 13:30):
            # O usuario esta apenas mexendo no PC para uso pessoal; o cronometro e mantido em pausa
            if current_time < profile.lunch_end_window.start_time:
                self.state.unlocked_during_lunch = True
                self.state_manager.save_state(self.state)
                logger.info(
                    f"Desbloqueio as {now.strftime('%H:%M')} antes da janela de retorno do almoco "
                    f"({profile.lunch_end_window.start_str}). Usuario mexendo no PC; cronometro mantido em pausa."
                )
                return self.state

            # Retorno valido do intervalo de almoco
            self.state.unlocked_during_lunch = False
            self.state.status = "RUNNING"
            self.state.intervals.append(TimeInterval(start=now_iso, issue_key=active_issue))
            self.state.last_event = "RESUMED_LUNCH_UNLOCK"
            self.state.last_event_time = now_iso
            self.state_manager.save_state(self.state)
            self.state_manager.create_snapshot(self.state, reason="resume_lunch")

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
            self.state_manager.create_snapshot(self.state, reason="resume_away")

            logger.info(f"Sessao retomada apos bloqueio intermediario as {now.strftime('%H:%M')}.")

        elif self.state.status == "COMPLETED":
            # Caso o usuario desbloqueie apos ter completado o dia (ex: hora extra), retoma como RUNNING
            self.state.status = "RUNNING"
            self.state.intervals.append(TimeInterval(start=now_iso, issue_key=active_issue))
            self.state.last_event = "RESUMED_AFTER_COMPLETION"
            self.state.last_event_time = now_iso
            self.state.is_logged = False
            self.state_manager.save_state(self.state)
            self.state_manager.create_snapshot(self.state, reason="resume_work")
            logger.info(f"Desbloqueio detectado apos dia completado as {now.strftime('%H:%M')}. Retomando contagem de horas extras.")

        return self.state

    def _has_completed_lunch_today(self) -> bool:
        """Verifica se o usuario ja concluiu o intervalo de almoco hoje."""
        if self.state.last_event == "RESUMED_LUNCH_UNLOCK":
            return True
        for i in range(len(self.state.intervals) - 1):
            cur_end = self.state.intervals[i].end
            nxt_start = self.state.intervals[i + 1].start
            if cur_end and nxt_start:
                try:
                    ce_dt = datetime.fromisoformat(cur_end)
                    ns_dt = datetime.fromisoformat(nxt_start)
                    gap_sec = (ns_dt - ce_dt).total_seconds()
                    # Pausa de pelo menos 20 min com saida entre 11h e 14h
                    if gap_sec >= 1200 and 11 <= ce_dt.hour <= 14:
                        return True
                except Exception:
                    pass
        return False

    def handle_lock(self, now: Optional[datetime] = None) -> DailyState:
        """Processa o evento de bloqueio de tela (WTS_SESSION_LOCK)."""
        now = now or datetime.now()
        current_time = now.time()
        now_iso = now.isoformat()

        self.refresh_config()
        self.refresh_state()
        profile = self.get_profile()
        logger.info(f"Processando LOCK as {now.strftime('%H:%M:%S')}. Estado atual: {self.state.status}")

        if self.state.status == "PAUSED_LUNCH":
            self.state.unlocked_during_lunch = False
            self.state_manager.save_state(self.state)

        if self.state.status == "RUNNING":
            # Fecha o intervalo de trabalho corrente
            if self.state.intervals and self.state.intervals[-1].end is None:
                self.state.intervals[-1].end = now_iso
                if not self.state.intervals[-1].issue_key:
                    self.state.intervals[-1].issue_key = self.get_active_issue()

            total_seconds = self.state.get_total_seconds()
            target_seconds = profile.target_hours * 3600

            # Avalia em qual janela de horario o bloqueio ocorreu.
            # E considerado pausa para almoco se:
            # 1. Estiver na janela nominal lunch_start_window; OU
            # 2. Estiver entre o inicio da janela de almoco e o horario planejado de retorno,
            #    desde que o usuario ainda nao tenha completado o almoco hoje
            is_lunch_window = profile.lunch_start_window.contains(current_time) or (
                current_time >= profile.lunch_start_window.start_time
                and current_time <= profile.get_planned_lunch_end_time()
                and not self._has_completed_lunch_today()
            )

            if is_lunch_window:
                # Pausa para almoco
                self.state.status = "PAUSED_LUNCH"
                self.state.last_event = "PAUSED_LUNCH_LOCK"
                self.state.last_event_time = now_iso
                self.state_manager.save_state(self.state)
                self.state_manager.create_snapshot(self.state, reason="pause_lunch")

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
                self.state_manager.create_snapshot(self.state, reason="shift_completed")

                total_str = format_duration(total_seconds)
                msg = f"Fim de expediente detectado as {now.strftime('%H:%M')}. Total trabalhado hoje: {total_str}"
                logger.info(msg)
                send_notification("JiraBot - Expediente Finalizado", msg, self.config.notifications_enabled)

                if self.config.auto_log_on_exit and not self.state.is_logged:
                    self._trigger_worklog_all_issues(auto_triggered=True)

            else:
                # Bloqueio intermediario fora das janelas planejadas (ex: banheiro, cafe)
                if self.config.intermediate_lock_mode == "pause":
                    self.state.status = "PAUSED_AWAY"
                    self.state.last_event = "PAUSED_AWAY_LOCK"
                    self.state.last_event_time = now_iso
                    self.state_manager.save_state(self.state)
                    self.state_manager.create_snapshot(self.state, reason="pause_away")
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

        self.refresh_config()
        self.refresh_state()
        profile = self.get_profile()
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
            self.state_manager.create_snapshot(self.state, reason="shift_completed")

            total_str = format_duration(total_seconds)
            logger.info(f"Fim de expediente por desligamento do PC as {now.strftime('%H:%M')}. Total: {total_str}")

            if self.config.auto_log_on_exit and not self.state.is_logged:
                self._trigger_worklog_all_issues(auto_triggered=True)

        elif was_running:
            is_lunch_window = profile.lunch_start_window.contains(current_time) or (
                current_time >= profile.lunch_start_window.start_time
                and current_time <= profile.get_planned_lunch_end_time()
                and not self._has_completed_lunch_today()
            )
            if is_lunch_window:
                self.state.status = "PAUSED_LUNCH"
                self.state.last_event = "PAUSED_LUNCH_SHUTDOWN"
                self.state.last_event_time = now_iso
                self.state_manager.save_state(self.state)
                self.state_manager.create_snapshot(self.state, reason="pause_lunch")
                logger.info(f"Pausa de almoco registrada por desligamento do PC as {now.strftime('%H:%M')}.")
            else:
                self.state.status = "PAUSED_AWAY"
                self.state.last_event = "PAUSED_SHUTDOWN"
                self.state.last_event_time = now_iso
                self.state_manager.save_state(self.state)
                self.state_manager.create_snapshot(self.state, reason="pause_away")
                logger.info(f"Cronometro pausado e salvo por desligamento/reinicializacao as {now.strftime('%H:%M')}.")

        return self.state

    def check_scheduled_transitions(self, now: Optional[datetime] = None) -> DailyState:
        """
        Verificacao periodica executada pelo daemon:
        1. Retomada automatica de almoco caso o usuario tenha desbloqueado antecipadamente para mexer no PC
           e o horario de retorno tenha sido atingido.
        2. Alerta de revisao de descricao configuravel antes do horario nominal de saida.
        """
        now = now or datetime.now()
        self.refresh_config()
        self.refresh_state()
        profile = self.get_profile()

        # Retomada automatica de almoco caso o usuario tenha desbloqueado antecipadamente para mexer no PC
        # e o relogio tenha atingido o horario nominal planejado de retorno do almoco (ex: 13:30)
        try:
            if self.state.status == "PAUSED_LUNCH" and getattr(self.state, "unlocked_during_lunch", False):
                if now.time() >= profile.get_planned_lunch_end_time():
                    now_iso = now.isoformat()
                    self.state.unlocked_during_lunch = False
                    self.state.status = "RUNNING"
                    active_issue = self.get_active_issue()
                    self.state.intervals.append(TimeInterval(start=now_iso, issue_key=active_issue))
                    self.state.last_event = "RESUMED_LUNCH_SCHEDULED"
                    self.state.last_event_time = now_iso
                    self.state_manager.save_state(self.state)
                    self.state_manager.create_snapshot(self.state, reason="resume_lunch")

                    total_str = format_duration(self.state.get_total_seconds())
                    msg = f"Retorno do almoco iniciado as {now.strftime('%H:%M')} conforme planejado. Tempo acumulado: {total_str}"
                    logger.info(msg)
                    send_notification("JiraBot - Retorno do Almoco", msg, self.config.notifications_enabled)
        except Exception as e:
            logger.error(f"Erro ao avaliar retorno agendado de almoco: {e}")

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
                    self._mascot_event("exit_warning")
                    show_pre_exit_popup(self.state_manager)
        except Exception as e:
            logger.error(f"Erro ao avaliar alerta pre-saida: {e}")

        return self.state

    def _mascot_event(self, name: str) -> None:
        """Comunica apresentação por melhor esforço, sem alterar o estado diário."""
        try:
            from mascote_runtime.control import publish_event
            publish_event(name, base=self.state_manager.base_dir)
        except Exception:
            pass

    def _acquire_cross_process_lock(self, timeout_sec: float = 15.0):
        """Delega para o lock reentrante multi-processo centralizado no StateManager."""
        return self.state_manager.worklog_sync_lock(timeout_sec=timeout_sec)

    def _fetch_existing_jira_worklogs_for_date(self, date_str: str) -> Dict[str, List[Dict[str, Any]]]:
        """Consulta worklogs ja existentes no Jira para a data informada, agrupados por ticket."""
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        try:
            jira_cfg = self.config.jira
            if not (
                getattr(jira_cfg, "base_url", "").strip()
                and getattr(jira_cfg, "email", "").strip()
                and getattr(jira_cfg, "api_token", "").strip()
            ):
                return grouped

            from jira_client import JiraClient
            client = JiraClient(jira_cfg, self.state_manager)
            items = client.get_user_worklogs_by_date_range(date_str, date_str)
            if not isinstance(items, list):
                return grouped
            for w in items:
                if not isinstance(w, dict):
                    continue
                k = clean_jira_issue_key(str(w.get("issue_key") or ""))
                if not k or k == "SEM_TICKET":
                    continue
                grouped.setdefault(k, []).append(w)
        except Exception as e:
            logger.warning(f"Falha ao reconciliar worklogs existentes no Jira para {date_str}: {e}")
        return grouped

    def _clear_queued_worklogs_for_date(self, date_str: str, issue_key: Optional[str] = None) -> None:
        """Remove da fila offline apontamentos ja confirmados para a data (e ticket opcional)."""
        try:
            target_issue = clean_jira_issue_key(issue_key) if issue_key else None
            for q_item in self.state_manager.load_queue():
                q_date = q_item.started_iso[:10] if len(q_item.started_iso) >= 10 else ""
                if q_date != date_str:
                    continue
                if target_issue and clean_jira_issue_key(q_item.issue_key) != target_issue:
                    continue
                self.state_manager.remove_from_queue(q_item.id)
        except Exception:
            pass

    def _trigger_worklog_all_issues(self, auto_triggered: bool = False) -> None:
        """
        Aciona o lancamento (ou atualizacao idempotente) do worklog para cada ticket trabalhado no dia.
        Garante exclusao mutua entre threads/processos, envia o horario de inicio real de cada ticket
        e reconcilia com o Jira antes de enviar para evitar duplicacoes.
        """
        with _WORKLOG_SYNC_LOCK:
            with self._acquire_cross_process_lock():
                self.refresh_config()
                self.refresh_state()

                if auto_triggered and not getattr(self.config, "auto_log_on_exit", True):
                    logger.info(
                        "Auto-lancamento no encerramento desabilitado na configuracao atual; envio automatico ignorado."
                    )
                    return

                # Garante que nenhum intervalo fique em aberto no momento do envio
                if self.state.intervals and self.state.intervals[-1].end is None:
                    self.state.intervals[-1].end = datetime.now().isoformat()
                    if not self.state.intervals[-1].issue_key:
                        self.state.intervals[-1].issue_key = self.get_active_issue()
                    self.state_manager.save_state(self.state)

                self._mascot_event("worklog_start")
                default_issue = self.config.jira.default_issue
                by_issue = self.state.get_seconds_by_issue(default_issue=default_issue)
                day_shift_summary = self.state.get_shift_times_summary()
                if day_shift_summary.get("start_hm"):
                    self.state_manager.save_day_shift_schedule(self.state.date_str, day_shift_summary)

                if not any(seconds > 0 for seconds in by_issue.values()):
                    return

                # Reconciliacao preventiva com worklogs ja gravados no Jira para a data
                existing_jira = self._fetch_existing_jira_worklogs_for_date(self.state.date_str)
                jira_total_all_seconds = sum(
                    sum(max(0, int(w.get("time_spent_seconds", 0) or 0)) for w in lst)
                    for lst in existing_jira.values()
                )
                local_total_all_seconds = sum(max(0, int(s or 0)) for s in by_issue.values())
                jira_has_any_for_date = any(len(lst) > 0 for lst in existing_jira.values())
                day_already_covered = (
                    jira_has_any_for_date
                    and local_total_all_seconds > 0
                    and jira_total_all_seconds >= max(60, local_total_all_seconds - 180)
                )

                # Caso o dia nao tenha registros no state local (ex: lancamento manual QE-6668 4h + ATIVDIV-32 2h
                # diretamente no Jira/Painel), mas o total no Jira ja cubra o tempo local, reconcilia sem duplicar.
                if not self.state.logged_worklogs_by_issue and day_already_covered:
                    for r_key, r_list in existing_jira.items():
                        for rw in r_list:
                            r_wid = str(rw.get("id") or "").strip()
                            if r_wid and r_wid not in self.state.jira_worklog_ids:
                                self.state.jira_worklog_ids.append(r_wid)
                        if r_list:
                            last_rw = r_list[-1]
                            last_rwid = str(last_rw.get("id") or "").strip()
                            r_sum_sec = sum(max(0, int(x.get("time_spent_seconds", 0) or 0)) for x in r_list)
                            if last_rwid:
                                self.state.logged_worklogs_by_issue[r_key] = {
                                    "worklog_id": last_rwid,
                                    "seconds": r_sum_sec,
                                    "started_iso": str(last_rw.get("started") or ""),
                                    "comment": str(last_rw.get("comment") or ""),
                                    "updated_at": datetime.now().isoformat(),
                                }
                    self._clear_queued_worklogs_for_date(self.state.date_str)
                    self.state.is_logged = True
                    self.state_manager.save_state(self.state)
                    self.state_manager.save_day_to_history(self.state)
                    logger.info(
                        f"Dia {self.state.date_str} ja possui {jira_total_all_seconds}s lancados no Jira "
                        f"(local={local_total_all_seconds}s). Reconciliado sem criar worklog duplicado."
                    )
                    return

                all_success = True
                for raw_issue_key, seconds in by_issue.items():
                    if seconds <= 0:
                        continue

                    eff_key = raw_issue_key if (raw_issue_key and raw_issue_key != "SEM_TICKET") else default_issue
                    issue_key = clean_jira_issue_key(eff_key)

                    if not issue_key or issue_key == "SEM_TICKET":
                        logger.warning(f"Horas contabilizadas ({seconds}s) sem nenhum ticket associado ou padrao.")
                        all_success = False
                        continue

                    issue_first_start = self.state.get_issue_first_start_time(issue_key, default_issue=default_issue)
                    if not issue_first_start:
                        issue_first_start = self.state.get_first_start_time()
                    started_iso = issue_first_start.isoformat() if issue_first_start else datetime.now().isoformat()
                    issue_schedule = self.state.get_issue_schedule_summary(issue_key, default_issue=default_issue)

                    # Obtem a descricao personalizada daquele ticket ou fallback (a menos que no_comment esteja ativo)
                    if self.state.no_comment:
                        custom_comment = "__EMPTY__"
                    else:
                        custom_comment = self.state.get_issue_comment(issue_key)
                        if not custom_comment:
                            custom_comment = get_fallback_description(issue_key)

                    # Verifica se este ticket ja foi lancado no Jira hoje
                    prev_entry = self.state.logged_worklogs_by_issue.get(issue_key)
                    if prev_entry and prev_entry.get("worklog_id"):
                        prev_wid = str(prev_entry.get("worklog_id")).strip()
                        prev_sec = int(prev_entry.get("seconds", 0) or 0)
                        prev_comm = str(prev_entry.get("comment", "") or "")

                        # 1. Se o tempo (< 60s de diferenca) e a descricao nao mudaram, ignora reenvio duplicado
                        if abs(seconds - prev_sec) < 60 and prev_comm == custom_comment:
                            logger.info(
                                f"Ticket {issue_key} ja lancado hoje (Worklog ID: {prev_wid}, {seconds}s). "
                                f"Envio duplicado evitado."
                            )
                            if not prev_wid.startswith("local_"):
                                if prev_wid not in self.state.jira_worklog_ids:
                                    self.state.jira_worklog_ids.append(prev_wid)
                                if issue_schedule.get("start_hm"):
                                    self.state_manager.save_worklog_schedule(prev_wid, issue_schedule)
                            self._clear_queued_worklogs_for_date(self.state.date_str, issue_key=issue_key)
                            continue

                        # Se o ticket foi registrado manualmente pelo usuario (ex: Novo Lancamento ou divisao)
                        # ou se o Jira ja difere durante gatilho automatico, preserva os registros sem sobrescrever
                        if (auto_triggered and (prev_entry.get("manual") or day_already_covered)) or (
                            bool(prev_entry.get("manual")) and day_already_covered
                        ):
                            logger.info(
                                f"Ticket {issue_key} possui apontamento manual ({prev_wid}) ou dia ja coberto no Jira. "
                                f"Sobrescrita automatica ignorada para preservar os valores lancados."
                            )
                            self._clear_queued_worklogs_for_date(self.state.date_str, issue_key=issue_key)
                            continue

                        # Se houver divergencia remota num disparo automatico (ex: usuario editou/dividiu no Jira),
                        # preserva os registros existentes no Jira em vez de sobrescrever ou recriar
                        remote_list = existing_jira.get(issue_key, [])
                        remote_ids = {str(rw.get("id") or "").strip() for rw in remote_list if rw.get("id")}
                        if auto_triggered and remote_list and prev_wid not in remote_ids:
                            logger.info(
                                f"Worklog local {prev_wid} ({issue_key}) difere do Jira atual ({sorted(remote_ids)}) "
                                f"durante gatilho automatico. Preservando registros existentes sem duplicar."
                            )
                            for rw in remote_list:
                                r_wid = str(rw.get("id") or "").strip()
                                if r_wid and r_wid not in self.state.jira_worklog_ids:
                                    self.state.jira_worklog_ids.append(r_wid)
                            self._clear_queued_worklogs_for_date(self.state.date_str, issue_key=issue_key)
                            self.state_manager.save_state(self.state)
                            continue

                        # 2. Se houve alteracao de tempo/comentario (ex: retomada apos expediente), atualiza via PUT
                        if not prev_wid.startswith("local_"):
                            updated_ok = False
                            is_not_found = False
                            if self.on_worklog_update:
                                try:
                                    raw_upd = self.on_worklog_update(
                                        issue_key, prev_wid, seconds, started_iso, custom_comment
                                    )
                                    if isinstance(raw_upd, dict):
                                        updated_ok = bool(
                                            raw_upd.get("success") or raw_upd.get("status") == "success"
                                        )
                                        if not updated_ok and "404" in str(raw_upd.get("message", "")):
                                            is_not_found = True
                                    else:
                                        updated_ok = bool(raw_upd)
                                except Exception as e:
                                    logger.error(f"Erro ao atualizar worklog {prev_wid} ({issue_key}): {e}")
                                    updated_ok = False
                            else:
                                try:
                                    from jira_client import JiraClient
                                    client = JiraClient(self.config.jira, self.state_manager)
                                    upd_res = client.update_worklog_full(
                                        issue_key=issue_key,
                                        worklog_id=prev_wid,
                                        time_spent_seconds=seconds,
                                        started_iso=started_iso,
                                        comment="" if custom_comment == "__EMPTY__" else custom_comment,
                                    )
                                    updated_ok = bool(upd_res.get("success"))
                                    if not updated_ok and "404" in str(upd_res.get("message", "")):
                                        is_not_found = True
                                except Exception as e:
                                    logger.error(f"Erro ao atualizar worklog {prev_wid} no Jira ({issue_key}): {e}")
                                    updated_ok = False

                            if updated_ok:
                                logger.info(
                                    f"Worklog existente {prev_wid} do ticket {issue_key} atualizado de "
                                    f"{prev_sec}s para {seconds}s com sucesso (sem duplicar)."
                                )
                                self.state.logged_worklogs_by_issue[issue_key] = {
                                    "worklog_id": prev_wid,
                                    "seconds": seconds,
                                    "started_iso": started_iso,
                                    "comment": custom_comment,
                                    "updated_at": datetime.now().isoformat(),
                                }
                                if prev_wid not in self.state.jira_worklog_ids:
                                    self.state.jira_worklog_ids.append(prev_wid)
                                if issue_schedule.get("start_hm"):
                                    self.state_manager.save_worklog_schedule(prev_wid, issue_schedule)
                                self._clear_queued_worklogs_for_date(self.state.date_str, issue_key=issue_key)
                                self.state_manager.save_state(self.state)
                                continue

                            if not is_not_found:
                                # Falha temporaria de rede ao atualizar: nao cria novo POST duplicado
                                all_success = False
                                continue
                            else:
                                # Worklog 404 (foi excluido manualmente no Jira): permite recriar via POST
                                if prev_wid in self.state.jira_worklog_ids:
                                    self.state.jira_worklog_ids.remove(prev_wid)
                    else:
                        # Ainda nao ha prev_entry no state.json: confere se este ticket ja tem worklog no Jira hoje
                        remote_list = existing_jira.get(issue_key, [])
                        if remote_list:
                            remote_sec = sum(
                                max(0, int(rw.get("time_spent_seconds", 0) or 0)) for rw in remote_list
                            )
                            last_rw = remote_list[-1]
                            last_rwid = str(last_rw.get("id") or "").strip()
                            if auto_triggered or abs(remote_sec - seconds) < 120 or day_already_covered:
                                logger.info(
                                    f"Ticket {issue_key} ja possui worklog no Jira para {self.state.date_str} "
                                    f"(ID {last_rwid}, {remote_sec}s remoto vs {seconds}s local). Reconciliado sem duplicar."
                                )
                                for rw in remote_list:
                                    r_wid = str(rw.get("id") or "").strip()
                                    if r_wid and r_wid not in self.state.jira_worklog_ids:
                                        self.state.jira_worklog_ids.append(r_wid)
                                if last_rwid:
                                    self.state.logged_worklogs_by_issue[issue_key] = {
                                        "worklog_id": last_rwid,
                                        "seconds": remote_sec,
                                        "started_iso": str(last_rw.get("started") or started_iso),
                                        "comment": str(last_rw.get("comment") or custom_comment),
                                        "updated_at": datetime.now().isoformat(),
                                    }
                                self._clear_queued_worklogs_for_date(self.state.date_str, issue_key=issue_key)
                                self.state_manager.save_state(self.state)
                                continue

                    # 3. Criacao do worklog para ticket ainda nao lancado hoje
                    success = False
                    new_wid = ""
                    ids_before = set(self.state.jira_worklog_ids)
                    if self.on_worklog_trigger:
                        try:
                            raw_res = self.on_worklog_trigger(issue_key, seconds, started_iso, custom_comment)
                            if isinstance(raw_res, dict):
                                success = bool(raw_res.get("status") == "success" or raw_res.get("success"))
                                new_wid = str(raw_res.get("worklog_id") or "").strip()
                            elif isinstance(raw_res, str):
                                success = bool(raw_res.strip())
                                new_wid = raw_res.strip()
                            else:
                                success = bool(raw_res)
                        except Exception as e:
                            logger.error(f"Erro ao executar callback de worklog para {issue_key}: {e}")
                            success = False

                    if success:
                        if not new_wid:
                            added = [x for x in self.state.jira_worklog_ids if x not in ids_before]
                            if added:
                                new_wid = str(added[-1]).strip()

                        if new_wid and new_wid not in self.state.jira_worklog_ids:
                            self.state.jira_worklog_ids.append(new_wid)

                        recorded_wid = new_wid or f"local_{issue_key}_{self.state.date_str}"
                        self.state.logged_worklogs_by_issue[issue_key] = {
                            "worklog_id": recorded_wid,
                            "seconds": seconds,
                            "started_iso": started_iso,
                            "comment": custom_comment,
                            "updated_at": datetime.now().isoformat(),
                        }
                        if new_wid and issue_schedule.get("start_hm"):
                            self.state_manager.save_worklog_schedule(new_wid, issue_schedule)

                        self._clear_queued_worklogs_for_date(self.state.date_str, issue_key=issue_key)

                        # Persiste imediatamente apos cada ticket enviado para evitar corrida
                        self.state_manager.save_state(self.state)
                    else:
                        all_success = False
                        self.state_manager.enqueue_worklog(
                            issue_key=issue_key,
                            started_iso=started_iso,
                            time_spent_seconds=seconds,
                            comment="" if self.state.no_comment else custom_comment,
                            schedule=issue_schedule if issue_schedule.get("start_hm") else None,
                        )

                if all_success:
                    self.state.is_logged = True
                    self.state_manager.save_state(self.state)
                    self.state_manager.save_day_to_history(self.state)
                    day_shift_summary = self.state.get_shift_times_summary()
                    if day_shift_summary.get("start_hm"):
                        self.state_manager.save_day_shift_schedule(self.state.date_str, day_shift_summary)
                    logger.info("Todos os apontamentos de hoje foram transmitidos ao Jira com sucesso.")
                    if any(seconds > 0 for seconds in by_issue.values()):
                        self._mascot_event("worklog_success")
                else:
                    self._mascot_event("worklog_error")

    def manual_start(self, now: Optional[datetime] = None) -> DailyState:
        """Inicia manualmente a contagem."""
        now = now or datetime.now()
        now_iso = now.isoformat()
        self.refresh_config()
        self.refresh_state()

        active_issue = self.get_active_issue()
        self.state.status = "RUNNING"
        self.state.intervals.append(TimeInterval(start=now_iso, issue_key=active_issue))
        self.state.last_event = "MANUAL_START"
        self.state.last_event_time = now_iso
        self.state_manager.save_state(self.state)
        self.state_manager.create_snapshot(self.state, reason="manual_start")
        return self.state

    def manual_pause(self, now: Optional[datetime] = None) -> DailyState:
        """Pausa manualmente o cronometro."""
        now = now or datetime.now()
        now_iso = now.isoformat()
        self.refresh_config()
        self.refresh_state()

        if self.state.status == "RUNNING":
            if self.state.intervals and self.state.intervals[-1].end is None:
                self.state.intervals[-1].end = now_iso
                if not self.state.intervals[-1].issue_key:
                    self.state.intervals[-1].issue_key = self.get_active_issue()

            profile = self.get_profile()
            current_time = now.time()
            is_lunch_window = profile.lunch_start_window.contains(current_time) or (
                current_time >= profile.lunch_start_window.start_time
                and current_time <= profile.get_planned_lunch_end_time()
                and not self._has_completed_lunch_today()
            )

            if is_lunch_window:
                self.state.status = "PAUSED_LUNCH"
                self.state.last_event = "PAUSED_LUNCH_MANUAL"
                logger.info(f"Pausa de almoco registrada manualmente as {now.strftime('%H:%M')}.")
                self.state.last_event_time = now_iso
                self.state_manager.save_state(self.state)
                self.state_manager.create_snapshot(self.state, reason="pause_lunch")
            else:
                self.state.status = "PAUSED_AWAY"
                self.state.last_event = "MANUAL_PAUSE"
                logger.info(f"Pausa temporaria registrada manualmente as {now.strftime('%H:%M')}.")
                self.state.last_event_time = now_iso
                self.state_manager.save_state(self.state)
                self.state_manager.create_snapshot(self.state, reason="manual_pause")
        return self.state

    def manual_log(
        self,
        issue_key: Optional[str] = None,
        comment: Optional[str] = None,
        no_comment: bool = False,
        now: Optional[datetime] = None,
    ) -> int:
        """Forca o encerramento do dia e lancamento imediato de todas as horas no Jira."""
        with _WORKLOG_SYNC_LOCK:
            now = now or datetime.now()
            now_iso = now.isoformat()
            self.refresh_config()
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
            self.state_manager.create_snapshot(self.state, reason="pre_log_now")

            total_seconds = self.state.get_total_seconds()
            self._trigger_worklog_all_issues(auto_triggered=False)
            return total_seconds
