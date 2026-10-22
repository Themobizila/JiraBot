"""
Modulo de consulta e formatacao de relatorios de horas para o JiraBot.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path

from config import BotConfig
from engine import format_duration
from storage import DaySummary, StateManager


WEEKDAYS_PT = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]


def generate_report(
    days: int = 7,
    base_dir: Optional[Path] = None,
    history_by_date: Optional[Dict[str, DaySummary]] = None,
) -> str:
    """Gera um relatório tabular formatado dos últimos N dias."""
    config = BotConfig.load()
    state_mgr = StateManager(base_dir=base_dir)
    current_state = state_mgr.load_state()

    # Se nao foi passado um historico reconciliado externo, carrega local
    if history_by_date is None:
        history = state_mgr.load_history()
        history_by_date = {h.date_str: h for h in history}

        # Se o dia atual tiver horas acumuladas, inclui no relatorio em tempo real
        if current_state.get_total_seconds() > 0:
            history_by_date[current_state.date_str] = DaySummary(
                date_str=current_state.date_str,
                total_seconds=current_state.get_total_seconds(),
                by_issue=current_state.get_seconds_by_issue(),
                is_logged=current_state.is_logged,
                worklog_ids=current_state.jira_worklog_ids,
                completed_at=current_state.last_event_time,
            )

    profile = config.get_current_profile()
    target_seconds_per_day = int(profile.target_hours * 3600)

    # Construir lista de datas do intervalo
    today = date.today()
    start_date = today - timedelta(days=days - 1)

    lines: List[str] = []
    lines.append("=" * 80)
    lines.append(f"          RELATÓRIO DE HORAS JIRABOT (ÚLTIMOS {days} DIAS)")
    lines.append("=" * 80)
    lines.append(f"{'Data':<12} {'Dia':<5} {'Tickets / Horas':<30} {'Total':<10} {'Meta':<8} {'Jira'}")
    lines.append("-" * 80)

    total_period_seconds = 0
    total_target_seconds = 0

    curr = start_date
    while curr <= today:
        d_str = curr.isoformat()
        day_of_week = WEEKDAYS_PT[curr.weekday()]
        is_weekend = curr.weekday() in [5, 6]

        summary = history_by_date.get(d_str)

        if summary:
            total_sec = summary.total_seconds
            total_period_seconds += total_sec

            # Detalhe dos tickets
            ticket_parts = []
            for issue, sec in summary.by_issue.items():
                if sec > 0:
                    ticket_parts.append(f"{issue} ({format_duration(sec)})")
            ticket_str = ", ".join(ticket_parts) if ticket_parts else "Geral"
            if len(ticket_str) > 28:
                ticket_str = ticket_str[:25] + "..."

            dur_str = format_duration(total_sec)
            target_str = f"{profile.target_hours:.1f}h" if not is_weekend else "0h"
            if not is_weekend:
                total_target_seconds += target_seconds_per_day

            jira_status = "Enviado" if summary.is_logged else "Pendente"
            lines.append(f"{d_str:<12} {day_of_week:<5} {ticket_str:<30} {dur_str:<10} {target_str:<8} {jira_status}")
        else:
            if not is_weekend:
                total_target_seconds += target_seconds_per_day
                lines.append(f"{d_str:<12} {day_of_week:<5} {'-':<30} {'0s':<10} {profile.target_hours:.1f}h     -")
            else:
                lines.append(f"{d_str:<12} {day_of_week:<5} {'[Fim de Semana]':<30} {'-':<10} {'0h':<8} -")

        curr += timedelta(days=1)

    lines.append("-" * 80)
    total_period_str = format_duration(total_period_seconds)
    total_target_str = format_duration(total_target_seconds)

    diff_seconds = total_period_seconds - total_target_seconds
    diff_sign = "+" if diff_seconds >= 0 else "-"
    diff_str = f"{diff_sign}{format_duration(abs(diff_seconds))}"

    lines.append(f"Total Trabalhado no Período : {total_period_str}")
    lines.append(f"Meta Esperada no Período    : {total_target_str}")
    lines.append(f"Saldo de Horas (Banco)      : {diff_str}")
    lines.append("=" * 80)

    return "\n".join(lines)
