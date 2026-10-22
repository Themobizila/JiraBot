"""
Painel Web Interativo do JiraBot (v2.2.0).
Servidor HTTP nativo (Standard Library) com interface grafica Web completa para:
- Monitoramento e controle do servico em background e cronometro do dia
- Dark Mode / Light Mode com persistencia por usuario
- Visualizacao Semanal interativa (semana atual ou escolhida no calendario)
- Adicao e Edicao de lancamentos em quantidade / lote (multiplas semanas ou multi-selecao)
- Edicao visual de horario de inicio, pausa de almoco, retorno e encerramento (hoje e historico Jira)
- Sistema de atualizacao automatica multi-usuario com isolamento seguro de configuracoes e tokens.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from typing import Any, Dict, List, Optional
import urllib.parse
import webbrowser
import winreg

from analytics import get_analytics, normalize_days
from config import BotConfig, ShiftProfile
from daemon import get_status, restart_background, start_background, stop_background
from engine import BotEngine, format_duration
from history import WEEKDAYS_PT, generate_report
from jira_client import JiraClient
from review_dialog import get_fallback_description, show_pre_exit_popup
from web_assets import ANALYTICS_JS, EARLY_JS, LOGO_SVG, THEME_CSS, UI_FX_JS
from storage import (
    DailyState,
    DaySummary,
    StateManager,
    TimeInterval,
    _parse_hm,
    calculate_shift_schedule,
)
from updater import (
    APP_VERSION,
    check_for_updates,
    get_version_info,
    perform_update,
    publish_clean_release,
)

logger = logging.getLogger("JiraBot.WebPanel")

AUTOSTART_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
AUTOSTART_APP_NAME = "JiraBotBackgroundService"


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    """Servidor HTTP multithread com reutilizacao imediata de porta e threads daemon."""
    allow_reuse_address = True
    daemon_threads = True


def is_autostart_enabled() -> bool:
    """Verifica no Registro do Windows (HKCU) se a inicializacao automatica esta ativa."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTOSTART_REG_KEY, 0, winreg.KEY_READ)
        val, _ = winreg.QueryValueEx(key, AUTOSTART_APP_NAME)
        winreg.CloseKey(key)
        return bool(val)
    except Exception:
        return False


def parse_duration_input(text: str) -> Optional[int]:
    """Converte strings como '06:00', '1h30m', '45m', '2h', '1.5h' em segundos."""
    s = (text or "").strip().lower()
    if not s:
        return None
    if ":" in s:
        parts = s.split(":")
        try:
            h = int(parts[0])
            m = int(parts[1]) if len(parts) > 1 else 0
            sec = int(parts[2]) if len(parts) > 2 else 0
            return h * 3600 + m * 60 + sec
        except ValueError:
            return None

    import re
    total = 0
    h_match = re.search(r"(\d+(?:\.\d+)?)\s*h", s)
    m_match = re.search(r"(\d+)\s*m", s)
    s_match = re.search(r"(\d+)\s*s", s)
    if h_match:
        total += int(float(h_match.group(1)) * 3600)
    if m_match:
        total += int(m_match.group(1)) * 60
    if s_match:
        total += int(s_match.group(1))
    if total > 0:
        return total
    try:
        val = float(s.replace(",", "."))
        if val <= 24:
            return int(val * 3600)
        return int(val * 60)
    except ValueError:
        return None


def format_hm_from_seconds(seconds: int) -> str:
    """Formata segundos no padrao HH:MM."""
    if seconds < 0:
        seconds = 0
    h = seconds // 3600
    m = (seconds % 3600) // 60
    return f"{h:02d}:{m:02d}"


def build_dashboard_payload() -> Dict[str, Any]:
    """Constroi o payload completo de status do dia, servico, fila e configuracao."""
    status = get_status()
    config = BotConfig.load()
    profile = config.get_current_profile()
    state_mgr = StateManager()
    state = state_mgr.load_state()
    queue = state_mgr.load_queue()

    active_issue = (state.target_issue or config.jira.default_issue or "ATIVDIV-32").strip().upper()
    total_sec = state.get_total_seconds()
    target_sec = int(profile.target_hours * 3600)
    progress_pct = min(100, round((total_sec / target_sec) * 100, 1)) if target_sec > 0 else 0.0

    intervals_list: List[Dict[str, Any]] = []
    for idx, inter in enumerate(state.intervals):
        dur = inter.get_duration_seconds()
        st_hm = inter.start[11:16] if len(inter.start) >= 16 else ""
        en_hm = inter.end[11:16] if (inter.end and len(inter.end) >= 16) else ""
        intervals_list.append({
            "index": idx,
            "start": inter.start,
            "end": inter.end,
            "start_hm": st_hm,
            "end_hm": en_hm,
            "issue_key": inter.issue_key or active_issue,
            "comment": inter.comment or "",
            "duration_seconds": dur,
            "duration_formatted": format_duration(dur),
        })

    by_issue = state.get_seconds_by_issue(default_issue=config.jira.default_issue)
    all_issues = state.get_all_issues_worked(default_issue=config.jira.default_issue)
    for k in by_issue.keys():
        if k not in all_issues and k != "SEM_TICKET":
            all_issues.append(k)

    issues_summary: List[Dict[str, Any]] = []
    for iss in all_issues:
        sec = by_issue.get(iss, 0)
        custom_c = state.get_issue_comment(iss)
        issues_summary.append({
            "issue_key": iss,
            "seconds": sec,
            "formatted": format_duration(sec),
            "hm_formatted": format_hm_from_seconds(sec),
            "comment": custom_c,
            "is_active": (iss == active_issue),
        })

    queue_list: List[Dict[str, Any]] = []
    for q in queue:
        queue_list.append({
            "id": q.id,
            "issue_key": q.issue_key,
            "date": q.started_iso[:10] if len(q.started_iso) >= 10 else "",
            "started_iso": q.started_iso,
            "time_spent_seconds": q.time_spent_seconds,
            "time_formatted": format_duration(q.time_spent_seconds),
            "comment": q.comment,
            "retry_count": q.retry_count,
            "last_error": q.last_error or "",
        })

    shift_times = state.get_shift_times_summary()

    return {
        "version": APP_VERSION,
        "theme": config.theme or "dark",
        "service": {
            "is_running": status["is_running"],
            "pid": status["pid"],
            "autostart_enabled": is_autostart_enabled(),
        },
        "today": {
            "date_str": state.date_str,
            "status": state.status,
            "total_seconds": total_sec,
            "total_formatted": format_duration(total_sec),
            "total_hm": format_hm_from_seconds(total_sec),
            "target_hours": profile.target_hours,
            "target_seconds": target_sec,
            "target_formatted": format_duration(target_sec),
            "progress_percent": progress_pct,
            "target_issue": active_issue,
            "active_comment": state.get_issue_comment(active_issue),
            "no_comment": state.no_comment,
            "is_logged": state.is_logged,
            "last_event": state.last_event,
            "last_event_time": state.last_event_time[11:19] if len(state.last_event_time) >= 19 else state.last_event_time,
            "shift_times": shift_times,
            "intervals": intervals_list,
            "issues_summary": issues_summary,
        },
        "profile": {
            "name": config.active_profile,
            "description": profile.description,
            "target_hours": profile.target_hours,
            "entry_window": profile.entry_window.to_dict(),
            "lunch_start_window": profile.lunch_start_window.to_dict(),
            "lunch_end_window": profile.lunch_end_window.to_dict(),
            "exit_window": profile.exit_window.to_dict(),
        },
        "queue": queue_list,
    }


def build_alerts_payload() -> Dict[str, Any]:
    """Constroi o payload com status do alerta pre-saida hoje e configuracoes de antecedencia."""
    cfg = BotConfig.load()
    prof = cfg.get_current_profile()
    state_mgr = StateManager()
    state = state_mgr.load_state()

    planned_exit = prof.get_planned_exit_time()
    warn_min = max(1, min(60, int(getattr(cfg, "exit_warning_minutes", 5))))
    exit_dt = datetime(2000, 1, 1, planned_exit.hour, planned_exit.minute, 0)
    trigger_dt = exit_dt - timedelta(minutes=warn_min)

    return {
        "profile_name": cfg.active_profile,
        "profile_desc": prof.description,
        "planned_exit_hm": planned_exit.strftime("%H:%M"),
        "trigger_time_hm": trigger_dt.strftime("%H:%M"),
        "warning_minutes": warn_min,
        "warning_enabled": bool(getattr(cfg, "exit_warning_enabled", True)),
        "warning_popup": bool(getattr(cfg, "exit_warning_popup", True)),
        "notifications_enabled": bool(cfg.notifications_enabled),
        "fired_today": bool(state.prompted_exit_review),
        "state_status": state.status,
    }


def build_weekly_payload(ref_date_str: str = "", fetch_jira: bool = True) -> Dict[str, Any]:
    """
    Constroi a Visualizacao Semanal completa (Segunda a Domingo) com base na data ou semana escolhida,
    combinando historico local, estado de hoje e worklogs reais do Jira naquela semana.
    """
    config = BotConfig.load()
    profile = config.get_current_profile()
    state_mgr = StateManager()
    history = state_mgr.load_history()
    current_state = state_mgr.load_state()

    try:
        ref_date = date.fromisoformat(ref_date_str[:10]) if ref_date_str else date.today()
    except Exception:
        ref_date = date.today()

    # Segunda-feira (weekday == 0) ate Domingo (weekday == 6)
    monday = ref_date - timedelta(days=ref_date.weekday())
    sunday = monday + timedelta(days=6)
    prev_monday = (monday - timedelta(days=7)).isoformat()
    next_monday = (monday + timedelta(days=7)).isoformat()
    today_iso = date.today().isoformat()

    history_by_date: Dict[str, DaySummary] = {h.date_str: h for h in history}
    if current_state.get_total_seconds() > 0:
        history_by_date[current_state.date_str] = DaySummary(
            date_str=current_state.date_str,
            total_seconds=current_state.get_total_seconds(),
            by_issue=current_state.get_seconds_by_issue(default_issue=config.jira.default_issue),
            is_logged=current_state.is_logged,
            worklog_ids=current_state.jira_worklog_ids,
            completed_at=current_state.last_event_time,
        )

    # Busca worklogs diretamente no Jira para o intervalo da semana caso solicitado
    jira_by_date: Dict[str, List[Dict[str, Any]]] = {}
    if fetch_jira:
        try:
            client = JiraClient(config.jira, state_mgr)
            is_8h = config.active_profile == "8h"
            def_ls = "12:00"
            def_le = "13:00" if is_8h else "13:30"
            wls = client.get_user_worklogs_by_date_range(monday.isoformat(), sunday.isoformat())
            for w in wls:
                d_key = w.get("date", "")
                sec = int(w.get("time_spent_seconds", 0) or 0)
                w["time_formatted"] = format_duration(sec)
                w["hm_formatted"] = format_hm_from_seconds(sec)
                w["schedule"] = state_mgr.get_or_infer_worklog_schedule(w, def_ls, def_le)
                jira_by_date.setdefault(d_key, []).append(w)
        except Exception as e:
            logger.warning(f"Falha ao buscar worklogs da semana no Jira: {e}")

    target_sec_per_day = int(profile.target_hours * 3600)
    days_rows: List[Dict[str, Any]] = []
    total_week_seconds = 0
    total_week_target = 0
    weekdays_logged_count = 0

    is_8h_prof = config.active_profile == "8h"
    default_schedule = {
        "start_hm": "07:42" if is_8h_prof else "07:45",
        "lunch_start_hm": "12:00",
        "lunch_end_hm": "13:00" if is_8h_prof else "13:30",
        "end_hm": "17:42" if is_8h_prof else "15:15",
    }

    for i in range(7):
        curr_date = monday + timedelta(days=i)
        d_str = curr_date.isoformat()
        d_br = curr_date.strftime("%d/%m/%Y")
        weekday_name = WEEKDAYS_PT[curr_date.weekday()]
        is_weekend = curr_date.weekday() in [5, 6]
        is_today = (d_str == today_iso)
        is_future = (curr_date > date.today())

        day_wls = jira_by_date.get(d_str, [])
        loc_sum = history_by_date.get(d_str)

        if day_wls:
            day_sec = sum(int(w.get("time_spent_seconds", 0) or 0) for w in day_wls)
            is_logged = True
            first_sch = day_wls[-1].get("schedule", {})
            tickets_info = [
                {
                    "id": w.get("id", ""),
                    "issue_key": w.get("issue_key", ""),
                    "seconds": w.get("time_spent_seconds", 0),
                    "formatted": w.get("time_formatted", ""),
                    "comment": w.get("comment", ""),
                    "schedule": w.get("schedule", {}),
                    "date": d_str,
                }
                for w in day_wls
            ]
        elif is_today and current_state.get_total_seconds() > 0:
            day_sec = current_state.get_total_seconds()
            is_logged = current_state.is_logged
            first_sch = current_state.get_shift_times_summary()
            tickets_info = [
                {
                    "id": "",
                    "issue_key": k,
                    "seconds": v,
                    "formatted": format_duration(v),
                    "comment": current_state.get_issue_comment(k),
                    "schedule": first_sch,
                    "date": d_str,
                }
                for k, v in current_state.get_seconds_by_issue(default_issue=config.jira.default_issue).items()
                if v > 0
            ]
        elif loc_sum and loc_sum.total_seconds > 0:
            day_sec = loc_sum.total_seconds
            is_logged = loc_sum.is_logged
            first_sch = default_schedule
            tickets_info = [
                {
                    "id": loc_sum.worklog_ids[0] if loc_sum.worklog_ids else "",
                    "issue_key": k,
                    "seconds": v,
                    "formatted": format_duration(v),
                    "comment": "",
                    "schedule": first_sch,
                    "date": d_str,
                }
                for k, v in loc_sum.by_issue.items()
                if v > 0
            ]
        else:
            day_sec = 0
            is_logged = False
            first_sch = {"start_hm": "-", "lunch_start_hm": "-", "lunch_end_hm": "-", "end_hm": "-"}
            tickets_info = []

        total_week_seconds += day_sec
        if not is_weekend and not is_future:
            total_week_target += target_sec_per_day
        if not is_weekend and (is_logged or day_sec > 0):
            weekdays_logged_count += 1

        if is_logged:
            status_label = "Lançado no Jira"
            status_type = "logged"
        elif is_today and day_sec > 0:
            status_label = "Em Andamento Hoje"
            status_type = "running"
        elif is_weekend:
            status_label = "Fim de Semana"
            status_type = "weekend"
        elif is_future:
            status_label = "Dia Futuro"
            status_type = "future"
        else:
            status_label = "Sem Lançamento"
            status_type = "missing"

        days_rows.append({
            "date": d_str,
            "date_br": d_br,
            "weekday": weekday_name,
            "is_weekend": is_weekend,
            "is_today": is_today,
            "is_future": is_future,
            "total_seconds": day_sec,
            "total_formatted": format_duration(day_sec) if day_sec > 0 else ("-" if is_weekend else "0s"),
            "target_formatted": "0h" if is_weekend else f"{profile.target_hours:.1f}h",
            "is_logged": is_logged,
            "status_label": status_label,
            "status_type": status_type,
            "schedule": first_sch,
            "tickets": tickets_info,
        })

    full_week_target_sec = int(5 * target_sec_per_day)
    diff_sec = total_week_seconds - total_week_target
    diff_sign = "+" if diff_sec >= 0 else "-"

    return {
        "ref_date": ref_date.isoformat(),
        "monday": monday.isoformat(),
        "sunday": sunday.isoformat(),
        "monday_br": monday.strftime("%d/%m/%Y"),
        "sunday_br": sunday.strftime("%d/%m/%Y"),
        "prev_monday": prev_monday,
        "next_monday": next_monday,
        "total_week_seconds": total_week_seconds,
        "total_week_formatted": format_duration(total_week_seconds),
        "target_until_today_formatted": format_duration(total_week_target),
        "full_week_target_formatted": format_duration(full_week_target_sec),
        "balance_seconds": diff_sec,
        "balance_positive": diff_sec >= 0,
        "balance_formatted": f"{diff_sign}{format_duration(abs(diff_sec))}",
        "weekdays_logged_count": weekdays_logged_count,
        "days": days_rows,
    }


def build_report_payload(days: int = 7) -> Dict[str, Any]:
    """Gera os dados estruturados e texto do relatorio de horas para o Painel Web."""
    config = BotConfig.load()
    state_mgr = StateManager()
    history = state_mgr.load_history()
    current_state = state_mgr.load_state()

    history_by_date: Dict[str, DaySummary] = {h.date_str: h for h in history}
    if current_state.get_total_seconds() > 0:
        history_by_date[current_state.date_str] = DaySummary(
            date_str=current_state.date_str,
            total_seconds=current_state.get_total_seconds(),
            by_issue=current_state.get_seconds_by_issue(default_issue=config.jira.default_issue),
            is_logged=current_state.is_logged,
            worklog_ids=current_state.jira_worklog_ids,
            completed_at=current_state.last_event_time,
        )

    profile = config.get_current_profile()
    target_seconds_per_day = int(profile.target_hours * 3600)

    today = date.today()
    start_date = today - timedelta(days=max(1, days) - 1)

    rows: List[Dict[str, Any]] = []
    total_period_seconds = 0
    total_target_seconds = 0

    curr = start_date
    while curr <= today:
        d_str = curr.isoformat()
        day_of_week = WEEKDAYS_PT[curr.weekday()]
        is_weekend = curr.weekday() in [5, 6]
        summary = history_by_date.get(d_str)

        if summary:
            t_sec = summary.total_seconds
            total_period_seconds += t_sec
            if not is_weekend:
                total_target_seconds += target_seconds_per_day
            tickets_list = [
                {"issue_key": k, "seconds": v, "formatted": format_duration(v)}
                for k, v in summary.by_issue.items()
                if v > 0
            ]
            rows.append({
                "date": d_str,
                "weekday": day_of_week,
                "is_weekend": is_weekend,
                "total_seconds": t_sec,
                "total_formatted": format_duration(t_sec),
                "target_seconds": 0 if is_weekend else target_seconds_per_day,
                "target_formatted": "0h" if is_weekend else f"{profile.target_hours:.1f}h",
                "is_logged": summary.is_logged,
                "status_label": "Enviado" if summary.is_logged else "Pendente",
                "tickets": tickets_list,
            })
        else:
            if not is_weekend:
                total_target_seconds += target_seconds_per_day
            rows.append({
                "date": d_str,
                "weekday": day_of_week,
                "is_weekend": is_weekend,
                "total_seconds": 0,
                "total_formatted": "-" if is_weekend else "0s",
                "target_seconds": 0 if is_weekend else target_seconds_per_day,
                "target_formatted": "0h" if is_weekend else f"{profile.target_hours:.1f}h",
                "is_logged": False,
                "status_label": "Fim de Semana" if is_weekend else "-",
                "tickets": [],
            })
        curr += timedelta(days=1)

    rows.reverse()
    diff_seconds = total_period_seconds - total_target_seconds
    diff_sign = "+" if diff_seconds >= 0 else "-"

    return {
        "days": days,
        "rows": rows,
        "total_period_seconds": total_period_seconds,
        "total_period_formatted": format_duration(total_period_seconds),
        "total_target_seconds": total_target_seconds,
        "total_target_formatted": format_duration(total_target_seconds),
        "balance_seconds": diff_seconds,
        "balance_positive": diff_seconds >= 0,
        "balance_formatted": f"{diff_sign}{format_duration(abs(diff_seconds))}",
        "raw_report": generate_report(days=days),
    }


HTML_PAGE = r"""<!DOCTYPE html>
<html lang="pt-BR" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="theme-color" content="#0a0907">
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<link rel="shortcut icon" href="/favicon.svg">
<title>JiraBot Web - Painel de Controle, Lote e Lançamentos</title>
<style>
/*__THEME_CSS__*/
</style>
<script>
/*__EARLY_JS__*/
</script>
</head>
<body>

<canvas id="fx-canvas" aria-hidden="true"></canvas>
<div class="fx-spot" aria-hidden="true"></div>
<div id="sidebar-backdrop" onclick="closeMobileSidebar()"></div>

<!-- Sidebar -->
<aside class="sidebar" id="app-sidebar">
  <div class="brand">
    <div class="brand-logo">__LOGO_SVG__</div>
    <div class="brand-text">
      <h1>JiraBot</h1>
      <span id="sidebar-version-label">Gerenciador de Horas v2.2.0</span>
    </div>
  </div>

  <nav class="nav-menu">
    <button class="nav-btn active" data-tab="tab-dashboard" title="Painel do Dia e Horários" onclick="switchTab('tab-dashboard', this)">
      <svg viewBox="0 0 24 24" fill="none" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
      <span class="nav-label">Painel do Dia e Horários</span>
    </button>
    <button class="nav-btn" data-tab="tab-analytics" title="Dashboard Analítico" onclick="switchTab('tab-analytics', this)">
      <svg viewBox="0 0 24 24" fill="none" stroke-width="2"><polyline points="3 17 9 11 13 15 21 7"/><polyline points="14 7 21 7 21 14"/></svg>
      <span class="nav-label">Dashboard Analítico</span>
    </button>
    <button class="nav-btn" data-tab="tab-weekly" title="Visualização Semanal" onclick="switchTab('tab-weekly', this)">
      <svg viewBox="0 0 24 24" fill="none" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
      <span class="nav-label">Visualização Semanal</span>
    </button>
    <button class="nav-btn" data-tab="tab-worklogs" title="Lançamentos do Jira" onclick="switchTab('tab-worklogs', this)">
      <svg viewBox="0 0 24 24" fill="none" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
      <span class="nav-label">Lançamentos do Jira</span>
    </button>
    <button class="nav-btn" data-tab="tab-batch" title="Lançamentos em Lote" onclick="switchTab('tab-batch', this)">
      <svg viewBox="0 0 24 24" fill="none" stroke-width="2"><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></svg>
      <span class="nav-label">Lançamentos em Lote</span>
    </button>
    <button class="nav-btn" data-tab="tab-profiles" title="Perfis de Turno e Janelas" onclick="switchTab('tab-profiles', this)">
      <svg viewBox="0 0 24 24" fill="none" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
      <span class="nav-label">Perfis de Turno e Janelas</span>
    </button>
    <button class="nav-btn" data-tab="tab-alerts" title="Avisos e Notificações" onclick="switchTab('tab-alerts', this)">
      <svg viewBox="0 0 24 24" fill="none" stroke-width="2"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
      <span class="nav-label">Avisos e Notificações</span>
    </button>
    <button class="nav-btn" data-tab="tab-reports" title="Relatórios e Banco de Horas" onclick="switchTab('tab-reports', this)">
      <svg viewBox="0 0 24 24" fill="none" stroke-width="2"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
      <span class="nav-label">Relatórios e Banco de Horas</span>
    </button>
  </nav>

  <div class="nav-bottom">
  <button class="nav-btn" data-tab="tab-settings" title="Configurações e Atualização" onclick="switchTab('tab-settings', this)">
    <svg viewBox="0 0 24 24" fill="none" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
    <span class="nav-label">Configurações e Atualização</span>
  </button>
  </div>

  <div class="sidebar-footer">
    <div class="daemon-pill">
      <span id="sidebar-dot" class="dot"></span>
      <span id="sidebar-daemon-text" class="footer-text">Verificando serviço...</span>
    </div>
    <div id="sidebar-profile-text" class="footer-text">Perfil: -</div>
  </div>
</aside>

<!-- Main Wrapper -->
<div class="main-wrapper">
  <header class="topbar">
    <div class="topbar-left">
      <button class="hamburger is-open" id="hamburger-btn" onclick="toggleSidebar()" aria-label="Recolher ou expandir o menu lateral" aria-expanded="true" title="Recolher ou expandir o menu lateral">
        <span class="hb-bar"></span><span class="hb-bar"></span><span class="hb-bar"></span>
      </button>
      <div class="topbar-title" id="page-title">Painel do Dia e Controle de Expediente</div>
      <span id="top-status-badge" class="badge badge-idle">CARREGANDO</span>
    </div>
    <div class="topbar-right">
      <button class="btn btn-outline btn-sm fx-btn" id="fx-toggle-btn" onclick="toggleFx()" aria-pressed="false" title="Pausar animações e efeitos visuais">
        <svg class="fx-ico-pause" viewBox="0 0 24 24" fill="none" stroke-width="2"><line x1="8" y1="5" x2="8" y2="19"/><line x1="16" y1="5" x2="16" y2="19"/></svg>
        <svg class="fx-ico-play" viewBox="0 0 24 24" fill="none" stroke-width="2"><polygon points="7 4 20 12 7 20 7 4"/></svg>
        <span id="fx-toggle-label">Pausar Efeitos</span>
      </button>
      <button class="btn btn-outline btn-sm" id="theme-toggle-btn" onclick="toggleTheme()">
        <svg viewBox="0 0 24 24" fill="none" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
        <span id="theme-toggle-label">Modo Claro</span>
      </button>
      <button class="btn btn-outline btn-sm" onclick="refreshAll()">Atualizar Dados</button>
      <button class="btn btn-outline btn-sm" onclick="switchTab('tab-batch')">Lançar em Lote</button>
      <button class="btn btn-primary btn-sm" onclick="openWorklogModal()">+ Novo Lançamento no Jira</button>
    </div>
  </header>

  <main class="content">

    <!-- ==================== TAB 1: DASHBOARD & EXPEDIENTE DE HOJE ==================== -->
    <section id="tab-dashboard" class="tab-pane active">
      <div class="grid-4">
        <div class="stat-card">
          <div class="stat-label">Tempo Acumulado Hoje</div>
          <div class="stat-value" id="stat-today-time">0s</div>
          <div class="progress-bar-wrap">
            <div class="progress-bar-fill" id="stat-progress-bar" style="width: 0%"></div>
          </div>
          <div class="stat-sub" id="stat-today-meta">Meta: 6.0h (0%)</div>
        </div>

        <div class="stat-card">
          <div class="stat-label">Ticket Ativo Atual</div>
          <div class="stat-value" id="stat-active-ticket">-</div>
          <div class="stat-sub" id="stat-active-desc">Sem descrição definida</div>
        </div>

        <div class="stat-card">
          <div class="stat-label">Serviço em Background</div>
          <div class="stat-value" id="stat-daemon-state">Parado</div>
          <div class="stat-sub" id="stat-last-event">Último evento: -</div>
        </div>

        <div class="stat-card">
          <div class="stat-label">Sincronização Jira Hoje</div>
          <div class="stat-value" id="stat-logged-state">Pendente</div>
          <div class="stat-sub" id="stat-queue-count">Fila offline: 0 item(ns)</div>
        </div>
      </div>

      <!-- Controles do Servico e Cronometro -->
      <div class="card">
        <div class="card-header">
          <div class="card-title">Controles Rápidos do Serviço e Cronômetro</div>
          <div class="btn-group">
            <button class="btn btn-success btn-sm" onclick="serviceAction('start_daemon')">Iniciar Serviço (Tray)</button>
            <button class="btn btn-danger btn-sm" onclick="serviceAction('stop_daemon')">Parar Serviço</button>
            <button class="btn btn-outline btn-sm" onclick="serviceAction('restart_daemon')">Reiniciar Serviço</button>
          </div>
        </div>
        <div class="btn-group">
          <button class="btn btn-primary" onclick="serviceAction('manual_start')">Iniciar / Retomar Contagem</button>
          <button class="btn btn-warning" onclick="serviceAction('manual_pause')">Pausar Contagem</button>
          <button class="btn btn-outline" onclick="serviceAction('simulate_unlock')">Simular Desbloqueio (Unlock)</button>
          <button class="btn btn-outline" onclick="serviceAction('simulate_lock')">Simular Bloqueio (Lock)</button>
          <button class="btn btn-outline" onclick="serviceAction('test_popup')">Abrir Janela de Revisão Pré-Saída</button>
          <button class="btn btn-success" onclick="openLogNowModal()">Lançar Horas de Hoje no Jira Agora</button>
        </div>
      </div>

      <!-- Grade Visual de Horarios de Hoje: Inicio, Pausa de Almoco, Retorno e Encerramento -->
      <div class="card">
        <div class="card-header">
          <div class="card-title">Horários do Expediente de Hoje (Início, Pausa de Almoço, Retorno e Encerramento)</div>
          <span style="font-size: 12px; color: var(--text-muted);">Edite os horários abaixo para recalcular automaticamente o expediente de hoje</span>
        </div>

        <div class="schedule-box">
          <div class="schedule-grid">
            <div class="form-group" style="margin-bottom:0">
              <label>1. Horário de Início (Entrada)</label>
              <input type="time" id="today-start-hm" class="form-control" oninput="previewTodaySchedule()">
            </div>
            <div class="form-group" style="margin-bottom:0">
              <label>2. Pausa de Almoço (Saída)</label>
              <input type="time" id="today-lunch-start-hm" class="form-control" oninput="previewTodaySchedule()">
            </div>
            <div class="form-group" style="margin-bottom:0">
              <label>3. Retorno do Almoço</label>
              <input type="time" id="today-lunch-end-hm" class="form-control" oninput="previewTodaySchedule()">
            </div>
            <div class="form-group" style="margin-bottom:0">
              <label>4. Horário de Encerramento (Saída)</label>
              <input type="time" id="today-end-hm" class="form-control" oninput="previewTodaySchedule()">
            </div>
          </div>

          <div class="schedule-summary-bar">
            <div id="today-schedule-calc-text">
              Preencha os horários para visualizar o cálculo líquido de manhã, almoço e tarde.
            </div>
            <div class="btn-group">
              <button class="btn btn-outline btn-sm" onclick="fillTodayDefaultSchedule()">Preencher Padrão do Perfil</button>
              <button class="btn btn-primary btn-sm" onclick="saveTodaySchedule()">Aplicar Horários ao Dia de Hoje</button>
            </div>
          </div>
        </div>
      </div>

      <div class="grid-2">
        <!-- Troca de Ticket Ativo e Edicao de Descricao -->
        <div class="card" style="margin-bottom:0">
          <div class="card-header">
            <div class="card-title">Trocar Ticket Ativo e Definir Descrição</div>
          </div>
          <div class="form-group">
            <label>Chave do Ticket Ativo (ex: CONSISABI-427, ATIVDIV-32)</label>
            <input type="text" id="switch-issue-input" class="form-control" placeholder="Ex: CONSISABI-427">
          </div>
          <div class="form-group">
            <label>Descrição da Atividade Realizada no Ticket</label>
            <textarea id="switch-comment-input" class="form-control" placeholder="Descreva as atividades executadas neste ticket..."></textarea>
          </div>
          <div class="form-group" style="flex-direction: row; align-items: center; gap: 8px;">
            <input type="checkbox" id="today-no-comment-chk" onchange="toggleTodayNoComment(this.checked)">
            <label for="today-no-comment-chk" style="margin:0; cursor:pointer;">Configurar expediente de hoje para enviar SEM NENHUMA DESCRIÇÃO</label>
          </div>
          <div class="btn-group">
            <button class="btn btn-primary" onclick="submitSwitchOrComment('switch')">Trocar Ticket Ativo</button>
            <button class="btn btn-outline" onclick="submitSwitchOrComment('set_comment')">Apenas Salvar Descrição</button>
          </div>
        </div>

        <!-- Transferencia / Remanejamento de Horas de Hoje -->
        <div class="card" style="margin-bottom:0">
          <div class="card-header">
            <div class="card-title">Transferir / Remanejar Horas entre Tickets (Hoje)</div>
          </div>
          <div class="form-grid">
            <div class="form-group">
              <label>Ticket de Origem (Hoje)</label>
              <input type="text" id="transfer-src-input" class="form-control" placeholder="Ex: ATIVDIV-32">
            </div>
            <div class="form-group">
              <label>Ticket de Destino</label>
              <input type="text" id="transfer-tgt-input" class="form-control" placeholder="Ex: CONSISABI-427">
            </div>
          </div>
          <div class="form-group">
            <label>Tempo a Transferir (vazio = transferir TUDO da origem, ou informe ex: 01:30, 45m)</label>
            <input type="text" id="transfer-time-input" class="form-control" placeholder="Deixe em branco para transferir todo o tempo">
          </div>
          <button class="btn btn-primary" onclick="submitTransferToday()">Transferir Horas de Hoje</button>

          <div style="margin-top: 18px; border-top: 1px solid var(--border-color); padding-top: 12px;">
            <div style="font-size: 12px; font-weight: 700; margin-bottom: 8px; color: var(--text-muted);">RESUMO POR TICKET TRABALHADO HOJE</div>
            <div id="today-tickets-list"></div>
          </div>
        </div>
      </div>

      <!-- Tabela de Intervalos Detalhados de Hoje -->
      <div class="card" style="margin-top: 20px;">
        <div class="card-header">
          <div class="card-title">Intervalos de Trabalho Registrados Hoje</div>
          <button class="btn btn-outline btn-sm" onclick="openIntervalModal(-1)">+ Adicionar Intervalo Manual</button>
        </div>
        <div class="table-responsive">
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Ticket</th>
                <th>Início</th>
                <th>Fim</th>
                <th>Duração</th>
                <th>Descrição do Intervalo</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody id="today-intervals-tbody">
              <tr><td colspan="7" style="text-align:center; color:var(--text-muted);">Nenhum intervalo registrado hoje.</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- ==================== TAB: DASHBOARD ANALITICO ==================== -->
    <section id="tab-analytics" class="tab-pane">
      <div class="card">
        <div class="card-header" style="margin-bottom:0; padding-bottom:0; border-bottom:none;">
          <div>
            <div class="card-title">Dashboard Analítico dos Seus Lançamentos</div>
            <div class="section-hint" id="an-subtitle">Indicadores calculados a partir dos worklogs reais que você lançou no Jira.</div>
          </div>
          <div class="an-controls">
            <div class="an-date-picker">
              <label for="an-start-date" class="an-date-label">De:</label>
              <input type="date" id="an-start-date" class="form-control an-date-input" title="Data inicial">
              <label for="an-end-date" class="an-date-label">Até:</label>
              <input type="date" id="an-end-date" class="form-control an-date-input" title="Data final">
              <button class="btn btn-primary btn-sm" onclick="applyCustomAnalyticsDates()" title="Filtrar pelo intervalo selecionado">Filtrar</button>
            </div>
            <div class="seg" role="group" aria-label="Atalhos de período">
              <button class="seg-btn" data-preset="today" onclick="setAnalyticsPreset('today')">Hoje</button>
              <button class="seg-btn" data-preset="yesterday" onclick="setAnalyticsPreset('yesterday')">Ontem</button>
              <button class="seg-btn" data-preset="this_month" onclick="setAnalyticsPreset('this_month')">Este Mês</button>
              <button class="seg-btn" data-preset="last_month" onclick="setAnalyticsPreset('last_month')">Mês Anterior</button>
              <button class="seg-btn active" data-preset="30d" onclick="setAnalyticsPreset('30d')">30 Dias</button>
              <button class="seg-btn" data-preset="90d" onclick="setAnalyticsPreset('90d')">90 Dias</button>
            </div>
            <button class="btn btn-outline btn-sm" onclick="loadAnalytics(true)" title="Forçar atualização dos dados diretamente do Jira">Atualizar do Jira</button>
          </div>
        </div>
      </div>

      <div id="an-state"></div>

      <div id="an-content" style="display:none;">
        <div class="grid-kpi">
          <div class="stat-card">
            <div class="stat-label">Horas Lançadas no Período</div>
            <div class="stat-value" id="an-kpi-hours">-</div>
            <div class="stat-sub" id="an-kpi-hours-sub"></div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Tickets Trabalhados</div>
            <div class="stat-value" id="an-kpi-tickets">-</div>
            <div class="stat-sub" id="an-kpi-tickets-sub"></div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Finalizados por Mim no Jira</div>
            <div class="stat-value" id="an-kpi-done">-</div>
            <div class="stat-sub" id="an-kpi-done-sub"></div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Média de Finalizados por Semana</div>
            <div class="stat-value" id="an-kpi-done-avg">-</div>
            <div class="stat-sub" id="an-kpi-done-avg-sub"></div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Tempo Médio por Ticket</div>
            <div class="stat-value" id="an-kpi-avg">-</div>
            <div class="stat-sub" id="an-kpi-avg-sub"></div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Tempo Médio por Ticket Finalizado</div>
            <div class="stat-value" id="an-kpi-avg-done">-</div>
            <div class="stat-sub" id="an-kpi-avg-done-sub"></div>
          </div>
        </div>

        <div class="grid-2">
          <div class="card" style="margin-bottom:0;">
            <div class="card-header"><div class="card-title">Tipos de Ticket com Mais Tempo</div></div>
            <div id="an-bars-time"></div>
          </div>
          <div class="card" style="margin-bottom:0;">
            <div class="card-header"><div class="card-title">Tipos de Ticket com Mais Lançamentos</div></div>
            <div id="an-bars-count"></div>
          </div>
        </div>

        <div class="grid-2">
          <div class="card" style="margin-bottom:0;">
            <div class="card-header"><div class="card-title">Lançamentos Com x Sem Descrição</div></div>
            <div id="an-desc"></div>
          </div>
          <div class="card" style="margin-bottom:0;">
            <div class="card-header"><div class="card-title">Tickets com Mais Tempo no Período</div></div>
            <div id="an-top"></div>
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <div class="card-title">Evolução dos Tickets ao Longo do Período</div>
          </div>
          <div class="chart-controls">
            <div class="chips" id="an-chips"></div>
            <div class="seg" role="group" aria-label="Granularidade do gráfico">
              <button class="seg-btn" data-gran="day" onclick="setAnalyticsGranularity('day')">Diário</button>
              <button class="seg-btn" data-gran="week" onclick="setAnalyticsGranularity('week')">Semanal</button>
            </div>
          </div>
          <div id="an-chart"></div>
        </div>
      </div>
    </section>

    <!-- ==================== TAB 2: VISUALIZACAO SEMANAL ==================== -->
    <section id="tab-weekly" class="tab-pane">
      <div class="card">
        <div class="card-header">
          <div class="card-title">Visualização Semanal (Semana Atual ou Escolhida)</div>
          <div class="btn-group">
            <button class="btn btn-outline btn-sm" onclick="navigateWeek(-1)">&lt; Semana Anterior</button>
            <button class="btn btn-primary btn-sm" onclick="navigateWeek(0)">Semana Atual (Hoje)</button>
            <button class="btn btn-outline btn-sm" onclick="navigateWeek(1)">Próxima Semana &gt;</button>
          </div>
        </div>

        <div class="schedule-box" style="display:flex; align-items:flex-end; justify-content:space-between; flex-wrap:wrap; gap:16px; margin-bottom:18px; padding:14px 16px;">
          <div style="display:flex; align-items:flex-end; flex-wrap:wrap; gap:20px;">
            <div class="form-group" style="margin-bottom:0;">
              <label>Escolher Data no Calendário (Exibe de Segunda a Domingo)</label>
              <input type="date" id="weekly-ref-date" class="form-control" style="width:210px;" onchange="loadWeeklyView(this.value)">
            </div>
            <div class="form-group" style="margin-bottom:0; flex-direction:row; align-items:center; gap:8px; height:36px;">
              <input type="checkbox" id="weekly-fetch-jira-chk" checked onchange="loadWeeklyView(document.getElementById('weekly-ref-date').value)">
              <label for="weekly-fetch-jira-chk" style="margin:0; cursor:pointer; font-size:13px;">Sincronizar com worklogs reais lançados no Jira nesta semana</label>
            </div>
          </div>
          <div class="btn-group" style="justify-content:flex-end;">
            <button class="btn btn-success" onclick="openBatchForCurrentWeek()">Lançar Dias Faltantes Desta Semana em Lote</button>
          </div>
        </div>

        <div class="grid-4">
          <div class="stat-card">
            <div class="stat-label">Semana Selecionada</div>
            <div class="stat-value" id="wk-range-label" style="font-size:17px;">-</div>
            <div class="stat-sub" id="wk-days-logged-sub">Dias úteis lançados: 0 / 5</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Total Trabalhado na Semana</div>
            <div class="stat-value" id="wk-total-worked">-</div>
            <div class="stat-sub" id="wk-full-target-sub">Meta semanal (5 dias): -</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Meta Esperada até Hoje</div>
            <div class="stat-value" id="wk-target-today">-</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Saldo da Semana</div>
            <div class="stat-value" id="wk-balance">-</div>
          </div>
        </div>

        <div class="table-responsive">
          <table>
            <thead>
              <tr>
                <th style="width:92px;">Dia</th>
                <th style="width:96px;">Data</th>
                <th style="width:74px; text-align:center;">Início</th>
                <th style="width:98px; text-align:center;">Pausa Almoço</th>
                <th style="width:74px; text-align:center;">Retorno</th>
                <th style="width:98px; text-align:center;">Encerramento</th>
                <th>Tickets e Descrições</th>
                <th style="width:98px;">Total do Dia</th>
                <th style="width:62px;">Meta</th>
                <th style="width:136px; text-align:center;">Status</th>
                <th style="width:190px; text-align:right;">Ações Rápidas</th>
              </tr>
            </thead>
            <tbody id="weekly-table-tbody">
              <tr><td colspan="11" style="text-align:center; padding:24px; color:var(--text-muted);">Carregando visualização semanal...</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- ==================== TAB 3: LANCAMENTOS DO JIRA (WORKLOGS) ==================== -->
    <section id="tab-worklogs" class="tab-pane">
      <div class="card">
        <div class="card-header">
          <div class="card-title">Gerenciador de Todos os Lançamentos do Jira (Worklogs)</div>
          <div class="btn-group">
            <button class="btn btn-outline" onclick="switchTab('tab-batch')">Lançamento Multi-Dias / Semanas em Lote</button>
            <button class="btn btn-primary" onclick="openWorklogModal()">+ Lançar Novo Worklog no Jira</button>
          </div>
        </div>

        <div class="form-grid" style="align-items: end;">
          <div class="form-group" style="margin-bottom:0">
            <label>Período Retroativo (Dias)</label>
            <select id="wl-filter-days" class="form-control" onchange="loadJiraWorklogs()">
              <option value="7">Últimos 7 dias (Semanal)</option>
              <option value="14" selected>Últimos 14 dias (Quinzena)</option>
              <option value="30">Últimos 30 dias (Mensal)</option>
              <option value="60">Últimos 60 dias</option>
              <option value="90">Últimos 90 dias</option>
            </select>
          </div>
          <div class="form-group" style="margin-bottom:0">
            <label>Filtrar por Ticket Específico no Jira (Opcional)</label>
            <input type="text" id="wl-filter-issue" class="form-control" placeholder="Ex: CONSISABI-427 (vazio = todos meus lançamentos)">
          </div>
          <div class="form-group" style="margin-bottom:0">
            <label>Busca Rápida na Tabela (Ticket, Data ou Descrição)</label>
            <input type="text" id="wl-search-text" class="form-control" placeholder="Filtrar resultados exibidos..." oninput="renderWorklogsTable()">
          </div>
          <div class="btn-group">
            <button class="btn btn-primary" onclick="loadJiraWorklogs()">Consultar no Jira</button>
            <button class="btn btn-outline" onclick="document.getElementById('wl-filter-issue').value=''; loadJiraWorklogs();">Limpar Filtro</button>
          </div>
        </div>
      </div>

      <!-- Fila Offline Pendente (se houver) -->
      <div class="card" id="offline-queue-card" style="display:none;">
        <div class="card-header">
          <div class="card-title">Fila Offline Pendente de Sincronização com o Jira</div>
          <button class="btn btn-success btn-sm" onclick="serviceAction('flush_queue')">Sincronizar Fila Agora</button>
        </div>
        <div class="table-responsive">
          <table>
            <thead>
              <tr>
                <th>Data</th>
                <th>Ticket</th>
                <th>Tempo</th>
                <th>Descrição</th>
                <th>Tentativas / Erro</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody id="offline-queue-tbody"></tbody>
          </table>
        </div>
      </div>

      <!-- Barra de Acoes em Lote (Multi-selecao) -->
      <div class="bulk-bar" id="wl-bulk-bar">
        <div>
          <strong id="wl-selected-count">0</strong> lançamento(s) selecionado(s) na tabela
        </div>
        <div class="btn-group">
          <button class="btn btn-primary btn-sm" onclick="openBulkEditModal()">Editar / Migrar Ticket / Horários em Lote</button>
          <button class="btn btn-danger btn-sm" onclick="deleteSelectedWorklogsBulk()">Excluir Selecionados em Lote</button>
          <button class="btn btn-outline btn-sm" onclick="clearWorklogSelection()">Desmarcar Todos</button>
        </div>
      </div>

      <!-- Tabela Principal de Lancamentos do Jira -->
      <div class="card">
        <div class="card-header">
          <div class="card-title">Lançamentos Encontrados no Jira (<span id="wl-count-label">0</span>)</div>
          <span style="font-size:12px; color:var(--text-muted);">Marque vários lançamentos para editar/excluir em lote, ou clique em Editar na linha desejada</span>
        </div>
        <div class="table-responsive">
          <table>
            <thead>
              <tr>
                <th style="width:36px;"><input type="checkbox" id="wl-select-all-chk" onchange="toggleSelectAllWorklogs(this.checked)"></th>
                <th>Data</th>
                <th>Ticket</th>
                <th>Início</th>
                <th>Pausa Almoço</th>
                <th>Retorno</th>
                <th>Encerramento</th>
                <th>Total Lançado</th>
                <th>Descrição / Comentário</th>
                <th style="text-align:right;">Ações</th>
              </tr>
            </thead>
            <tbody id="jira-worklogs-tbody">
              <tr><td colspan="10" style="text-align:center; padding: 24px; color:var(--text-muted);">Clique em "Consultar no Jira" ou aguarde o carregamento dos lançamentos...</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- ==================== TAB 4: LANCAMENTOS EM LOTE (MULTI-DIAS / SEMANAS / MULTI-TICKETS) ==================== -->
    <section id="tab-batch" class="tab-pane">
      <div class="card">
        <div class="card-header">
          <div class="card-title">Gerador de Lançamentos em Lote (Múltiplos Dias, Semanas e Múltiplos Tickets)</div>
          <div class="btn-group" style="align-items:center;">
            <span style="font-size:11.5px; color:var(--text-muted); margin-right:4px;">Atalhos Opcionais:</span>
            <button class="btn btn-outline btn-sm" onclick="setBatchPreset('this_week')">Esta Semana</button>
            <button class="btn btn-outline btn-sm" onclick="setBatchPreset('last_week')">Semana Passada</button>
            <button class="btn btn-outline btn-sm" onclick="setBatchPreset('2_weeks')">Últimas 2 Semanas</button>
            <button class="btn btn-outline btn-sm" onclick="setBatchPreset('3_weeks')">Últimas 3 Semanas</button>
            <button class="btn btn-outline btn-sm" onclick="setBatchPreset('month')">Últimos 30 Dias</button>
          </div>
        </div>

        <p style="font-size:13px; color:var(--text-muted); margin-bottom:16px;">
          Escolha livremente a <strong>Data Inicial</strong> e a <strong>Data Final</strong> do período que deseja lançar, marque os dias da semana desejados (por padrão Segunda a Sexta, pulando Sábado e Domingo) e selecione abaixo como os tickets devem ser distribuídos.
        </p>

        <div class="form-grid">
          <div class="form-group">
            <label>Data Inicial do Período (Escolha Livre)</label>
            <input type="date" id="batch-start-date" class="form-control" oninput="onBatchPeriodOrWeekdayChange()" onchange="onBatchPeriodOrWeekdayChange()">
          </div>
          <div class="form-group">
            <label>Data Final do Período (Escolha Livre)</label>
            <input type="date" id="batch-end-date" class="form-control" oninput="onBatchPeriodOrWeekdayChange()" onchange="onBatchPeriodOrWeekdayChange()">
          </div>
          <div class="form-group" style="grid-column: span 2;">
            <label>Como Deseja Lançar os Tickets neste Período?</label>
            <select id="batch-multi-mode" class="form-control" onchange="onBatchMultiModeChange()">
              <option value="one_per_day">1 Ticket por Dia (Em Ordem Cronológica: 1 linha para cada dia habilitado do período, limitado ao total de dias)</option>
              <option value="split_day">Dividir o Mesmo Dia entre Vários Tickets (Lançar 2 ou mais tickets dentro do mesmo dia e repetir esse padrão em todos os dias)</option>
            </select>
          </div>
        </div>

        <!-- Quadro Explicativo Detalhado do Modo Selecionado -->
        <div id="batch-mode-explanation-box" class="schedule-box" style="margin-bottom:14px; border-left: 4px solid var(--primary); padding: 12px 16px;">
        </div>

        <div class="schedule-box">
          <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:10px;">
            <div style="font-weight:700; font-size:13px;">Expediente Base de Referência do Dia</div>
            <div class="btn-group">
              <button class="btn btn-outline btn-sm" onclick="setBatchBaseProfile('6h')">Padrão 6h (07:45 - 15:15)</button>
              <button class="btn btn-outline btn-sm" onclick="setBatchBaseProfile('8h')">Padrão 8h (07:42 - 17:42)</button>
            </div>
          </div>
          <div class="schedule-grid">
            <div class="form-group" style="margin-bottom:0">
              <label>Horário de Início</label>
              <input type="time" id="batch-start-hm" class="form-control" value="07:45" oninput="previewBatchBaseSchedule()">
            </div>
            <div class="form-group" style="margin-bottom:0">
              <label>Pausa de Almoço</label>
              <input type="time" id="batch-ls-hm" class="form-control" value="12:00" oninput="previewBatchBaseSchedule()">
            </div>
            <div class="form-group" style="margin-bottom:0">
              <label>Retorno do Almoço</label>
              <input type="time" id="batch-le-hm" class="form-control" value="13:30" oninput="previewBatchBaseSchedule()">
            </div>
            <div class="form-group" style="margin-bottom:0">
              <label>Horário de Encerramento</label>
              <input type="time" id="batch-end-hm" class="form-control" value="15:15" oninput="previewBatchBaseSchedule()">
            </div>
          </div>

          <div class="schedule-summary-bar">
            <div style="display:flex; flex-direction:column; gap:6px;">
              <div>
                <strong>Dias da Semana Habilitados para Lançamento:</strong>
                <div class="weekday-checks">
                  <label><input type="checkbox" class="batch-wd-chk" value="0" checked onchange="onBatchPeriodOrWeekdayChange()"> Seg</label>
                  <label><input type="checkbox" class="batch-wd-chk" value="1" checked onchange="onBatchPeriodOrWeekdayChange()"> Ter</label>
                  <label><input type="checkbox" class="batch-wd-chk" value="2" checked onchange="onBatchPeriodOrWeekdayChange()"> Qua</label>
                  <label><input type="checkbox" class="batch-wd-chk" value="3" checked onchange="onBatchPeriodOrWeekdayChange()"> Qui</label>
                  <label><input type="checkbox" class="batch-wd-chk" value="4" checked onchange="onBatchPeriodOrWeekdayChange()"> Sex</label>
                  <label><input type="checkbox" class="batch-wd-chk" value="5" onchange="onBatchPeriodOrWeekdayChange()"> Sáb</label>
                  <label><input type="checkbox" class="batch-wd-chk" value="6" onchange="onBatchPeriodOrWeekdayChange()"> Dom</label>
                </div>
              </div>
              <div id="batch-period-days-info" style="font-size:12.5px; color:var(--primary-text); font-weight:600;"></div>
            </div>
            <div id="batch-base-calc-text" style="font-weight:600;">Tempo Líquido Base: 06:00</div>
          </div>
        </div>

        <!-- Lista Dinamica de Tickets do Lote -->
        <div class="schedule-box" style="margin-top:14px;">
          <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; margin-bottom:12px;">
            <div>
              <div style="font-weight:700; font-size:13.5px;" id="batch-tickets-section-title">Tickets Configurados para o Lote (<span id="batch-tickets-count-lbl">1</span>)</div>
              <div style="font-size:12px; color:var(--text-muted);" id="batch-tickets-section-subtitle"></div>
            </div>
            <div class="btn-group">
              <button class="btn btn-primary btn-sm" id="batch-add-ticket-btn" onclick="addBatchTemplateTicket()">+ Adicionar Ticket</button>
              <button class="btn btn-outline btn-sm" id="batch-copy-first-btn" onclick="copyFirstTicketToAllBatchTemplates()" title="Copia o código e a descrição do Ticket #1 para todas as linhas abaixo">Repetir Ticket #1 em Todos</button>
              <button class="btn btn-outline btn-sm" id="batch-split-eq-btn" onclick="autoSplitBatchTicketsEqual()" title="Divide o tempo líquido do dia igualmente entre todos os tickets listados">Dividir Horas Iguais no Dia</button>
              <button class="btn btn-outline btn-sm" id="batch-split-ma-btn" onclick="autoSplitBatchTicketsMorningAfternoon()" title="1º ticket de manhã (até o almoço) e demais tickets à tarde">Dividir Manhã / Tarde</button>
              <button class="btn btn-outline btn-sm" onclick="syncBatchTicketsWithBaseSchedule()" title="Copia o expediente base completo para todos os tickets">Aplicar Horário Base em Todos</button>
            </div>
          </div>

          <div class="table-responsive">
            <table>
              <thead>
                <tr>
                  <th style="min-width:155px;" id="batch-tpl-col-order-hdr">Ordem / Dia Correspondente</th>
                  <th>Ticket (Ex: CONSISABI-427)</th>
                  <th>Início</th>
                  <th>Pausa Almoço</th>
                  <th>Retorno</th>
                  <th>Encerramento</th>
                  <th>Líquido</th>
                  <th>Descrição / Comentário deste Ticket</th>
                  <th style="text-align:right;">Ação</th>
                </tr>
              </thead>
              <tbody id="batch-template-tickets-tbody"></tbody>
            </table>
          </div>
        </div>

        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; margin-top:14px;">
          <div style="display:flex; flex-direction:column; gap:6px;">
            <label style="font-size:13px; display:flex; align-items:center; gap:8px; cursor:pointer;">
              <input type="checkbox" id="batch-skip-existing-chk" checked>
              Consultar o Jira e desmarcar automaticamente os dias que já possuem lançamento registrado
            </label>
            <label style="font-size:13px; display:flex; align-items:center; gap:8px; cursor:pointer;">
              <input type="checkbox" id="batch-no-comment-chk">
              Enviar lançamentos deste lote SEM nenhuma descrição
            </label>
          </div>
          <div class="btn-group">
            <button class="btn btn-primary" onclick="generateBatchPreview()">1. Validar no Jira e Gerar Pré-Visualização de Envio</button>
          </div>
        </div>
      </div>

      <!-- Grade Editavel de Pre-Visualizacao do Lote -->
      <div class="card" id="batch-preview-card" style="display:none;">
        <div class="card-header">
          <div class="card-title">Revisão Dia a Dia do Lote (<span id="batch-selected-summary">0 selecionados</span>)</div>
          <div class="btn-group">
            <button class="btn btn-outline btn-sm" onclick="toggleAllBatchRows(true)">Marcar Todos</button>
            <button class="btn btn-outline btn-sm" onclick="toggleAllBatchRows(false)">Desmarcar Todos</button>
            <button class="btn btn-success" id="batch-submit-btn" onclick="submitBatchWorklogs()">2. Lançar Todos os Selecionados no Jira Agora</button>
          </div>
        </div>

        <!-- Barra de Aplicacao Rapida de Ticket / Descricao nas Linhas Marcadas -->
        <div class="schedule-box" style="margin-bottom:14px; padding:10px 14px;">
          <div style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:10px;">
            <div style="font-size:12.5px; font-weight:600; color:var(--text-muted);">
              Alterar Rápido nas Linhas Marcadas Abaixo:
            </div>
            <div style="display:flex; align-items:center; flex-wrap:wrap; gap:8px; flex:1; justify-content:flex-end;">
              <input type="text" id="batch-quick-issue" class="form-control" style="width:160px; padding:6px 10px;" placeholder="Novo Ticket (ex: PROJ-10)">
              <input type="text" id="batch-quick-comment" class="form-control" style="width:240px; padding:6px 10px;" placeholder="Nova Descrição (opcional)">
              <button class="btn btn-outline btn-sm" onclick="applyQuickFillToBatchRows()">Aplicar nas Linhas Marcadas</button>
            </div>
          </div>
        </div>

        <div class="table-responsive">
          <table>
            <thead>
              <tr>
                <th style="width:36px;">Incluir</th>
                <th>Data</th>
                <th>Dia</th>
                <th>Status Atual no Jira</th>
                <th>Ticket</th>
                <th>Início</th>
                <th>Almoço</th>
                <th>Retorno</th>
                <th>Encerramento</th>
                <th>Líquido</th>
                <th>Descrição</th>
                <th style="text-align:right;">Ações no Dia</th>
              </tr>
            </thead>
            <tbody id="batch-preview-tbody"></tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- ==================== TAB 5: PERFIS DE TURNO E JANELAS ==================== -->
    <section id="tab-profiles" class="tab-pane">
      <div class="card">
        <div class="card-header">
          <div class="card-title">Seleção e Configuração Visual de Perfis de Turno</div>
          <button class="btn btn-primary" onclick="saveProfileSettings()">Salvar Perfil e Janelas</button>
        </div>

        <div class="form-grid" style="margin-bottom: 18px;">
          <div class="form-group">
            <label>Perfil de Turno Ativo</label>
            <select id="prof-active-select" class="form-control" onchange="onProfileSelectChange()">
              <option value="8h">Turno de 8h (8h)</option>
              <option value="6h_0745">Turno de 6h Cedo - 07:45 (6h_0745)</option>
              <option value="6h_0800">Turno de 6h Padrão - 08:00 (6h_0800)</option>
              <option value="custom">Turno Personalizado (custom)</option>
            </select>
          </div>
          <div class="form-group">
            <label>Meta Diária de Horas do Perfil</label>
            <input type="number" step="0.5" min="1" max="24" id="prof-target-hours" class="form-control">
          </div>
          <div class="form-group" style="grid-column: span 2;">
            <label>Descrição do Perfil</label>
            <input type="text" id="prof-description" class="form-control">
          </div>
        </div>

        <div class="grid-2">
          <div class="schedule-box" style="margin-bottom:0">
            <div style="font-weight:700; font-size:13px; margin-bottom:12px;">Janelas de Detecção Automática (Início e Fim de cada Janela)</div>
            <div class="form-grid">
              <div class="form-group">
                <label>Janela de Entrada (Início)</label>
                <input type="time" id="win-entry-start" class="form-control">
              </div>
              <div class="form-group">
                <label>Janela de Entrada (Fim)</label>
                <input type="time" id="win-entry-end" class="form-control">
              </div>

              <div class="form-group">
                <label>Janela Saída Almoço (Início)</label>
                <input type="time" id="win-ls-start" class="form-control">
              </div>
              <div class="form-group">
                <label>Janela Saída Almoço (Fim)</label>
                <input type="time" id="win-ls-end" class="form-control">
              </div>

              <div class="form-group">
                <label>Janela Retorno Almoço (Início)</label>
                <input type="time" id="win-le-start" class="form-control">
              </div>
              <div class="form-group">
                <label>Janela Retorno Almoço (Fim)</label>
                <input type="time" id="win-le-end" class="form-control">
              </div>

              <div class="form-group">
                <label>Janela de Encerramento (Início)</label>
                <input type="time" id="win-exit-start" class="form-control">
              </div>
              <div class="form-group">
                <label>Janela de Encerramento (Fim)</label>
                <input type="time" id="win-exit-end" class="form-control">
              </div>
            </div>
          </div>

          <div class="schedule-box" style="margin-bottom:0">
            <div style="font-weight:700; font-size:13px; margin-bottom:12px;">Calculadora de Janelas por Horário Base + Folgas (Minutos)</div>
            <div class="form-grid">
              <div class="form-group">
                <label>Entrada Alvo</label>
                <input type="time" id="calc-entry-hm" class="form-control" value="07:45" oninput="applyToleranceCalculator(true)">
              </div>
              <div class="form-group">
                <label>Folga Antes / Depois (min)</label>
                <div style="display:flex; gap:6px;">
                  <input type="number" id="calc-entry-bef" class="form-control" value="20" style="width:50%" oninput="applyToleranceCalculator(true)">
                  <input type="number" id="calc-entry-aft" class="form-control" value="20" style="width:50%" oninput="applyToleranceCalculator(true)">
                </div>
              </div>

              <div class="form-group">
                <label>Saída Almoço Alvo</label>
                <input type="time" id="calc-ls-hm" class="form-control" value="12:00" oninput="applyToleranceCalculator(true)">
              </div>
              <div class="form-group">
                <label>Folga Antes / Depois (min)</label>
                <div style="display:flex; gap:6px;">
                  <input type="number" id="calc-ls-bef" class="form-control" value="20" style="width:50%" oninput="applyToleranceCalculator(true)">
                  <input type="number" id="calc-ls-aft" class="form-control" value="20" style="width:50%" oninput="applyToleranceCalculator(true)">
                </div>
              </div>

              <div class="form-group">
                <label>Retorno Almoço Alvo</label>
                <input type="time" id="calc-le-hm" class="form-control" value="13:30" oninput="applyToleranceCalculator(true)">
              </div>
              <div class="form-group">
                <label>Folga Antes / Depois (min)</label>
                <div style="display:flex; gap:6px;">
                  <input type="number" id="calc-le-bef" class="form-control" value="10" style="width:50%" oninput="applyToleranceCalculator(true)">
                  <input type="number" id="calc-le-aft" class="form-control" value="10" style="width:50%" oninput="applyToleranceCalculator(true)">
                </div>
              </div>

              <div class="form-group">
                <label>Encerramento Alvo</label>
                <input type="time" id="calc-exit-hm" class="form-control" value="15:30" oninput="applyToleranceCalculator(true)">
              </div>
              <div class="form-group">
                <label>Folga Antes / Depois (min)</label>
                <div style="display:flex; gap:6px;">
                  <input type="number" id="calc-exit-bef" class="form-control" value="15" style="width:50%" oninput="applyToleranceCalculator(true)">
                  <input type="number" id="calc-exit-aft" class="form-control" value="30" style="width:50%" oninput="applyToleranceCalculator(true)">
                </div>
              </div>
            </div>
            <button class="btn btn-outline btn-sm" style="margin-top:8px;" onclick="applyToleranceCalculator(false)">Calcular e Preencher Janelas ao Lado</button>
          </div>
        </div>
      </div>
    </section>

    <!-- ==================== TAB 6: RELATORIOS E BANCO DE HORAS ==================== -->
    <section id="tab-reports" class="tab-pane">
      <div class="card">
        <div class="card-header">
          <div class="card-title">Relatório Consolidado e Saldo de Horas</div>
          <div class="btn-group">
            <button class="btn btn-outline btn-sm" onclick="loadReport(7)">Últimos 7 Dias</button>
            <button class="btn btn-outline btn-sm" onclick="loadReport(14)">Últimos 14 Dias</button>
            <button class="btn btn-outline btn-sm" onclick="loadReport(30)">Últimos 30 Dias</button>
            <button class="btn btn-outline btn-sm" onclick="loadReport(60)">Últimos 60 Dias</button>
          </div>
        </div>

        <div class="grid-4" style="margin-bottom: 16px;">
          <div class="stat-card">
            <div class="stat-label">Total Trabalhado no Período</div>
            <div class="stat-value" id="rep-total-worked">-</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Meta Esperada (Dias Úteis)</div>
            <div class="stat-value" id="rep-total-target">-</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Saldo do Banco de Horas</div>
            <div class="stat-value" id="rep-balance">-</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Período Analisado</div>
            <div class="stat-value" id="rep-days-count">7 dias</div>
          </div>
        </div>

        <div class="table-responsive" style="margin-bottom: 20px;">
          <table>
            <thead>
              <tr>
                <th>Data</th>
                <th>Dia</th>
                <th>Tickets e Horas Contabilizadas</th>
                <th>Total do Dia</th>
                <th>Meta</th>
                <th>Status Jira</th>
              </tr>
            </thead>
            <tbody id="rep-table-tbody"></tbody>
          </table>
        </div>

        <div style="font-size: 12px; font-weight: 700; color: var(--text-muted); margin-bottom: 6px;">VISUALIZAÇÃO EM FORMATO TERMINAL</div>
        <pre class="terminal-box" id="rep-raw-pre"></pre>
      </div>
    </section>

    <!-- ==================== TAB: AVISOS E NOTIFICACOES DE EXPEDIENTE ==================== -->
    <section id="tab-alerts" class="tab-pane">
      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title">Avisos e Notificações de Encerramento de Turno</div>
            <div class="section-hint">Configure a antecedência e o comportamento do alerta automático de fim de expediente.</div>
          </div>
          <div class="btn-group">
            <button class="btn btn-outline btn-sm" onclick="testExitAlert()">Testar Alerta Agora</button>
            <button class="btn btn-primary btn-sm" onclick="saveAlertConfig()">Salvar Configurações</button>
          </div>
        </div>

        <div class="grid-4" style="margin-bottom: 20px;">
          <div class="stat-card">
            <div class="stat-label">Perfil Ativo</div>
            <div class="stat-value" style="font-size: 18px;" id="alert-profile-name">-</div>
            <div class="stat-sub" id="alert-profile-desc">Turno configurado</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Horário Planejado de Saída</div>
            <div class="stat-value" id="alert-planned-exit">-</div>
            <div class="stat-sub" id="alert-planned-exit-sub">Base calculada do turno</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Disparo do Alerta Programado</div>
            <div class="stat-value" id="alert-trigger-time">-</div>
            <div class="stat-sub" id="alert-trigger-time-sub">Antecedência configurada</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Status do Alerta Hoje</div>
            <div class="stat-value" style="font-size: 16px;" id="alert-today-status">-</div>
            <div class="stat-sub" id="alert-today-status-sub">Disparo no expediente atual</div>
          </div>
        </div>

        <div class="schedule-box" style="margin-bottom: 20px;">
          <div class="card-title" style="margin-bottom: 14px;">Configuração do Tempo de Antecedência</div>

          <div class="form-group" style="margin-bottom: 16px;">
            <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; font-size: 13.5px; font-weight: 600;">
              <input type="checkbox" id="cfg-alert-enabled" onchange="onAlertEnabledChange()">
              Ativar aviso pré-encerramento do expediente
            </label>
            <span class="section-hint" style="margin-left: 24px;">Quando desativado, o JiraBot não emitirá som, notificação ou janela popup antes de encerrar o expediente.</span>
          </div>

          <div id="alert-settings-controls">
            <div class="form-group" style="margin-bottom: 18px;">
              <label for="cfg-alert-minutes" style="font-size: 11.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted); margin-bottom: 8px; display: block;">
                Minutos de Antecedência do Aviso (antes da saída):
              </label>
              <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
                <input type="number" id="cfg-alert-minutes" class="form-control" min="1" max="60" value="5" style="width: 100px;" oninput="onAlertMinutesInput()">
                <span style="font-size: 13px; color: var(--text-muted);">minutos antes da saída</span>
                <div class="seg" role="group" aria-label="Atalhos de minutos de aviso">
                  <button type="button" class="seg-btn" onclick="setAlertMinutesQuick(3)">3 min</button>
                  <button type="button" class="seg-btn" onclick="setAlertMinutesQuick(5)">5 min</button>
                  <button type="button" class="seg-btn" onclick="setAlertMinutesQuick(10)">10 min</button>
                  <button type="button" class="seg-btn" onclick="setAlertMinutesQuick(15)">15 min</button>
                  <button type="button" class="seg-btn" onclick="setAlertMinutesQuick(20)">20 min</button>
                  <button type="button" class="seg-btn" onclick="setAlertMinutesQuick(30)">30 min</button>
                </div>
              </div>
              <span class="section-hint" id="alert-calculation-hint" style="margin-top: 6px; display: block;"></span>
            </div>

            <div class="form-group" style="margin-bottom: 8px;">
              <label style="font-size: 11.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted); margin-bottom: 8px; display: block;">
                Modos de Exibição do Alerta:
              </label>
              <div style="display: flex; flex-direction: column; gap: 8px;">
                <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; font-size: 13px;">
                  <input type="checkbox" id="cfg-alert-popup">
                  Exibir janela interativa (Popup) em primeiro plano para revisar e editar as descrições dos tickets do dia
                </label>
                <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; font-size: 13px;">
                  <input type="checkbox" id="cfg-alert-toast">
                  Exibir notificação nativa do Windows (toast na bandeja do sistema)
                </label>
              </div>
            </div>
          </div>
        </div>

        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
          <button class="btn btn-outline" onclick="testExitAlert()">Testar Alerta na Minha Tela Agora</button>
          <button class="btn btn-primary" onclick="saveAlertConfig()">Salvar Configurações de Avisos</button>
        </div>
      </div>
    </section>

    <!-- ==================== TAB 7: CONFIGURACOES, ISOLAMENTO MULTI-USUARIO E ATUALIZACAO ==================== -->
    <section id="tab-settings" class="tab-pane">
      <!-- Card de Atualizacao em 1 Clique e Isolamento de Configuracoes Individuais -->
      <div class="card">
        <div class="card-header">
          <div class="card-title">Atualização do Aplicativo e Isolamento Multi-Usuário de Tokens</div>
          <div class="btn-group">
            <button class="btn btn-outline btn-sm" onclick="checkAppUpdate()">Verificar se há Atualização</button>
            <button class="btn btn-primary btn-sm" onclick="runAppUpdate()">Atualizar Aplicativo Agora (1 Clique)</button>
          </div>
        </div>

        <div class="schedule-box">
          <div class="form-grid">
            <div>
              <div style="font-size:12px; color:var(--text-muted);">VERSÃO INSTALADA</div>
              <div style="font-size:15px; font-weight:700;" id="upd-version-text">v2.2.0</div>
              <div style="font-size:11.5px; color:var(--text-muted); margin-top:2px;" id="upd-lastmod-text">-</div>
            </div>
            <div>
              <div style="font-size:12px; color:var(--text-muted);">USUÁRIO WINDOWS ATUAL</div>
              <div style="font-size:15px; font-weight:700;" id="upd-user-text">-</div>
              <div style="font-size:11.5px; color:var(--success); margin-top:2px;">Token e dados 100% isolados por usuário</div>
            </div>
            <div style="grid-column: span 2;">
              <div style="font-size:12px; color:var(--text-muted);">PASTA PRIVADA DE CONFIGURAÇÃO E TOKEN (NUNCA AFETADA POR ATUALIZAÇÕES)</div>
              <div style="font-family:Consolas,monospace; font-size:12.5px; margin-top:4px;" id="upd-config-path-text">~/.jirabot/config.json</div>
            </div>
          </div>
        </div>

        <div class="grid-2" style="margin-bottom:0">
          <div>
            <div class="form-group">
              <label>Fonte de Atualização para os Usuários (Pasta Compartilhada na Rede, OneDrive, Git ou URL .zip)</label>
              <input type="text" id="cfg-update-source" class="form-control" placeholder="Ex: \\servidor\compartilhamento\JiraBot ou URL .zip">
              <small style="font-size:11.5px; color:var(--text-muted);">
                Todos os usuários apontados para a mesma pasta de rede ou Git podem clicar em "Atualizar Aplicativo Agora" sem precisar receber arquivos manualmente e sem perder seus tokens individuais.
              </small>
            </div>
            <div class="form-group" style="flex-direction:row; align-items:center; gap:8px;">
              <input type="checkbox" id="cfg-auto-update">
              <label for="cfg-auto-update" style="margin:0; cursor:pointer;">Buscar e aplicar atualizações automaticamente ao iniciar o JiraBot</label>
            </div>
          </div>

          <div>
            <div class="form-group">
              <label>Publicar Nova Versão Limpa na Pasta Compartilhada (Uso do Mantenedor)</label>
              <div style="display:flex; gap:8px;">
                <input type="text" id="publish-target-dir" class="form-control" placeholder="Ex: \\servidor\compartilhamento\JiraBot" style="flex:1">
                <button class="btn btn-outline" onclick="publishCleanRelease()">Publicar Código Limpo</button>
              </div>
              <small style="font-size:11.5px; color:var(--text-muted);">
                Copia apenas os arquivos .py, .bat e assets atualizados para a pasta compartilhada da equipe (sem incluir jamais .env, tokens, config.json ou relatórios).
              </small>
            </div>
          </div>
        </div>
        <div id="update-status-box" style="margin-top:12px; font-size:13px; display:none; padding:10px 14px; border-radius:7px;"></div>
      </div>

      <div class="grid-2">
        <div class="card">
          <div class="card-header">
            <div class="card-title">Credenciais Individuais e Acesso ao Jira REST API</div>
            <button class="btn btn-outline btn-sm" onclick="testJiraConnection()">Testar Conexão com o Jira</button>
          </div>
          <div class="form-group">
            <label>URL Base do Jira</label>
            <input type="text" id="cfg-base-url" class="form-control" placeholder="https://sua-empresa.atlassian.net">
          </div>
          <div class="form-group">
            <label>E-mail Corporativo do Jira</label>
            <input type="email" id="cfg-email" class="form-control" placeholder="usuario@empresa.com.br">
          </div>
          <div class="form-group">
            <label>API Token Pessoal do Jira (<span id="cfg-token-status">Verificando...</span>)</label>
            <input type="password" id="cfg-api-token" class="form-control" placeholder="Deixe em branco para manter o token salvo atual">
          </div>
          <div class="form-group">
            <label>Ticket Padrão (Default Issue)</label>
            <input type="text" id="cfg-default-issue" class="form-control" placeholder="Ex: ATIVDIV-32">
          </div>
          <div class="form-group">
            <label>Descrição Padrão de Fallback</label>
            <input type="text" id="cfg-default-comment" class="form-control">
          </div>
          <div id="test-jira-result" style="margin-top: 10px; font-size: 13px; display:none; padding: 10px; border-radius: 6px;"></div>
        </div>

        <div class="card">
          <div class="card-header">
            <div class="card-title">Comportamento do Bot e Sistema Windows</div>
          </div>
          <div class="form-group">
            <label>Comportamento para Bloqueios Rápidos fora das Janelas (ex: café / banheiro)</label>
            <select id="cfg-lock-mode" class="form-control">
              <option value="pause">Pausar contagem durante o bloqueio e retomar ao desbloquear (pause)</option>
              <option value="ignore">Ignorar bloqueios rápidos e manter contagem contínua (ignore)</option>
            </select>
          </div>
          <div class="form-group">
            <label>Tempo Mínimo para Lançamento (minutos)</label>
            <input type="number" id="cfg-min-log" class="form-control" min="1" max="120">
          </div>
          <div class="form-group" style="flex-direction:row; align-items:center; gap:8px; margin-top: 10px;">
            <input type="checkbox" id="cfg-notifications">
            <label for="cfg-notifications" style="margin:0; cursor:pointer;">Exibir notificações do Windows (Toast Notifications)</label>
          </div>
          <div class="form-group" style="flex-direction:row; align-items:center; gap:8px;">
            <input type="checkbox" id="cfg-auto-log">
            <label for="cfg-auto-log" style="margin:0; cursor:pointer;">Lançar worklog automaticamente ao bloquear na janela de fim de expediente</label>
          </div>
          <div class="form-group" style="flex-direction:row; align-items:center; gap:8px;">
            <input type="checkbox" id="cfg-autostart">
            <label for="cfg-autostart" style="margin:0; cursor:pointer;">Iniciar JiraBot automaticamente junto com o Windows (Registro HKCU)</label>
          </div>

          <div style="margin-top: 20px;">
            <button class="btn btn-primary" onclick="saveGeneralSettings()">Salvar Todas as Configurações</button>
          </div>
        </div>
      </div>
    </section>

  </main>
</div>

<!-- ==================== MODAL: CRIAR / EDITAR LANCAMENTO DO JIRA ==================== -->
<div class="modal-backdrop" id="worklog-modal">
  <div class="modal-dialog">
    <div class="modal-header">
      <h3 id="wl-modal-title">Novo Lançamento no Jira</h3>
      <button class="btn btn-outline btn-sm" onclick="closeWorklogModal()">Fechar</button>
    </div>
    <div class="modal-body">
      <input type="hidden" id="wl-modal-id">
      <input type="hidden" id="wl-modal-source-issue">

      <div class="form-grid">
        <div class="form-group">
          <label>Ticket do Lançamento (ex: CONSISABI-427)</label>
          <input type="text" id="wl-modal-issue" class="form-control" placeholder="Ex: CONSISABI-427">
          <span id="wl-modal-migrate-hint" style="font-size:11px; color:var(--primary-text); display:none;">
            Se alterar a chave do ticket, o lançamento será migrado automaticamente para o novo ticket.
          </span>
        </div>
        <div class="form-group">
          <label>Data do Lançamento</label>
          <input type="date" id="wl-modal-date" class="form-control" oninput="recalcModalWorklog()">
        </div>
      </div>

      <div class="schedule-box">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; flex-wrap:wrap; gap:6px;">
          <strong style="font-size:13px;">Horários do Lançamento (Início, Pausa de Almoço, Retorno e Encerramento)</strong>
          <label style="font-size:12px; display:flex; align-items:center; gap:6px; cursor:pointer;">
            <input type="checkbox" id="wl-modal-manual-dur-chk" onchange="toggleModalDurationMode()">
            Informar duração manualmente sem calcular pelos horários
          </label>
        </div>

        <div class="schedule-grid" id="wl-modal-schedule-inputs">
          <div class="form-group" style="margin-bottom:0">
            <label>Horário de Início</label>
            <input type="time" id="wl-modal-start-hm" class="form-control" oninput="recalcModalWorklog()">
          </div>
          <div class="form-group" style="margin-bottom:0">
            <label>Pausa de Almoço</label>
            <input type="time" id="wl-modal-ls-hm" class="form-control" oninput="recalcModalWorklog()">
          </div>
          <div class="form-group" style="margin-bottom:0">
            <label>Retorno do Almoço</label>
            <input type="time" id="wl-modal-le-hm" class="form-control" oninput="recalcModalWorklog()">
          </div>
          <div class="form-group" style="margin-bottom:0">
            <label>Encerramento</label>
            <input type="time" id="wl-modal-end-hm" class="form-control" oninput="recalcModalWorklog()">
          </div>
        </div>

        <div class="form-grid" style="margin-top:12px; align-items:center;">
          <div class="form-group" style="margin-bottom:0">
            <label>Tempo Líquido Total a Lançar (ex: 06:00 ou 6h 00m)</label>
            <input type="text" id="wl-modal-duration" class="form-control" placeholder="Ex: 06:00">
          </div>
          <div id="wl-modal-calc-summary" style="font-size:12px; color:var(--text-muted); padding-top:14px;">
            Altere os horários acima para calcular o tempo líquido automaticamente.
          </div>
        </div>
      </div>

      <div class="form-group">
        <label>Descrição / Comentário da Atividade</label>
        <textarea id="wl-modal-comment" class="form-control" placeholder="Digite a descrição detalhada da atividade para este lançamento..."></textarea>
      </div>
      <div class="form-group" style="flex-direction:row; align-items:center; gap:8px;">
        <input type="checkbox" id="wl-modal-no-comment">
        <label for="wl-modal-no-comment" style="margin:0; cursor:pointer;">Lançar SEM descrição (vazio)</label>
      </div>
    </div>
    <div class="modal-footer">
      <button class="btn btn-outline" onclick="closeWorklogModal()">Cancelar</button>
      <button class="btn btn-primary" id="wl-modal-save-btn" onclick="saveModalWorklog()">Salvar Lançamento no Jira</button>
    </div>
  </div>
</div>

<!-- ==================== MODAL: EDICAO EM LOTE DE LANCAMENTOS SELECIONADOS ==================== -->
<div class="modal-backdrop" id="bulk-edit-modal">
  <div class="modal-dialog">
    <div class="modal-header">
      <h3>Editar em Lote (<span id="bulk-edit-count-lbl">0</span> Lançamentos Selecionados)</h3>
      <button class="btn btn-outline btn-sm" onclick="closeBulkEditModal()">Fechar</button>
    </div>
    <div class="modal-body">
      <p style="font-size:13px; color:var(--text-muted); margin-bottom:14px;">
        Marque abaixo apenas os campos que você deseja alterar em todos os lançamentos selecionados:
      </p>

      <!-- 1. Mudar Ticket em Lote -->
      <div class="schedule-box">
        <label style="display:flex; align-items:center; gap:8px; font-weight:700; font-size:13px; cursor:pointer; margin-bottom:8px;">
          <input type="checkbox" id="bulk-apply-ticket-chk">
          Mudar o Ticket de todos os lançamentos selecionados (Migrar em Lote)
        </label>
        <input type="text" id="bulk-new-ticket" class="form-control" placeholder="Novo Ticket de Destino (ex: CONSISABI-427)">
      </div>

      <!-- 2. Alterar Horarios em Lote -->
      <div class="schedule-box">
        <label style="display:flex; align-items:center; gap:8px; font-weight:700; font-size:13px; cursor:pointer; margin-bottom:10px;">
          <input type="checkbox" id="bulk-apply-schedule-chk">
          Alterar Horários (Início, Pausa de Almoço, Retorno e Encerramento) de todos os selecionados
        </label>
        <div class="schedule-grid">
          <div class="form-group" style="margin-bottom:0">
            <label>Início</label>
            <input type="time" id="bulk-edit-start-hm" class="form-control" value="07:45" oninput="recalcBulkEditModal()">
          </div>
          <div class="form-group" style="margin-bottom:0">
            <label>Pausa Almoço</label>
            <input type="time" id="bulk-edit-ls-hm" class="form-control" value="12:00" oninput="recalcBulkEditModal()">
          </div>
          <div class="form-group" style="margin-bottom:0">
            <label>Retorno</label>
            <input type="time" id="bulk-edit-le-hm" class="form-control" value="13:30" oninput="recalcBulkEditModal()">
          </div>
          <div class="form-group" style="margin-bottom:0">
            <label>Encerramento</label>
            <input type="time" id="bulk-edit-end-hm" class="form-control" value="15:15" oninput="recalcBulkEditModal()">
          </div>
        </div>
        <div id="bulk-edit-calc-lbl" style="font-size:12px; color:var(--text-muted); margin-top:8px;">
          Tempo líquido resultante: 06:00
        </div>
      </div>

      <!-- 3. Alterar Descricao em Lote -->
      <div class="schedule-box" style="margin-bottom:0">
        <label style="display:flex; align-items:center; gap:8px; font-weight:700; font-size:13px; cursor:pointer; margin-bottom:8px;">
          <input type="checkbox" id="bulk-apply-comment-chk">
          Alterar a Descrição / Comentário de todos os selecionados
        </label>
        <textarea id="bulk-new-comment" class="form-control" placeholder="Nova descrição para aplicar aos lançamentos selecionados..."></textarea>
      </div>
    </div>
    <div class="modal-footer">
      <button class="btn btn-outline" onclick="closeBulkEditModal()">Cancelar</button>
      <button class="btn btn-primary" id="bulk-edit-save-btn" onclick="submitBulkEditWorklogs()">Aplicar Alterações em Lote no Jira</button>
    </div>
  </div>
</div>

<!-- ==================== MODAL: ADICIONAR / EDITAR INTERVALO DE HOJE ==================== -->
<div class="modal-backdrop" id="interval-modal">
  <div class="modal-dialog" style="max-width: 500px;">
    <div class="modal-header">
      <h3 id="inter-modal-title">Adicionar Intervalo de Trabalho</h3>
      <button class="btn btn-outline btn-sm" onclick="closeIntervalModal()">Fechar</button>
    </div>
    <div class="modal-body">
      <input type="hidden" id="inter-modal-idx" value="-1">
      <div class="form-group">
        <label>Ticket do Intervalo</label>
        <input type="text" id="inter-modal-issue" class="form-control" placeholder="Ex: CONSISABI-427">
      </div>
      <div class="form-grid">
        <div class="form-group">
          <label>Horário de Início (HH:MM)</label>
          <input type="time" id="inter-modal-start" class="form-control">
        </div>
        <div class="form-group">
          <label>Horário de Fim (HH:MM - vazio se em andamento)</label>
          <input type="time" id="inter-modal-end" class="form-control">
        </div>
      </div>
      <div class="form-group">
        <label>Descrição / Comentário</label>
        <input type="text" id="inter-modal-comment" class="form-control">
      </div>
    </div>
    <div class="modal-footer">
      <button class="btn btn-outline" onclick="closeIntervalModal()">Cancelar</button>
      <button class="btn btn-primary" onclick="saveIntervalModal()">Salvar Intervalo</button>
    </div>
  </div>
</div>

<!-- ==================== MODAL: LANCAR HORAS DE HOJE AGORA (LOG-NOW) ==================== -->
<div class="modal-backdrop" id="lognow-modal">
  <div class="modal-dialog" style="max-width: 520px;">
    <div class="modal-header">
      <h3>Lançar Expediente de Hoje no Jira Agora</h3>
      <button class="btn btn-outline btn-sm" onclick="closeLogNowModal()">Fechar</button>
    </div>
    <div class="modal-body">
      <p style="font-size:13px; color:var(--text-muted); margin-bottom:14px;">
        Isso encerrará os intervalos em aberto de hoje e enviará imediatamente os apontamentos acumulados de cada ticket para o Jira.
      </p>
      <div class="form-group" style="flex-direction:row; align-items:center; gap:8px;">
        <input type="checkbox" id="lognow-no-comment">
        <label for="lognow-no-comment" style="margin:0; cursor:pointer;">Enviar apontamentos SEM nenhuma descrição</label>
      </div>
    </div>
    <div class="modal-footer">
      <button class="btn btn-outline" onclick="closeLogNowModal()">Cancelar</button>
      <button class="btn btn-success" onclick="confirmLogNow()">Confirmar e Lançar no Jira</button>
    </div>
  </div>
</div>

<div id="toast-container"></div>

<script>
let appState = null;
let configData = null;
let loadedWorklogs = [];
let selectedWorklogIds = new Set();
let batchPreviewRows = [];
let currentWeeklyData = null;
let scheduleInputsTouched = false;

/* ==================== TEMA (DARK / LIGHT MODE) ==================== */
function applyTheme(theme) {
  const clean = theme === 'light' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', clean);
  localStorage.setItem('jirabot_theme', clean);
  const lbl = document.getElementById('theme-toggle-label');
  if (lbl) {
    lbl.textContent = clean === 'dark' ? 'Modo Claro' : 'Modo Escuro';
  }
}

async function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'dark';
  const next = current === 'dark' ? 'light' : 'dark';
  applyTheme(next);
  try {
    await apiCall('/api/theme', 'POST', { theme: next });
  } catch (e) {
    // salvo no localStorage mesmo se offline
  }
}

// Aplica tema salvo imediatamente ao carregar
(function initTheme() {
  const saved = localStorage.getItem('jirabot_theme') || 'dark';
  applyTheme(saved);
})();

function showToast(msg, type = 'info') {
  const container = document.getElementById('toast-container');
  const el = document.createElement('div');
  el.className = 'toast ' + type;
  el.textContent = msg;
  container.appendChild(el);
  setTimeout(() => {
    el.remove();
  }, 4200);
}

/* API Call com Retentativa Transparente contra resets de socket */
async function apiCall(path, method = 'GET', body = null, retries = 2) {
  const opts = { method, cache: 'no-store' };
  if (body !== null) {
    opts.headers = { 'Content-Type': 'application/json' };
    opts.body = JSON.stringify(body);
  }
  let lastErr = null;
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const resp = await fetch(path, opts);
      const data = await resp.json();
      if (!resp.ok || data.error) {
        throw new Error(data.error || data.message || `Erro HTTP ${resp.status}`);
      }
      return data;
    } catch (err) {
      lastErr = err;
      const isNetworkErr = err instanceof TypeError || String(err.message).includes('Failed to fetch');
      if (isNetworkErr && attempt < retries) {
        await new Promise(r => setTimeout(r, 350 * (attempt + 1)));
        continue;
      }
      throw err;
    }
  }
  throw lastErr;
}

function switchTab(tabId, btnEl) {
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  const pane = document.getElementById(tabId);
  if (pane) pane.classList.add('active');
  const navBtn = btnEl || document.querySelector('.nav-btn[data-tab="' + tabId + '"]');
  if (navBtn) navBtn.classList.add('active');
  if (typeof closeMobileSidebar === 'function') closeMobileSidebar();
  window.scrollTo({ top: 0, behavior: 'auto' });

  const titles = {
    'tab-dashboard': 'Painel do Dia e Controle de Expediente',
    'tab-analytics': 'Dashboard Analítico (Tickets, Tipos e Evolução)',
    'tab-alerts': 'Avisos e Notificações de Expediente',
    'tab-weekly': 'Visualização Semanal (Calendário e Status)',
    'tab-worklogs': 'Lançamentos do Jira (Worklogs e Multi-Seleção)',
    'tab-batch': 'Lançamentos em Lote (Múltiplos Dias e Semanas)',
    'tab-profiles': 'Perfis de Turno e Janelas de Horário',
    'tab-reports': 'Relatórios Consolidados e Banco de Horas',
    'tab-settings': 'Configurações, Isolamento Multi-Usuário e Atualização'
  };
  document.getElementById('page-title').textContent = titles[tabId] || 'JiraBot Web';

  if (tabId === 'tab-weekly') {
    const refInput = document.getElementById('weekly-ref-date');
    if (!refInput.value) refInput.value = new Date().toISOString().slice(0, 10);
    loadWeeklyView(refInput.value);
  } else if (tabId === 'tab-alerts') {
    loadAlertsData();
  } else if (tabId === 'tab-worklogs' && loadedWorklogs.length === 0) {
    loadJiraWorklogs();
  } else if (tabId === 'tab-batch') {
    initBatchTabDefaults();
  } else if (tabId === 'tab-reports') {
    loadReport(7);
  } else if (tabId === 'tab-analytics') {
    loadAnalytics(false);
  } else if (tabId === 'tab-profiles' || tabId === 'tab-settings') {
    loadConfigData();
  }
}

function hmToMinutes(hm) {
  if (!hm || !hm.includes(':')) return null;
  const [h, m] = hm.split(':').map(Number);
  if (isNaN(h) || isNaN(m)) return null;
  return h * 60 + m;
}

function minutesToHM(mins) {
  const m = Math.max(0, Math.round(mins));
  const hh = String(Math.floor(m / 60)).padStart(2, '0');
  const mm = String(m % 60).padStart(2, '0');
  return `${hh}:${mm}`;
}

function computeScheduleMinutes(startHm, lsHm, leHm, endHm) {
  const s = hmToMinutes(startHm);
  if (s === null) return null;
  const ls = hmToMinutes(lsHm);
  const le = hmToMinutes(leHm);
  const e = hmToMinutes(endHm);

  let morning = 0;
  let lunch = 0;
  let afternoon = 0;

  // Se o intervalo [s, e] termina antes do almoco ou comeca apos o retorno do almoco, ignora a pausa
  if (ls !== null && le !== null && e !== null && e >= s && ls <= le && (e <= ls || s >= le)) {
    morning = e - s;
    return { morning, lunch: 0, afternoon: 0, total: morning };
  }

  if (ls !== null && le !== null) {
    if (ls < s || le < ls) return { error: 'Verifique a ordem entre Início, Pausa de Almoço e Retorno.' };
    morning = ls - s;
    lunch = le - ls;
    if (e !== null) {
      if (e < le) return { error: 'O encerramento não pode ser anterior ao retorno do almoço.' };
      afternoon = e - le;
    }
  } else if (ls !== null && le === null && e === null) {
    if (ls < s) return { error: 'A pausa de almoço não pode ser anterior ao início.' };
    morning = ls - s;
  } else if (e !== null) {
    if (e < s) return { error: 'O encerramento não pode ser anterior ao início.' };
    morning = e - s;
  }

  const total = morning + afternoon;
  return { morning, lunch, afternoon, total };
}

function escapeHtml(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/* ==================== DASHBOARD ==================== */
async function loadDashboard(forceScheduleFill = false) {
  try {
    const data = await apiCall('/api/status', 'GET', null, 1);
    appState = data;

    if (data.version) {
      document.getElementById('sidebar-version-label').textContent = `Gerenciador de Horas v${data.version}`;
    }

    const dot = document.getElementById('sidebar-dot');
    const dText = document.getElementById('sidebar-daemon-text');
    if (data.service.is_running) {
      dot.className = 'dot online';
      dText.textContent = `Serviço Ativo (PID: ${data.service.pid})`;
      document.getElementById('stat-daemon-state').textContent = `Ativo (${data.service.pid})`;
    } else {
      dot.className = 'dot';
      dText.textContent = 'Serviço Parado';
      document.getElementById('stat-daemon-state').textContent = 'Parado';
    }
    document.getElementById('sidebar-profile-text').textContent = `Perfil: ${data.profile.name} (${data.profile.target_hours}h)`;

    const badge = document.getElementById('top-status-badge');
    const st = data.today.status;
    const statusLabelsPt = {
      'RUNNING': 'EM ANDAMENTO',
      'PAUSED_LUNCH': 'PAUSADO (ALMOÇO)',
      'PAUSED_AWAY': 'PAUSADO (AUSENTE)',
      'COMPLETED': 'EXPEDIENTE CONCLUÍDO',
      'IDLE': 'AGUARDANDO'
    };
    badge.textContent = statusLabelsPt[st] || st;
    badge.className = 'badge ' + (
      st === 'RUNNING' ? 'badge-running' :
      (st === 'PAUSED_LUNCH' || st === 'PAUSED_AWAY') ? 'badge-paused' :
      st === 'COMPLETED' ? 'badge-completed' : 'badge-idle'
    );

    document.getElementById('stat-today-time').textContent = data.today.total_formatted;
    document.getElementById('stat-progress-bar').style.width = `${data.today.progress_percent}%`;
    document.getElementById('stat-today-meta').textContent = `Meta: ${data.today.target_hours}h (${data.today.progress_percent}%)`;

    document.getElementById('stat-active-ticket').textContent = data.today.target_issue;
    if (data.today.no_comment) {
      document.getElementById('stat-active-desc').textContent = '(Configurado para enviar SEM descrição)';
    } else {
      document.getElementById('stat-active-desc').textContent = data.today.active_comment || '(Usando descrição padrão do ticket)';
    }

    document.getElementById('stat-last-event').textContent = `Último: ${data.today.last_event} (${data.today.last_event_time})`;
    document.getElementById('stat-logged-state').textContent = data.today.is_logged ? 'Enviado ao Jira' : 'Pendente';
    document.getElementById('stat-queue-count').textContent = `Fila offline: ${data.queue.length} item(ns)`;

    const swIssue = document.getElementById('switch-issue-input');
    if (!swIssue.value) swIssue.value = data.today.target_issue;
    const swComm = document.getElementById('switch-comment-input');
    if (document.activeElement !== swComm && !swComm.value) {
      swComm.value = data.today.active_comment || '';
    }
    document.getElementById('today-no-comment-chk').checked = Boolean(data.today.no_comment);

    if (!scheduleInputsTouched || forceScheduleFill) {
      document.getElementById('today-start-hm').value = data.today.shift_times.start_hm || '';
      document.getElementById('today-lunch-start-hm').value = data.today.shift_times.lunch_start_hm || '';
      document.getElementById('today-lunch-end-hm').value = data.today.shift_times.lunch_end_hm || '';
      document.getElementById('today-end-hm').value = data.today.shift_times.end_hm || '';
      previewTodaySchedule(false);
    }

    const tList = document.getElementById('today-tickets-list');
    if (data.today.issues_summary.length === 0) {
      tList.innerHTML = '<div style="font-size:12px; color:var(--text-muted);">Nenhum ticket contabilizado ainda hoje.</div>';
    } else {
      tList.innerHTML = data.today.issues_summary.map(item => `
        <div style="display:flex; justify-content:space-between; align-items:center; padding:6px 0; border-bottom:1px solid var(--border-color); font-size:13px;">
          <div>
            <span class="ticket-pill">${escapeHtml(item.issue_key)}</span>
            <strong style="margin-left:8px;">${item.formatted}</strong>
            <span style="color:var(--text-muted); margin-left:8px; font-size:12px;">${item.comment ? '"' + escapeHtml(item.comment) + '"' : '(padrão)'}</span>
          </div>
          <button class="btn btn-outline btn-sm" onclick="quickEditIssueToday('${escapeHtml(item.issue_key)}', '${escapeHtml(item.comment || '').replace(/'/g, "\\'")}')">Editar Descrição</button>
        </div>
      `).join('');
    }

    const iTbody = document.getElementById('today-intervals-tbody');
    if (data.today.intervals.length === 0) {
      iTbody.innerHTML = '<tr><td colspan="7" style="text-align:center; color:var(--text-muted);">Nenhum intervalo registrado hoje.</td></tr>';
    } else {
      iTbody.innerHTML = data.today.intervals.map(inter => `
        <tr>
          <td>${inter.index + 1}</td>
          <td><span class="ticket-pill">${escapeHtml(inter.issue_key)}</span></td>
          <td><span class="time-pill">${inter.start_hm || '-'}</span></td>
          <td><span class="time-pill">${inter.end_hm || 'Em andamento'}</span></td>
          <td><strong>${inter.duration_formatted}</strong></td>
          <td>${inter.comment ? escapeHtml(inter.comment) : '<span style="color:var(--text-muted);">-</span>'}</td>
          <td>
            <div class="btn-group">
              <button class="btn btn-outline btn-sm" onclick='openIntervalModal(${inter.index}, ${JSON.stringify(inter)})'>Editar</button>
              <button class="btn btn-danger btn-sm" onclick="deleteInterval(${inter.index})">Excluir</button>
            </div>
          </td>
        </tr>
      `).join('');
    }

    const qCard = document.getElementById('offline-queue-card');
    const qTbody = document.getElementById('offline-queue-tbody');
    if (data.queue.length > 0) {
      qCard.style.display = 'block';
      qTbody.innerHTML = data.queue.map(q => `
        <tr>
          <td>${q.date}</td>
          <td><span class="ticket-pill">${escapeHtml(q.issue_key)}</span></td>
          <td><strong>${q.time_formatted}</strong></td>
          <td>${escapeHtml(q.comment || '(Sem descrição)')}</td>
          <td>Tentativas: ${q.retry_count} ${q.last_error ? '<br><small style="color:var(--danger)">' + escapeHtml(q.last_error) + '</small>' : ''}</td>
          <td>
            <button class="btn btn-danger btn-sm" onclick="deleteQueueItem('${q.id}')">Remover da Fila</button>
          </td>
        </tr>
      `).join('');
    } else {
      qCard.style.display = 'none';
    }
  } catch (err) {
    console.debug('Polling status:', err);
  }
}

function previewTodaySchedule(markTouched = true) {
  if (markTouched) scheduleInputsTouched = true;
  const s = document.getElementById('today-start-hm').value;
  const ls = document.getElementById('today-lunch-start-hm').value;
  const le = document.getElementById('today-lunch-end-hm').value;
  const e = document.getElementById('today-end-hm').value;
  const label = document.getElementById('today-schedule-calc-text');

  const res = computeScheduleMinutes(s, ls, le, e);
  if (!res) {
    label.textContent = 'Informe ao menos o Horário de Início para calcular o expediente.';
    return;
  }
  if (res.error) {
    label.innerHTML = `<span style="color:var(--danger); font-weight:600;">${res.error}</span>`;
    return;
  }
  label.innerHTML = `Manhã: <strong>${minutesToHM(res.morning)}</strong> | Pausa Almoço: <strong>${minutesToHM(res.lunch)}</strong> | Tarde: <strong>${minutesToHM(res.afternoon)}</strong> | Total Líquido: <strong style="color:var(--primary-text); font-size:14px;">${minutesToHM(res.total)}</strong>`;
}

function fillTodayDefaultSchedule() {
  const is8h = appState && appState.profile && appState.profile.name === '8h';
  document.getElementById('today-start-hm').value = is8h ? '07:42' : '07:45';
  document.getElementById('today-lunch-start-hm').value = '12:00';
  document.getElementById('today-lunch-end-hm').value = is8h ? '13:00' : '13:30';
  document.getElementById('today-end-hm').value = is8h ? '17:42' : '15:15';
  previewTodaySchedule(true);
}

async function saveTodaySchedule() {
  const start_hm = document.getElementById('today-start-hm').value;
  const lunch_start_hm = document.getElementById('today-lunch-start-hm').value;
  const lunch_end_hm = document.getElementById('today-lunch-end-hm').value;
  const end_hm = document.getElementById('today-end-hm').value;

  if (!start_hm) {
    showToast('Informe o Horário de Início.', 'error');
    return;
  }
  try {
    const res = await apiCall('/api/today/schedule', 'POST', {
      start_hm, lunch_start_hm, lunch_end_hm, end_hm
    });
    scheduleInputsTouched = false;
    showToast(res.message || 'Horários de hoje atualizados com sucesso!', 'success');
    await loadDashboard(true);
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function serviceAction(action) {
  try {
    const res = await apiCall('/api/service', 'POST', { action });
    showToast(res.message || 'Ação executada com sucesso!', 'success');
    await loadDashboard(true);
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function deleteQueueItem(itemId) {
  if (!confirm('Deseja remover este item pendente da fila offline?')) return;
  try {
    const res = await apiCall('/api/service', 'POST', { action: 'delete_queue_item', item_id: itemId });
    showToast(res.message, 'success');
    await loadDashboard();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

function quickEditIssueToday(issueKey, currentComment) {
  document.getElementById('switch-issue-input').value = issueKey;
  document.getElementById('switch-comment-input').value = currentComment;
  document.getElementById('switch-comment-input').focus();
}

async function submitSwitchOrComment(action) {
  const issue_key = document.getElementById('switch-issue-input').value.trim().toUpperCase();
  const comment = document.getElementById('switch-comment-input').value.trim();
  const no_comment = document.getElementById('today-no-comment-chk').checked;
  if (!issue_key) {
    showToast('Informe a chave do ticket.', 'error');
    return;
  }
  try {
    const res = await apiCall('/api/today/ticket', 'POST', {
      action, issue_key, comment, no_comment
    });
    showToast(res.message, 'success');
    await loadDashboard();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function toggleTodayNoComment(checked) {
  try {
    const res = await apiCall('/api/today/ticket', 'POST', {
      action: 'toggle_no_comment',
      no_comment: checked
    });
    showToast(res.message, 'success');
    await loadDashboard();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function submitTransferToday() {
  const source_issue = document.getElementById('transfer-src-input').value.trim().toUpperCase();
  const target_issue = document.getElementById('transfer-tgt-input').value.trim().toUpperCase();
  const time_str = document.getElementById('transfer-time-input').value.trim();
  if (!source_issue || !target_issue) {
    showToast('Informe o ticket de origem e o de destino.', 'error');
    return;
  }
  try {
    const res = await apiCall('/api/today/ticket', 'POST', {
      action: 'transfer', source_issue, target_issue, time_str
    });
    showToast(res.message, 'success');
    await loadDashboard();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

/* ==================== VISUALIZACAO SEMANAL ==================== */
async function loadWeeklyView(refDateStr = '') {
  const tbody = document.getElementById('weekly-table-tbody');
  tbody.innerHTML = '<tr><td colspan="11" style="text-align:center; padding:24px; color:var(--text-muted);">Consultando dados da semana...</td></tr>';
  const fetchJira = document.getElementById('weekly-fetch-jira-chk').checked ? '1' : '0';

  try {
    const q = new URLSearchParams({ ref_date: refDateStr || '', fetch_jira: fetchJira });
    const data = await apiCall('/api/weekly?' + q.toString());
    currentWeeklyData = data;

    document.getElementById('weekly-ref-date').value = data.ref_date;
    document.getElementById('wk-range-label').textContent = `${data.monday_br} a ${data.sunday_br}`;
    document.getElementById('wk-days-logged-sub').textContent = `Dias úteis lançados: ${data.weekdays_logged_count} / 5`;
    document.getElementById('wk-total-worked').textContent = data.total_week_formatted;
    document.getElementById('wk-full-target-sub').textContent = `Meta semanal (5 dias): ${data.full_week_target_formatted}`;
    document.getElementById('wk-target-today').textContent = data.target_until_today_formatted;

    const balEl = document.getElementById('wk-balance');
    balEl.textContent = data.balance_formatted;
    balEl.style.color = data.balance_positive ? 'var(--success)' : 'var(--danger)';

    tbody.innerHTML = data.days.map(d => {
      const sch = d.schedule || {};
      const rowClass = d.is_today ? 'row-today' : '';
      const badgeClass = d.status_type === 'logged' ? 'badge-running' :
                         d.status_type === 'running' ? 'badge-completed' :
                         d.status_type === 'missing' ? 'badge-danger' : 'badge-idle';

      const ticketsHtml = d.tickets && d.tickets.length > 0
        ? d.tickets.map((t, tIdx) => `
            <div style="display:flex; align-items:baseline; flex-wrap:wrap; gap:6px; ${tIdx < d.tickets.length - 1 ? 'margin-bottom:6px;' : ''} line-height:1.45;">
              <span class="ticket-pill">${escapeHtml(t.issue_key)}</span>
              <strong style="white-space:nowrap;">${t.formatted}</strong>
              ${t.comment ? `<span style="font-size:12px; color:var(--text-muted); word-break:break-word;">— "${escapeHtml(t.comment)}"</span>` : ''}
            </div>
          `).join('')
        : (d.is_weekend ? '<span style="color:var(--text-muted);">[Fim de Semana]</span>' : '<span style="color:var(--text-muted);">-</span>');

      const firstWl = (d.tickets && d.tickets.length > 0 && d.tickets[0].id) ? d.tickets[0] : null;
      const editBtn = firstWl
        ? `<button class="btn btn-outline btn-sm" onclick='openWorklogModal(${JSON.stringify({
            id: firstWl.id,
            issue_key: firstWl.issue_key,
            date: d.date,
            time_spent_seconds: firstWl.seconds,
            comment: firstWl.comment,
            schedule: firstWl.schedule
          })})'>Editar</button>`
        : '';

      return `
        <tr class="${rowClass}">
          <td style="white-space:nowrap;">
            <div style="display:inline-flex; align-items:center; gap:6px;">
              <strong>${d.weekday}</strong>
              ${d.is_today ? '<span class="badge badge-completed">HOJE</span>' : ''}
            </div>
          </td>
          <td style="white-space:nowrap;"><strong>${d.date_br}</strong></td>
          <td style="white-space:nowrap; text-align:center;"><span class="time-pill">${sch.start_hm || '-'}</span></td>
          <td style="white-space:nowrap; text-align:center;"><span class="time-pill">${sch.lunch_start_hm || '-'}</span></td>
          <td style="white-space:nowrap; text-align:center;"><span class="time-pill">${sch.lunch_end_hm || '-'}</span></td>
          <td style="white-space:nowrap; text-align:center;"><span class="time-pill">${sch.end_hm || '-'}</span></td>
          <td style="min-width:240px;">${ticketsHtml}</td>
          <td style="white-space:nowrap;"><strong>${d.total_formatted}</strong></td>
          <td style="white-space:nowrap;">${d.target_formatted}</td>
          <td style="white-space:nowrap; text-align:center;"><span class="badge ${badgeClass}">${d.status_label}</span></td>
          <td style="text-align:right; white-space:nowrap;">
            <div class="btn-group" style="justify-content:flex-end; flex-wrap:nowrap;">
              ${editBtn}
              <button class="btn btn-primary btn-sm" onclick="openWorklogModalForDate('${d.date}')">+ Lançar no Dia</button>
            </div>
          </td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="11" style="text-align:center; color:var(--danger); padding:20px;">Erro ao carregar semana: ${escapeHtml(err.message)}</td></tr>`;
  }
}

function navigateWeek(direction) {
  if (direction === 0) {
    const todayIso = new Date().toISOString().slice(0, 10);
    loadWeeklyView(todayIso);
  } else if (direction < 0 && currentWeeklyData) {
    loadWeeklyView(currentWeeklyData.prev_monday);
  } else if (direction > 0 && currentWeeklyData) {
    loadWeeklyView(currentWeeklyData.next_monday);
  }
}

function openWorklogModalForDate(dateStr) {
  openWorklogModal(null);
  document.getElementById('wl-modal-date').value = dateStr;
  recalcModalWorklog();
}

function openBatchForCurrentWeek() {
  if (!currentWeeklyData) return;
  switchTab('tab-batch');
  document.getElementById('batch-start-date').value = currentWeeklyData.monday;
  document.getElementById('batch-end-date').value = currentWeeklyData.sunday;
  onBatchPeriodOrWeekdayChange();
  generateBatchPreview();
}

/* ==================== INTERVALS MODAL ==================== */
function openIntervalModal(idx, inter = null) {
  document.getElementById('inter-modal-idx').value = idx;
  document.getElementById('inter-modal-title').textContent = idx >= 0 ? `Editar Intervalo #${idx + 1}` : 'Adicionar Intervalo Manual';
  document.getElementById('inter-modal-issue').value = inter ? inter.issue_key : (appState ? appState.today.target_issue : '');
  document.getElementById('inter-modal-start').value = inter ? inter.start_hm : '08:00';
  document.getElementById('inter-modal-end').value = inter ? inter.end_hm : '12:00';
  document.getElementById('inter-modal-comment').value = inter ? inter.comment : '';
  document.getElementById('interval-modal').classList.add('open');
}

function closeIntervalModal() {
  document.getElementById('interval-modal').classList.remove('open');
}

async function saveIntervalModal() {
  const idx = parseInt(document.getElementById('inter-modal-idx').value, 10);
  const issue_key = document.getElementById('inter-modal-issue').value.trim().toUpperCase();
  const start_hm = document.getElementById('inter-modal-start').value;
  const end_hm = document.getElementById('inter-modal-end').value;
  const comment = document.getElementById('inter-modal-comment').value.trim();

  if (!start_hm) {
    showToast('Informe o horário de início do intervalo.', 'error');
    return;
  }
  try {
    const res = await apiCall('/api/today/intervals', 'POST', {
      action: idx >= 0 ? 'update' : 'add',
      index: idx,
      issue_key,
      start_hm,
      end_hm,
      comment
    });
    closeIntervalModal();
    showToast(res.message, 'success');
    await loadDashboard(true);
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function deleteInterval(idx) {
  if (!confirm(`Deseja realmente excluir o intervalo #${idx + 1} de hoje?`)) return;
  try {
    const res = await apiCall('/api/today/intervals', 'POST', {
      action: 'delete',
      index: idx
    });
    showToast(res.message, 'success');
    await loadDashboard(true);
  } catch (err) {
    showToast(err.message, 'error');
  }
}

/* ==================== LOG NOW MODAL ==================== */
function openLogNowModal() {
  document.getElementById('lognow-no-comment').checked = Boolean(appState && appState.today.no_comment);
  document.getElementById('lognow-modal').classList.add('open');
}

function closeLogNowModal() {
  document.getElementById('lognow-modal').classList.remove('open');
}

async function confirmLogNow() {
  const no_comment = document.getElementById('lognow-no-comment').checked;
  try {
    const res = await apiCall('/api/today/ticket', 'POST', {
      action: 'log_now',
      no_comment
    });
    closeLogNowModal();
    showToast(res.message, 'success');
    await loadDashboard(true);
  } catch (err) {
    showToast(err.message, 'error');
  }
}

/* ==================== WORKLOGS DO JIRA E MULTI-SELECAO EM LOTE ==================== */
async function loadJiraWorklogs() {
  const days = document.getElementById('wl-filter-days').value;
  const issue = document.getElementById('wl-filter-issue').value.trim().toUpperCase();
  const tbody = document.getElementById('jira-worklogs-tbody');
  tbody.innerHTML = '<tr><td colspan="10" style="text-align:center; padding: 24px; color:var(--text-muted);">Consultando lançamentos no Jira... Aguarde.</td></tr>';

  try {
    const q = new URLSearchParams({ days });
    if (issue) q.set('issue_key', issue);
    const res = await apiCall('/api/worklogs?' + q.toString());
    loadedWorklogs = res.worklogs || [];
    selectedWorklogIds.clear();
    updateBulkBarUI();
    renderWorklogsTable();
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="10" style="text-align:center; color:var(--danger); padding:20px;">Erro ao carregar lançamentos: ${escapeHtml(err.message)}</td></tr>`;
  }
}

function renderWorklogsTable() {
  const tbody = document.getElementById('jira-worklogs-tbody');
  const search = (document.getElementById('wl-search-text').value || '').trim().toLowerCase();

  const filtered = loadedWorklogs.filter(w => {
    if (!search) return true;
    return (
      (w.issue_key || '').toLowerCase().includes(search) ||
      (w.date || '').toLowerCase().includes(search) ||
      (w.comment || '').toLowerCase().includes(search) ||
      (w.summary || '').toLowerCase().includes(search)
    );
  });

  document.getElementById('wl-count-label').textContent = filtered.length;

  if (filtered.length === 0) {
    tbody.innerHTML = '<tr><td colspan="10" style="text-align:center; padding: 24px; color:var(--text-muted);">Nenhum lançamento encontrado para o filtro selecionado.</td></tr>';
    return;
  }

  tbody.innerHTML = filtered.map(w => {
    const sch = w.schedule || {};
    const isChecked = selectedWorklogIds.has(String(w.id)) ? 'checked' : '';
    const commentHtml = w.comment
      ? `<span>${escapeHtml(w.comment)}</span>`
      : `<span style="color:var(--text-muted); font-style:italic;">(Sem descrição)</span>`;
    return `
      <tr>
        <td><input type="checkbox" class="wl-row-chk" value="${w.id}" ${isChecked} onchange="onWorklogRowCheck('${w.id}', this.checked)"></td>
        <td><strong>${w.date}</strong></td>
        <td>
          <span class="ticket-pill" title="${escapeHtml(w.summary || '')}">${escapeHtml(w.issue_key)}</span>
          ${w.summary ? `<div style="font-size:11px; color:var(--text-muted); max-width:190px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${escapeHtml(w.summary)}</div>` : ''}
        </td>
        <td><span class="time-pill">${sch.start_hm || '-'}</span></td>
        <td><span class="time-pill">${sch.lunch_start_hm || '-'}</span></td>
        <td><span class="time-pill">${sch.lunch_end_hm || '-'}</span></td>
        <td><span class="time-pill">${sch.end_hm || '-'}</span></td>
        <td><strong style="color:var(--primary-text);">${w.time_formatted || w.time_spent}</strong></td>
        <td style="max-width: 280px;">${commentHtml}</td>
        <td style="text-align:right; white-space:nowrap;">
          <div class="btn-group" style="justify-content:flex-end;">
            <button class="btn btn-outline btn-sm" onclick="openEditWorklogById('${w.id}')">Editar / Horários / Ticket</button>
            <button class="btn btn-danger btn-sm" onclick="deleteJiraWorklog('${w.issue_key}', '${w.id}', '${w.date}')">Excluir</button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

function onWorklogRowCheck(wid, checked) {
  if (checked) {
    selectedWorklogIds.add(String(wid));
  } else {
    selectedWorklogIds.delete(String(wid));
  }
  updateBulkBarUI();
}

function toggleSelectAllWorklogs(checked) {
  document.querySelectorAll('.wl-row-chk').forEach(chk => {
    chk.checked = checked;
    if (checked) selectedWorklogIds.add(String(chk.value));
    else selectedWorklogIds.delete(String(chk.value));
  });
  updateBulkBarUI();
}

function clearWorklogSelection() {
  selectedWorklogIds.clear();
  const selAll = document.getElementById('wl-select-all-chk');
  if (selAll) selAll.checked = false;
  document.querySelectorAll('.wl-row-chk').forEach(chk => { chk.checked = false; });
  updateBulkBarUI();
}

function updateBulkBarUI() {
  const bar = document.getElementById('wl-bulk-bar');
  const count = selectedWorklogIds.size;
  document.getElementById('wl-selected-count').textContent = count;
  if (count > 0) bar.classList.add('active');
  else bar.classList.remove('active');
}

function openBulkEditModal() {
  const count = selectedWorklogIds.size;
  if (count === 0) return;
  document.getElementById('bulk-edit-count-lbl').textContent = count;
  document.getElementById('bulk-apply-ticket-chk').checked = false;
  document.getElementById('bulk-new-ticket').value = '';
  document.getElementById('bulk-apply-schedule-chk').checked = false;
  document.getElementById('bulk-apply-comment-chk').checked = false;
  document.getElementById('bulk-new-comment').value = '';
  recalcBulkEditModal();
  document.getElementById('bulk-edit-modal').classList.add('open');
}

function closeBulkEditModal() {
  document.getElementById('bulk-edit-modal').classList.remove('open');
}

function recalcBulkEditModal() {
  const s = document.getElementById('bulk-edit-start-hm').value;
  const ls = document.getElementById('bulk-edit-ls-hm').value;
  const le = document.getElementById('bulk-edit-le-hm').value;
  const e = document.getElementById('bulk-edit-end-hm').value;
  const res = computeScheduleMinutes(s, ls, le, e);
  const lbl = document.getElementById('bulk-edit-calc-lbl');
  if (!res || res.error) {
    lbl.textContent = res && res.error ? res.error : 'Informe horários válidos.';
    return;
  }
  lbl.innerHTML = `Tempo líquido resultante para cada lançamento: <strong>${minutesToHM(res.total)}</strong>`;
}

async function submitBulkEditWorklogs() {
  const applyTicket = document.getElementById('bulk-apply-ticket-chk').checked;
  const newTicket = document.getElementById('bulk-new-ticket').value.trim().toUpperCase();
  const applySchedule = document.getElementById('bulk-apply-schedule-chk').checked;
  const start_hm = document.getElementById('bulk-edit-start-hm').value;
  const lunch_start_hm = document.getElementById('bulk-edit-ls-hm').value;
  const lunch_end_hm = document.getElementById('bulk-edit-le-hm').value;
  const end_hm = document.getElementById('bulk-edit-end-hm').value;
  const applyComment = document.getElementById('bulk-apply-comment-chk').checked;
  const newComment = document.getElementById('bulk-new-comment').value.trim();

  if (!applyTicket && !applySchedule && !applyComment) {
    showToast('Marque ao menos uma alteração (Ticket, Horários ou Descrição).', 'error');
    return;
  }
  if (applyTicket && !newTicket) {
    showToast('Informe o novo Ticket de destino.', 'error');
    return;
  }

  const items = loadedWorklogs.filter(w => selectedWorklogIds.has(String(w.id)));
  const btn = document.getElementById('bulk-edit-save-btn');
  btn.disabled = true;
  btn.textContent = `Processando ${items.length} lançamentos...`;

  try {
    const res = await apiCall('/api/worklogs/batch-update', 'POST', {
      items: items.map(w => ({
        worklog_id: w.id,
        source_issue: w.issue_key,
        date_str: w.date,
        current_seconds: w.time_spent_seconds,
        current_started: w.started,
        current_comment: w.comment
      })),
      apply_ticket: applyTicket,
      target_issue: newTicket,
      apply_schedule: applySchedule,
      start_hm,
      lunch_start_hm,
      lunch_end_hm,
      end_hm,
      apply_comment: applyComment,
      comment: newComment
    });
    closeBulkEditModal();
    showToast(res.message, 'success');
    await loadJiraWorklogs();
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Aplicar Alterações em Lote no Jira';
  }
}

async function deleteSelectedWorklogsBulk() {
  const items = loadedWorklogs.filter(w => selectedWorklogIds.has(String(w.id)));
  if (items.length === 0) return;
  if (!confirm(`Confirma a EXCLUSÃO em lote de ${items.length} lançamento(s) selecionado(s) no Jira?`)) return;

  try {
    const res = await apiCall('/api/worklogs/batch-delete', 'POST', {
      items: items.map(w => ({ worklog_id: w.id, issue_key: w.issue_key }))
    });
    showToast(res.message, 'success');
    await loadJiraWorklogs();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

/* ==================== GERADOR DE LANCAMENTOS EM LOTE (MULTI-DIAS / SEMANAS / MULTI-TICKETS) ==================== */
let batchTemplateTickets = [];

function formatDateBrFromIso(isoStr) {
  if (!isoStr || isoStr.length < 10) return isoStr || '';
  const [y, m, d] = isoStr.slice(0, 10).split('-');
  return `${d}/${m}/${y}`;
}

function getBatchActiveDaysInfo() {
  const startDateStr = document.getElementById('batch-start-date').value;
  const endDateStr = document.getElementById('batch-end-date').value;
  const allowedWeekdays = new Set(
    Array.from(document.querySelectorAll('.batch-wd-chk:checked')).map(c => parseInt(c.value, 10))
  );
  const weekdaysNames = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'];

  if (!startDateStr || !endDateStr || startDateStr > endDateStr) {
    return { valid: false, calendarDays: 0, skippedDays: 0, activeDays: [] };
  }

  const cur = new Date(startDateStr + 'T12:00:00');
  const end = new Date(endDateStr + 'T12:00:00');
  let calendarDays = 0;
  let skippedDays = 0;
  const activeDays = [];

  // Limite de seguranca de 180 dias para evitar loops acidentais em datas invalidas
  while (cur <= end && calendarDays < 180) {
    calendarDays++;
    const iso = cur.toISOString().slice(0, 10);
    const wd = (cur.getDay() + 6) % 7; // Seg=0..Dom=6
    if (allowedWeekdays.has(wd)) {
      activeDays.push({
        date: iso,
        date_br: formatDateBrFromIso(iso),
        weekday: weekdaysNames[wd],
        wd_index: wd
      });
    } else {
      skippedDays++;
    }
    cur.setDate(cur.getDate() + 1);
  }

  return { valid: true, calendarDays, skippedDays, activeDays };
}

function initBatchTabDefaults() {
  previewBatchBaseSchedule();
  onBatchPeriodOrWeekdayChange();
}

function onBatchPeriodOrWeekdayChange() {
  const mode = document.getElementById('batch-multi-mode').value || 'one_per_day';
  const info = getBatchActiveDaysInfo();
  const infoEl = document.getElementById('batch-period-days-info');

  if (!info.valid) {
    if (infoEl) {
      infoEl.innerHTML = `<span style="color:var(--text-muted);">Escolha a <strong>Data Inicial</strong> e a <strong>Data Final</strong> acima para calcular os dias habilitados do período (ou clique em um dos atalhos opcionais).</span>`;
    }
  } else {
    if (infoEl) {
      infoEl.innerHTML = `Período selecionado: <strong>${info.calendarDays} dia(s) corrido(s)</strong> | <strong>${info.activeDays.length} dia(s) habilitado(s)</strong> para lançamento (${info.skippedDays} dia(s) pulado(s) pelo seletor Seg-Dom).`;
    }
  }

  if (mode === 'one_per_day') {
    syncTicketsToActiveDays(info);
  } else if (batchTemplateTickets.length === 0) {
    const defaultIssue = (appState && appState.today && appState.today.target_issue) ? appState.today.target_issue : 'ATIVDIV-32';
    batchTemplateTickets.push({
      issue_key: defaultIssue,
      start_hm: document.getElementById('batch-start-hm').value || '07:45',
      lunch_start_hm: document.getElementById('batch-ls-hm').value || '12:00',
      lunch_end_hm: document.getElementById('batch-le-hm').value || '13:30',
      end_hm: document.getElementById('batch-end-hm').value || '15:15',
      comment: ''
    });
  }

  updateBatchModeExplanation(info);
  renderBatchTemplateTickets(info);
}

function syncTicketsToActiveDays(infoObj = null) {
  const info = infoObj || getBatchActiveDaysInfo();
  const defaultIssue = (appState && appState.today && appState.today.target_issue) ? appState.today.target_issue : 'ATIVDIV-32';
  const baseStart = document.getElementById('batch-start-hm').value || '07:45';
  const baseLs = document.getElementById('batch-ls-hm').value || '12:00';
  const baseLe = document.getElementById('batch-le-hm').value || '13:30';
  const baseEnd = document.getElementById('batch-end-hm').value || '15:15';

  if (!info.valid || info.activeDays.length === 0) {
    if (batchTemplateTickets.length === 0) {
      batchTemplateTickets = [{
        issue_key: defaultIssue,
        start_hm: baseStart,
        lunch_start_hm: baseLs,
        lunch_end_hm: baseLe,
        end_hm: baseEnd,
        comment: ''
      }];
    } else if (batchTemplateTickets.length > 1) {
      batchTemplateTickets = batchTemplateTickets.slice(0, 1);
    }
    return;
  }

  const targetCount = info.activeDays.length;
  const refIssue = (batchTemplateTickets.length > 0 && batchTemplateTickets[batchTemplateTickets.length - 1].issue_key)
    ? batchTemplateTickets[batchTemplateTickets.length - 1].issue_key
    : defaultIssue;
  const refComment = (batchTemplateTickets.length > 0)
    ? (batchTemplateTickets[batchTemplateTickets.length - 1].comment || '')
    : '';

  // Se o periodo aumentou (ex: de 2 dias para 14 dias -> 10 dias uteis), adiciona automaticamente os tickets faltantes
  while (batchTemplateTickets.length < targetCount) {
    batchTemplateTickets.push({
      issue_key: refIssue,
      start_hm: baseStart,
      lunch_start_hm: baseLs,
      lunch_end_hm: baseLe,
      end_hm: baseEnd,
      comment: refComment
    });
  }

  // Se o periodo diminuiu, limita estritamente ao total de dias habilitados no periodo
  if (batchTemplateTickets.length > targetCount) {
    batchTemplateTickets = batchTemplateTickets.slice(0, targetCount);
  }
}

function updateBatchModeExplanation(infoObj = null) {
  const info = infoObj || getBatchActiveDaysInfo();
  const mode = document.getElementById('batch-multi-mode').value || 'one_per_day';
  const box = document.getElementById('batch-mode-explanation-box');
  const secTitle = document.getElementById('batch-tickets-section-title');
  const secSub = document.getElementById('batch-tickets-section-subtitle');
  const colHdr = document.getElementById('batch-tpl-col-order-hdr');
  const addBtn = document.getElementById('batch-add-ticket-btn');
  const splitEqBtn = document.getElementById('batch-split-eq-btn');
  const splitMaBtn = document.getElementById('batch-split-ma-btn');
  const activeCount = info.valid ? info.activeDays.length : 0;

  if (mode === 'one_per_day') {
    if (box) {
      box.innerHTML = `
        <div style="font-weight:700; font-size:13px; color:var(--primary-text); margin-bottom:4px;">
          Como funciona o modo "1 Ticket por Dia (Em Ordem Cronológica)":
        </div>
        <div style="font-size:12.5px; color:var(--text-main); line-height:1.5;">
          1. O sistema calcula automaticamente quantos dias serão lançados no período que você escolheu, descontando os dias da semana desmarcados (por exemplo: um período de <strong>14 dias corridos</strong> com Sábado e Domingo desmarcados gera exatamente <strong>10 dias úteis/tickets</strong>).<br>
          2. A tabela abaixo cria <strong>automaticamente 1 linha para cada dia habilitado, em ordem cronológica</strong>: o <strong>Ticket #1</strong> será lançado no <strong>1º dia útil</strong> do período, o <strong>Ticket #2</strong> no <strong>2º dia útil</strong>, e assim sucessivamente até o último dia.<br>
          3. A quantidade de tickets fica <strong>estritamente limitada ao total de dias habilitados (${activeCount} dia(s) neste momento)</strong>.
        </div>
      `;
    }
    if (secTitle) {
      secTitle.innerHTML = `Tickets por Dia do Período (<span id="batch-tickets-count-lbl">${batchTemplateTickets.length}</span> de ${activeCount || batchTemplateTickets.length} dia(s) habilitado(s))`;
    }
    if (secSub) {
      secSub.textContent = info.valid
        ? `As ${activeCount} linha(s) abaixo foram ajustadas automaticamente para os ${activeCount} dia(s) habilitados do período escolhido (em ordem do 1º ao último dia).`
        : `Escolha a Data Inicial e a Data Final acima para que o sistema gere automaticamente 1 linha para cada dia útil do período.`;
    }
    if (colHdr) colHdr.textContent = 'Ordem / Data do Dia';
    if (splitEqBtn) splitEqBtn.style.display = 'none';
    if (splitMaBtn) splitMaBtn.style.display = 'none';
    if (addBtn) {
      const maxReached = !info.valid || batchTemplateTickets.length >= activeCount;
      addBtn.disabled = maxReached;
      addBtn.textContent = maxReached
        ? `Limite de ${activeCount || 1} Ticket(s) para ${activeCount || 1} Dia(s)`
        : `+ Adicionar Ticket (${batchTemplateTickets.length}/${activeCount})`;
    }
  } else {
    if (box) {
      box.innerHTML = `
        <div style="font-weight:700; font-size:13px; color:var(--primary-text); margin-bottom:4px;">
          Como funciona o modo "Dividir o Mesmo Dia entre Vários Tickets":
        </div>
        <div style="font-size:12.5px; color:var(--text-main); line-height:1.5;">
          1. Use esta opção quando você trabalha em <strong>2 ou mais tickets diferentes dentro do mesmo dia</strong> (por exemplo: 3h pela manhã no <code>TICKET-A</code> e 3h à tarde no <code>TICKET-B</code>) e quer repetir essa mesma divisão diária em todos os <strong>${activeCount} dia(s) habilitados</strong> do período.<br>
          2. Na tabela abaixo você cadastra apenas os tickets que compõem <strong>1 dia de trabalho</strong> e pode clicar em <strong>Dividir Horas Iguais no Dia</strong> ou <strong>Dividir Manhã / Tarde</strong> para repartir o horário sem sobreposição.
        </div>
      `;
    }
    if (secTitle) {
      secTitle.innerHTML = `Tickets que Dividem Cada Dia de Trabalho (<span id="batch-tickets-count-lbl">${batchTemplateTickets.length}</span> ticket(s) por dia)`;
    }
    if (secSub) {
      secSub.textContent = `Todos os ${batchTemplateTickets.length} ticket(s) abaixo serão lançados dentro de cada um dos ${activeCount} dia(s) habilitados do período.`;
    }
    if (colHdr) colHdr.textContent = 'Ordem no Dia';
    if (splitEqBtn) splitEqBtn.style.display = 'inline-flex';
    if (splitMaBtn) splitMaBtn.style.display = 'inline-flex';
    if (addBtn) {
      addBtn.disabled = false;
      addBtn.textContent = '+ Adicionar Outro Ticket no Mesmo Dia';
    }
  }
}

function copyFirstTicketToAllBatchTemplates() {
  if (batchTemplateTickets.length === 0) return;
  const firstIssue = (batchTemplateTickets[0].issue_key || '').trim().toUpperCase();
  const firstComment = batchTemplateTickets[0].comment || '';
  if (!firstIssue) {
    showToast('Informe primeiro o código do Ticket #1.', 'error');
    return;
  }
  batchTemplateTickets.forEach(t => {
    t.issue_key = firstIssue;
    if (firstComment) t.comment = firstComment;
  });
  renderBatchTemplateTickets();
  showToast(`Ticket ${firstIssue} copiado para todas as ${batchTemplateTickets.length} linhas!`, 'success');
}

function setBatchBaseProfile(mode) {
  if (mode === '8h') {
    document.getElementById('batch-start-hm').value = '07:42';
    document.getElementById('batch-ls-hm').value = '12:00';
    document.getElementById('batch-le-hm').value = '13:00';
    document.getElementById('batch-end-hm').value = '17:42';
  } else {
    document.getElementById('batch-start-hm').value = '07:45';
    document.getElementById('batch-ls-hm').value = '12:00';
    document.getElementById('batch-le-hm').value = '13:30';
    document.getElementById('batch-end-hm').value = '15:15';
  }
  previewBatchBaseSchedule();
  const distMode = document.getElementById('batch-multi-mode').value;
  if (distMode === 'split_day' && batchTemplateTickets.length > 1) {
    autoSplitBatchTicketsEqual();
  } else {
    syncBatchTicketsWithBaseSchedule();
  }
}

function renderBatchTemplateTickets(infoObj = null) {
  const tbody = document.getElementById('batch-template-tickets-tbody');
  const info = infoObj || getBatchActiveDaysInfo();
  const mode = document.getElementById('batch-multi-mode').value || 'one_per_day';
  updateBatchModeExplanation(info);
  if (!tbody) return;

  tbody.innerHTML = batchTemplateTickets.map((t, idx) => {
    const calc = computeScheduleMinutes(t.start_hm, t.lunch_start_hm, t.lunch_end_hm, t.end_hm);
    const netStr = (calc && !calc.error) ? minutesToHM(calc.total) : 'Inválido';
    const disableDel = batchTemplateTickets.length <= 1 ? 'disabled' : '';

    let orderCellHtml = `<strong>#${idx + 1}</strong>`;
    if (mode === 'one_per_day' && info.valid && info.activeDays[idx]) {
      const dObj = info.activeDays[idx];
      orderCellHtml = `
        <div>
          <strong>Dia #${idx + 1}</strong>
          <span class="badge badge-completed" style="margin-left:6px;">${dObj.weekday}, ${dObj.date_br}</span>
        </div>
      `;
    } else if (mode === 'split_day') {
      orderCellHtml = `<strong>Parte #${idx + 1} do Dia</strong>`;
    }

    return `
      <tr>
        <td style="white-space:nowrap;">${orderCellHtml}</td>
        <td>
          <input type="text" class="form-control" style="width:145px; padding:6px 8px;" value="${escapeHtml(t.issue_key)}" placeholder="Ex: CONSISABI-427" oninput="batchTemplateTickets[${idx}].issue_key=this.value.toUpperCase()">
        </td>
        <td>
          <input type="time" class="form-control" style="padding:6px 6px;" value="${t.start_hm}" oninput="batchTemplateTickets[${idx}].start_hm=this.value; updateBatchTemplateRowNet(${idx})">
        </td>
        <td>
          <input type="time" class="form-control" style="padding:6px 6px;" value="${t.lunch_start_hm}" oninput="batchTemplateTickets[${idx}].lunch_start_hm=this.value; updateBatchTemplateRowNet(${idx})">
        </td>
        <td>
          <input type="time" class="form-control" style="padding:6px 6px;" value="${t.lunch_end_hm}" oninput="batchTemplateTickets[${idx}].lunch_end_hm=this.value; updateBatchTemplateRowNet(${idx})">
        </td>
        <td>
          <input type="time" class="form-control" style="padding:6px 6px;" value="${t.end_hm}" oninput="batchTemplateTickets[${idx}].end_hm=this.value; updateBatchTemplateRowNet(${idx})">
        </td>
        <td>
          <strong id="batch-tpl-net-${idx}" style="color:var(--primary-text);">${netStr}</strong>
        </td>
        <td>
          <input type="text" class="form-control" style="min-width:200px; padding:6px 8px;" value="${escapeHtml(t.comment)}" placeholder="Opcional (vazio usa padrão do ticket)" oninput="batchTemplateTickets[${idx}].comment=this.value">
        </td>
        <td style="text-align:right;">
          <button class="btn btn-danger btn-sm" ${disableDel} onclick="removeBatchTemplateTicket(${idx})">Remover</button>
        </td>
      </tr>
    `;
  }).join('');
}

function updateBatchTemplateRowNet(idx) {
  const t = batchTemplateTickets[idx];
  const calc = computeScheduleMinutes(t.start_hm, t.lunch_start_hm, t.lunch_end_hm, t.end_hm);
  const el = document.getElementById(`batch-tpl-net-${idx}`);
  if (el) {
    el.textContent = (calc && !calc.error) ? minutesToHM(calc.total) : 'Inválido';
  }
}

function addBatchTemplateTicket() {
  const mode = document.getElementById('batch-multi-mode').value || 'one_per_day';
  const info = getBatchActiveDaysInfo();
  if (mode === 'one_per_day') {
    if (!info.valid || info.activeDays.length === 0) {
      showToast('Escolha primeiro a Data Inicial e a Data Final do período.', 'error');
      return;
    }
    if (batchTemplateTickets.length >= info.activeDays.length) {
      showToast(`Limite atingido: o período possui ${info.activeDays.length} dia(s) habilitado(s), portanto o máximo no modo 1 Ticket por Dia é ${info.activeDays.length}.`, 'error');
      return;
    }
  }

  const defaultIssue = (appState && appState.today && appState.today.target_issue) ? appState.today.target_issue : 'ATIVDIV-32';
  batchTemplateTickets.push({
    issue_key: defaultIssue,
    start_hm: document.getElementById('batch-start-hm').value || '07:45',
    lunch_start_hm: document.getElementById('batch-ls-hm').value || '12:00',
    lunch_end_hm: document.getElementById('batch-le-hm').value || '13:30',
    end_hm: document.getElementById('batch-end-hm').value || '15:15',
    comment: ''
  });
  if (mode === 'split_day') {
    autoSplitBatchTicketsEqual();
  } else {
    renderBatchTemplateTickets(info);
  }
}

function removeBatchTemplateTicket(idx) {
  if (batchTemplateTickets.length <= 1) return;
  batchTemplateTickets.splice(idx, 1);
  const mode = document.getElementById('batch-multi-mode').value;
  if (mode === 'split_day') {
    autoSplitBatchTicketsEqual();
  } else {
    renderBatchTemplateTickets();
  }
}

function onBatchMultiModeChange() {
  const mode = document.getElementById('batch-multi-mode').value;
  const info = getBatchActiveDaysInfo();
  if (mode === 'one_per_day') {
    syncTicketsToActiveDays(info);
    syncBatchTicketsWithBaseSchedule();
  } else if (mode === 'split_day') {
    // Ao mudar para dividir o mesmo dia, se havia 10 linhas dos 10 dias, reduz para os 2 primeiros tickets para dividir o dia
    if (batchTemplateTickets.length > 2) {
      batchTemplateTickets = batchTemplateTickets.slice(0, 2);
    }
    if (batchTemplateTickets.length > 1) {
      autoSplitBatchTicketsEqual();
    } else {
      renderBatchTemplateTickets(info);
    }
  }
}

function syncBatchTicketsWithBaseSchedule() {
  const s = document.getElementById('batch-start-hm').value || '07:45';
  const ls = document.getElementById('batch-ls-hm').value || '12:00';
  const le = document.getElementById('batch-le-hm').value || '13:30';
  const e = document.getElementById('batch-end-hm').value || '15:15';
  batchTemplateTickets.forEach(t => {
    t.start_hm = s;
    t.lunch_start_hm = ls;
    t.lunch_end_hm = le;
    t.end_hm = e;
  });
  renderBatchTemplateTickets();
}

function autoSplitBatchTicketsEqual() {
  const sHm = document.getElementById('batch-start-hm').value || '07:45';
  const lsHm = document.getElementById('batch-ls-hm').value || '12:00';
  const leHm = document.getElementById('batch-le-hm').value || '13:30';
  const eHm = document.getElementById('batch-end-hm').value || '15:15';

  const s = hmToMinutes(sHm);
  const ls = hmToMinutes(lsHm);
  const le = hmToMinutes(leHm);
  const e = hmToMinutes(eHm);
  const n = batchTemplateTickets.length;

  if (n <= 1 || s === null || e === null) {
    syncBatchTicketsWithBaseSchedule();
    return;
  }

  const hasLunch = (ls !== null && le !== null && ls >= s && le >= ls && e >= le);
  const morningMins = hasLunch ? (ls - s) : (e - s);
  const afternoonMins = hasLunch ? (e - le) : 0;
  const totalNet = morningMins + afternoonMins;

  if (totalNet <= 0) {
    syncBatchTicketsWithBaseSchedule();
    return;
  }

  const netOffsetToClock = (offset, isEndBoundary) => {
    if (!hasLunch) return s + offset;
    if (offset < morningMins) return s + offset;
    if (offset === morningMins) return isEndBoundary ? ls : le;
    return le + (offset - morningMins);
  };

  for (let i = 0; i < n; i++) {
    const wStart = Math.round((i * totalNet) / n);
    const wEnd = Math.round(((i + 1) * totalNet) / n);
    const clockStart = netOffsetToClock(wStart, false);
    const clockEnd = netOffsetToClock(wEnd, true);

    batchTemplateTickets[i].start_hm = minutesToHM(clockStart);
    batchTemplateTickets[i].end_hm = minutesToHM(clockEnd);
    if (hasLunch && wStart < morningMins && wEnd > morningMins) {
      batchTemplateTickets[i].lunch_start_hm = lsHm;
      batchTemplateTickets[i].lunch_end_hm = leHm;
    } else {
      batchTemplateTickets[i].lunch_start_hm = '';
      batchTemplateTickets[i].lunch_end_hm = '';
    }
  }
  renderBatchTemplateTickets();
}

function autoSplitBatchTicketsMorningAfternoon() {
  const sHm = document.getElementById('batch-start-hm').value || '07:45';
  const lsHm = document.getElementById('batch-ls-hm').value || '12:00';
  const leHm = document.getElementById('batch-le-hm').value || '13:30';
  const eHm = document.getElementById('batch-end-hm').value || '15:15';
  const n = batchTemplateTickets.length;

  if (n <= 1) {
    syncBatchTicketsWithBaseSchedule();
    return;
  }

  batchTemplateTickets[0].start_hm = sHm;
  batchTemplateTickets[0].lunch_start_hm = '';
  batchTemplateTickets[0].lunch_end_hm = '';
  batchTemplateTickets[0].end_hm = lsHm;

  const le = hmToMinutes(leHm) || 810;
  const e = hmToMinutes(eHm) || 915;
  const aftTotal = Math.max(0, e - le);
  const rem = n - 1;

  for (let j = 0; j < rem; j++) {
    const st = le + Math.round((j * aftTotal) / rem);
    const en = le + Math.round(((j + 1) * aftTotal) / rem);
    batchTemplateTickets[j + 1].start_hm = minutesToHM(st);
    batchTemplateTickets[j + 1].lunch_start_hm = '';
    batchTemplateTickets[j + 1].lunch_end_hm = '';
    batchTemplateTickets[j + 1].end_hm = minutesToHM(en);
  }
  renderBatchTemplateTickets();
}

function setBatchPreset(preset) {
  const today = new Date();
  const formatIso = d => d.toISOString().slice(0, 10);
  const dayOfWeek = (today.getDay() + 6) % 7; // Segunda=0 .. Domingo=6

  let start = new Date(today);
  let end = new Date(today);

  if (preset === 'this_week') {
    start.setDate(today.getDate() - dayOfWeek);
  } else if (preset === 'last_week') {
    start.setDate(today.getDate() - dayOfWeek - 7);
    end = new Date(start);
    end.setDate(start.getDate() + 4);
  } else if (preset === '2_weeks') {
    start.setDate(today.getDate() - dayOfWeek - 7);
  } else if (preset === '3_weeks') {
    start.setDate(today.getDate() - dayOfWeek - 14);
  } else if (preset === 'month') {
    start.setDate(today.getDate() - 29);
  }

  document.getElementById('batch-start-date').value = formatIso(start);
  document.getElementById('batch-end-date').value = formatIso(end);
  onBatchPeriodOrWeekdayChange();
}

function previewBatchBaseSchedule() {
  const s = document.getElementById('batch-start-hm').value;
  const ls = document.getElementById('batch-ls-hm').value;
  const le = document.getElementById('batch-le-hm').value;
  const e = document.getElementById('batch-end-hm').value;
  const res = computeScheduleMinutes(s, ls, le, e);
  const el = document.getElementById('batch-base-calc-text');
  if (!res || res.error) {
    el.innerHTML = `<span style="color:var(--danger)">${res ? res.error : 'Horários inválidos'}</span>`;
    return;
  }
  el.innerHTML = `Tempo Líquido Base: <span style="color:var(--primary-text)">${minutesToHM(res.total)}</span>`;
}

async function generateBatchPreview() {
  const startDateStr = document.getElementById('batch-start-date').value;
  const endDateStr = document.getElementById('batch-end-date').value;
  const multiMode = document.getElementById('batch-multi-mode').value || 'one_per_day';
  const skipExisting = document.getElementById('batch-skip-existing-chk').checked;
  const info = getBatchActiveDaysInfo();

  if (!info.valid || info.activeDays.length === 0) {
    showToast('Escolha uma Data Inicial e uma Data Final válidas com pelo menos 1 dia da semana habilitado.', 'error');
    return;
  }

  const validTickets = batchTemplateTickets.filter(t => (t.issue_key || '').trim().length > 0);
  if (validTickets.length === 0) {
    showToast('Informe ao menos 1 Ticket na lista de Tickets.', 'error');
    return;
  }

  const card = document.getElementById('batch-preview-card');
  const tbody = document.getElementById('batch-preview-tbody');
  card.style.display = 'block';
  tbody.innerHTML = '<tr><td colspan="12" style="text-align:center; padding:20px; color:var(--text-muted);">Validando dias no Jira e montando a grade de envio...</td></tr>';

  let existingByDate = {};
  if (skipExisting) {
    try {
      const res = await apiCall(`/api/worklogs/range?start_date=${startDateStr}&end_date=${endDateStr}`);
      (res.worklogs || []).forEach(w => {
        existingByDate[w.date] = (existingByDate[w.date] || 0) + (w.time_spent_seconds || 0);
      });
    } catch (e) {
      console.warn('Falha ao consultar existentes:', e);
    }
  }

  batchPreviewRows = [];

  info.activeDays.forEach((dObj, dayIdx) => {
    const iso = dObj.date;
    const existingSec = existingByDate[iso] || 0;
    const shouldSelect = !(skipExisting && existingSec > 0);

    if (multiMode === 'one_per_day') {
      // Ordem cronologica estrita: Ticket #1 para o 1o dia habilitado, Ticket #2 para o 2o dia, ate o ultimo dia
      if (dayIdx < validTickets.length) {
        const tpl = validTickets[dayIdx];
        batchPreviewRows.push({
          date: iso,
          weekday: dObj.weekday,
          existing_seconds: existingSec,
          selected: shouldSelect,
          issue_key: tpl.issue_key.trim().toUpperCase(),
          start_hm: tpl.start_hm,
          lunch_start_hm: tpl.lunch_start_hm,
          lunch_end_hm: tpl.lunch_end_hm,
          end_hm: tpl.end_hm,
          comment: tpl.comment || ''
        });
      }
    } else {
      // split_day: divide cada dia habilitado entre os tickets configurados
      validTickets.forEach(tpl => {
        batchPreviewRows.push({
          date: iso,
          weekday: dObj.weekday,
          existing_seconds: existingSec,
          selected: shouldSelect,
          issue_key: tpl.issue_key.trim().toUpperCase(),
          start_hm: tpl.start_hm,
          lunch_start_hm: tpl.lunch_start_hm,
          lunch_end_hm: tpl.lunch_end_hm,
          end_hm: tpl.end_hm,
          comment: tpl.comment || ''
        });
      });
    }
  });

  renderBatchPreviewTable();
}

function renderBatchPreviewTable() {
  const tbody = document.getElementById('batch-preview-tbody');
  if (batchPreviewRows.length === 0) {
    tbody.innerHTML = '<tr><td colspan="12" style="text-align:center; padding:20px; color:var(--text-muted);">Nenhum dia corresponde aos critérios selecionados.</td></tr>';
    updateBatchSummaryCount();
    return;
  }

  tbody.innerHTML = batchPreviewRows.map((r, idx) => {
    const calc = computeScheduleMinutes(r.start_hm, r.lunch_start_hm, r.lunch_end_hm, r.end_hm);
    const netStr = (calc && !calc.error) ? minutesToHM(calc.total) : 'Erro';
    const statusBadge = r.existing_seconds > 0
      ? `<span class="badge badge-running">Já possui ${minutesToHM(r.existing_seconds / 60)}</span>`
      : `<span class="badge badge-idle">Sem lançamento</span>`;

    return `
      <tr>
        <td><input type="checkbox" ${r.selected ? 'checked' : ''} onchange="batchPreviewRows[${idx}].selected=this.checked; updateBatchSummaryCount();"></td>
        <td><strong>${r.date}</strong></td>
        <td>${r.weekday}</td>
        <td>${statusBadge}</td>
        <td><input type="text" class="form-control" style="width:130px; padding:5px 8px;" value="${escapeHtml(r.issue_key)}" oninput="batchPreviewRows[${idx}].issue_key=this.value.toUpperCase()"></td>
        <td><input type="time" class="form-control" style="padding:5px 6px;" value="${r.start_hm}" oninput="batchPreviewRows[${idx}].start_hm=this.value; updateBatchRowNet(${idx})"></td>
        <td><input type="time" class="form-control" style="padding:5px 6px;" value="${r.lunch_start_hm}" oninput="batchPreviewRows[${idx}].lunch_start_hm=this.value; updateBatchRowNet(${idx})"></td>
        <td><input type="time" class="form-control" style="padding:5px 6px;" value="${r.lunch_end_hm}" oninput="batchPreviewRows[${idx}].lunch_end_hm=this.value; updateBatchRowNet(${idx})"></td>
        <td><input type="time" class="form-control" style="padding:5px 6px;" value="${r.end_hm}" oninput="batchPreviewRows[${idx}].end_hm=this.value; updateBatchRowNet(${idx})"></td>
        <td><strong id="batch-row-net-${idx}" style="color:var(--primary-text);">${netStr}</strong></td>
        <td><input type="text" class="form-control" style="min-width:170px; padding:5px 8px;" value="${escapeHtml(r.comment)}" placeholder="Padrão do ticket" oninput="batchPreviewRows[${idx}].comment=this.value"></td>
        <td style="text-align:right; white-space:nowrap;">
          <div class="btn-group" style="justify-content:flex-end;">
            <button class="btn btn-outline btn-sm" onclick="addTicketRowForDay(${idx})" title="Adicionar outro ticket para esta mesma data">+ Ticket no Dia</button>
            <button class="btn btn-danger btn-sm" onclick="removeBatchPreviewRow(${idx})" title="Remover esta linha do lote">Remover</button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
  updateBatchSummaryCount();
}

function addTicketRowForDay(idx) {
  const curRow = batchPreviewRows[idx];
  if (!curRow) return;

  let newStart = curRow.start_hm;
  let newLs = '';
  let newLe = '';
  let newEnd = curRow.end_hm;

  // Se a linha atual tem almoco preenchido, divide automaticamente em Manha (linha atual) e Tarde (nova linha)
  const s = hmToMinutes(curRow.start_hm);
  const ls = hmToMinutes(curRow.lunch_start_hm);
  const le = hmToMinutes(curRow.lunch_end_hm);
  const e = hmToMinutes(curRow.end_hm);

  if (s !== null && ls !== null && le !== null && e !== null && ls > s && e > le) {
    curRow.end_hm = curRow.lunch_start_hm;
    curRow.lunch_start_hm = '';
    curRow.lunch_end_hm = '';
    newStart = minutesToHM(le);
    newEnd = minutesToHM(e);
  } else if (s !== null && e !== null && e > s) {
    const mid = Math.round((s + e) / 2);
    curRow.end_hm = minutesToHM(mid);
    curRow.lunch_start_hm = '';
    curRow.lunch_end_hm = '';
    newStart = minutesToHM(mid);
    newEnd = minutesToHM(e);
  }

  const newRow = {
    date: curRow.date,
    weekday: curRow.weekday,
    existing_seconds: curRow.existing_seconds,
    selected: curRow.selected,
    issue_key: curRow.issue_key,
    start_hm: newStart,
    lunch_start_hm: newLs,
    lunch_end_hm: newLe,
    end_hm: newEnd,
    comment: curRow.comment
  };

  batchPreviewRows.splice(idx + 1, 0, newRow);
  renderBatchPreviewTable();
  showToast(`Novo ticket adicionado para o dia ${curRow.date}. Informe a chave do segundo ticket!`, 'info');
}

function removeBatchPreviewRow(idx) {
  batchPreviewRows.splice(idx, 1);
  renderBatchPreviewTable();
}

function applyQuickFillToBatchRows() {
  const newIssue = (document.getElementById('batch-quick-issue').value || '').trim().toUpperCase();
  const newComm = (document.getElementById('batch-quick-comment').value || '').trim();
  if (!newIssue && !newComm) {
    showToast('Informe um Ticket ou uma Descrição para aplicar nas linhas marcadas.', 'error');
    return;
  }
  let count = 0;
  batchPreviewRows.forEach(r => {
    if (r.selected) {
      if (newIssue) r.issue_key = newIssue;
      if (newComm) r.comment = newComm;
      count++;
    }
  });
  if (count === 0) {
    showToast('Nenhuma linha está marcada na tabela.', 'error');
    return;
  }
  renderBatchPreviewTable();
  showToast(`Alteração aplicada em ${count} linha(s) marcada(s)!`, 'success');
}

function updateBatchRowNet(idx) {
  const r = batchPreviewRows[idx];
  const calc = computeScheduleMinutes(r.start_hm, r.lunch_start_hm, r.lunch_end_hm, r.end_hm);
  const el = document.getElementById(`batch-row-net-${idx}`);
  if (el) {
    el.textContent = (calc && !calc.error) ? minutesToHM(calc.total) : 'Inválido';
  }
}

function toggleAllBatchRows(checked) {
  batchPreviewRows.forEach(r => { r.selected = checked; });
  renderBatchPreviewTable();
}

function updateBatchSummaryCount() {
  const selectedRows = batchPreviewRows.filter(r => r.selected);
  const distinctDays = new Set(selectedRows.map(r => r.date)).size;
  const distinctTickets = new Set(selectedRows.map(r => r.issue_key)).size;
  document.getElementById('batch-selected-summary').textContent =
    `${selectedRows.length} lançamento(s) marcado(s) em ${distinctDays} dia(s) (${distinctTickets} ticket(s))`;
}

async function submitBatchWorklogs() {
  const selected = batchPreviewRows.filter(r => r.selected);
  if (selected.length === 0) {
    showToast('Selecione ao menos 1 lançamento na tabela para enviar.', 'error');
    return;
  }
  const distinctDays = new Set(selected.map(r => r.date)).size;
  const distinctTickets = Array.from(new Set(selected.map(r => r.issue_key))).join(', ');
  const no_comment = document.getElementById('batch-no-comment-chk').checked;
  if (!confirm(`Confirma o lançamento em lote de ${selected.length} apontamento(s) (${distinctDays} dia(s) | Tickets: ${distinctTickets}) diretamente no Jira?`)) return;

  const btn = document.getElementById('batch-submit-btn');
  btn.disabled = true;
  btn.textContent = `Enviando ${selected.length} lançamentos ao Jira...`;

  try {
    const res = await apiCall('/api/worklogs/batch-create', 'POST', {
      no_comment,
      entries: selected
    });
    showToast(res.message, 'success');
    await generateBatchPreview();
    await loadDashboard();
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = '2. Lançar Todos os Selecionados no Jira Agora';
  }
}


/* ==================== MODAL INDIVIDUAL WORKLOG ==================== */
function openWorklogModal(worklog = null) {
  const isEdit = Boolean(worklog && worklog.id);
  document.getElementById('wl-modal-title').textContent = isEdit
    ? `Editar Lançamento #${worklog.id} (${worklog.issue_key})`
    : 'Lançar Novo Worklog no Jira';
  document.getElementById('wl-modal-id').value = isEdit ? worklog.id : '';
  document.getElementById('wl-modal-source-issue').value = isEdit ? worklog.issue_key : '';
  document.getElementById('wl-modal-issue').value = isEdit
    ? worklog.issue_key
    : (appState && appState.today ? appState.today.target_issue : 'ATIVDIV-32');
  document.getElementById('wl-modal-migrate-hint').style.display = isEdit ? 'block' : 'none';

  const todayIso = new Date().toISOString().slice(0, 10);
  document.getElementById('wl-modal-date').value = isEdit ? worklog.date : todayIso;

  const sch = (worklog && worklog.schedule) ? worklog.schedule : {
    start_hm: '07:45',
    lunch_start_hm: '12:00',
    lunch_end_hm: '13:30',
    end_hm: '15:15'
  };

  document.getElementById('wl-modal-start-hm').value = sch.start_hm || '07:45';
  document.getElementById('wl-modal-ls-hm').value = sch.lunch_start_hm || '';
  document.getElementById('wl-modal-le-hm').value = sch.lunch_end_hm || '';
  document.getElementById('wl-modal-end-hm').value = sch.end_hm || '';

  document.getElementById('wl-modal-manual-dur-chk').checked = false;
  toggleModalDurationMode();

  if (isEdit) {
    document.getElementById('wl-modal-duration').value = worklog.hm_formatted || minutesToHM((worklog.time_spent_seconds || 0) / 60);
  } else {
    recalcModalWorklog();
  }

  document.getElementById('wl-modal-comment').value = isEdit ? (worklog.comment || '') : '';
  document.getElementById('wl-modal-no-comment').checked = false;

  document.getElementById('worklog-modal').classList.add('open');
}

function openEditWorklogById(wid) {
  const found = loadedWorklogs.find(x => String(x.id) === String(wid));
  if (found) {
    openWorklogModal(found);
  }
}

function closeWorklogModal() {
  document.getElementById('worklog-modal').classList.remove('open');
}

function toggleModalDurationMode() {
  const manual = document.getElementById('wl-modal-manual-dur-chk').checked;
  const durInput = document.getElementById('wl-modal-duration');
  durInput.readOnly = !manual;
  if (!manual) {
    recalcModalWorklog();
  }
}

function recalcModalWorklog() {
  const manual = document.getElementById('wl-modal-manual-dur-chk').checked;
  const s = document.getElementById('wl-modal-start-hm').value;
  const ls = document.getElementById('wl-modal-ls-hm').value;
  const le = document.getElementById('wl-modal-le-hm').value;
  const e = document.getElementById('wl-modal-end-hm').value;
  const summaryEl = document.getElementById('wl-modal-calc-summary');

  const res = computeScheduleMinutes(s, ls, le, e);
  if (!res) {
    summaryEl.textContent = 'Preencha início e encerramento para calcular automaticamente.';
    return;
  }
  if (res.error) {
    summaryEl.innerHTML = `<span style="color:var(--danger); font-weight:600;">${res.error}</span>`;
    return;
  }
  if (!manual && res.total > 0) {
    document.getElementById('wl-modal-duration').value = minutesToHM(res.total);
  }
  summaryEl.innerHTML = `Manhã: <strong>${minutesToHM(res.morning)}</strong> | Almoço: <strong>${minutesToHM(res.lunch)}</strong> | Tarde: <strong>${minutesToHM(res.afternoon)}</strong> | Líquido: <strong>${minutesToHM(res.total)}</strong>`;
}

async function saveModalWorklog() {
  const worklog_id = document.getElementById('wl-modal-id').value.trim();
  const source_issue = document.getElementById('wl-modal-source-issue').value.trim().toUpperCase();
  const target_issue = document.getElementById('wl-modal-issue').value.trim().toUpperCase();
  const date_str = document.getElementById('wl-modal-date').value;
  const start_hm = document.getElementById('wl-modal-start-hm').value;
  const lunch_start_hm = document.getElementById('wl-modal-ls-hm').value;
  const lunch_end_hm = document.getElementById('wl-modal-le-hm').value;
  const end_hm = document.getElementById('wl-modal-end-hm').value;
  const manual_duration = document.getElementById('wl-modal-manual-dur-chk').checked;
  const time_str = document.getElementById('wl-modal-duration').value.trim();
  const comment = document.getElementById('wl-modal-comment').value.trim();
  const no_comment = document.getElementById('wl-modal-no-comment').checked;

  if (!target_issue || !date_str) {
    showToast('Informe o Ticket e a Data do lançamento.', 'error');
    return;
  }

  const btn = document.getElementById('wl-modal-save-btn');
  btn.disabled = true;
  btn.textContent = 'Salvando no Jira...';

  try {
    const endpoint = worklog_id ? '/api/worklogs/update' : '/api/worklogs/create';
    const res = await apiCall(endpoint, 'POST', {
      worklog_id,
      source_issue: source_issue || target_issue,
      target_issue,
      date_str,
      start_hm,
      lunch_start_hm,
      lunch_end_hm,
      end_hm,
      manual_duration,
      time_str,
      comment,
      no_comment
    });
    closeWorklogModal();
    showToast(res.message || 'Lançamento salvo com sucesso!', 'success');
    if (document.getElementById('tab-worklogs').classList.contains('active')) {
      await loadJiraWorklogs();
    }
    if (document.getElementById('tab-weekly').classList.contains('active')) {
      await loadWeeklyView(document.getElementById('weekly-ref-date').value);
    }
    await loadDashboard();
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Salvar Lançamento no Jira';
  }
}

async function deleteJiraWorklog(issueKey, worklogId, dateStr) {
  if (!confirm(`Confirma a EXCLUSÃO permanente do lançamento #${worklogId} do ticket ${issueKey} (${dateStr}) no Jira?`)) {
    return;
  }
  try {
    const res = await apiCall('/api/worklogs/delete', 'POST', {
      issue_key: issueKey,
      worklog_id: worklogId
    });
    showToast(res.message, 'success');
    await loadJiraWorklogs();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

/* ==================== PERFIS, CONFIGURACOES E ATUALIZACAO ==================== */
async function loadConfigData() {
  try {
    const data = await apiCall('/api/config');
    configData = data;

    document.getElementById('prof-active-select').value = data.active_profile;
    populateProfileFields(data.active_profile);

    document.getElementById('cfg-base-url').value = data.jira.base_url || '';
    document.getElementById('cfg-email').value = data.jira.email || '';
    document.getElementById('cfg-token-status').textContent = data.jira.has_token
      ? 'Token individual configurado e seguro'
      : 'Nenhum token salvo';
    document.getElementById('cfg-api-token').value = '';
    document.getElementById('cfg-default-issue').value = data.jira.default_issue || '';
    document.getElementById('cfg-default-comment').value = data.jira.default_comment || '';

    document.getElementById('cfg-lock-mode').value = data.intermediate_lock_mode || 'pause';
    document.getElementById('cfg-min-log').value = data.min_log_minutes || 15;
    document.getElementById('cfg-notifications').checked = Boolean(data.notifications_enabled);
    document.getElementById('cfg-auto-log').checked = Boolean(data.auto_log_on_exit);
    document.getElementById('cfg-autostart').checked = Boolean(data.autostart_enabled);

    document.getElementById('cfg-update-source').value = data.update_source || '';
    document.getElementById('cfg-auto-update').checked = Boolean(data.auto_update_on_start);

    if (data.version_info) {
      document.getElementById('upd-version-text').textContent = `v${data.version_info.version}`;
      document.getElementById('upd-lastmod-text').textContent = `Última modificação: ${data.version_info.last_modified}`;
      document.getElementById('upd-user-text').textContent = data.version_info.current_windows_user;
      document.getElementById('upd-config-path-text').textContent = data.version_info.user_config_file;
    }
  } catch (err) {
    showToast(err.message, 'error');
  }
}

function onProfileSelectChange() {
  const sel = document.getElementById('prof-active-select').value;
  populateProfileFields(sel);
}

function populateProfileFields(profName) {
  if (!configData || !configData.profiles) return;
  const p = configData.profiles[profName];
  if (!p) return;
  document.getElementById('prof-target-hours').value = p.target_hours;
  document.getElementById('prof-description').value = p.description || '';
  document.getElementById('win-entry-start').value = p.entry_window.start;
  document.getElementById('win-entry-end').value = p.entry_window.end;
  document.getElementById('win-ls-start').value = p.lunch_start_window.start;
  document.getElementById('win-ls-end').value = p.lunch_start_window.end;
  document.getElementById('win-le-start').value = p.lunch_end_window.start;
  document.getElementById('win-le-end').value = p.lunch_end_window.end;
  document.getElementById('win-exit-start').value = p.exit_window.start;
  document.getElementById('win-exit-end').value = p.exit_window.end;
  populateCalculatorFields(p);
}

// Mapeamento entre os campos da Calculadora de Janelas e as chaves salvas no perfil
const CALC_FIELD_MAP = [
  { hm: 'calc-entry-hm', bef: 'calc-entry-bef', aft: 'calc-entry-aft', key: 'entry', win: 'entry_window' },
  { hm: 'calc-ls-hm', bef: 'calc-ls-bef', aft: 'calc-ls-aft', key: 'lunch_start', win: 'lunch_start_window' },
  { hm: 'calc-le-hm', bef: 'calc-le-bef', aft: 'calc-le-aft', key: 'lunch_end', win: 'lunch_end_window' },
  { hm: 'calc-exit-hm', bef: 'calc-exit-bef', aft: 'calc-exit-aft', key: 'exit', win: 'exit_window' }
];

function populateCalculatorFields(p) {
  const calc = p.calculator || {};
  CALC_FIELD_MAP.forEach(f => {
    const savedHm = calc[`${f.key}_hm`];
    const savedBef = calc[`${f.key}_before`];
    const savedAft = calc[`${f.key}_after`];
    if (savedHm) {
      document.getElementById(f.hm).value = savedHm;
      if (savedBef !== undefined && savedBef !== null) document.getElementById(f.bef).value = savedBef;
      if (savedAft !== undefined && savedAft !== null) document.getElementById(f.aft).value = savedAft;
      return;
    }
    // Perfil sem calculadora salva: deriva alvo (ponto medio) e folgas (metade da largura) da janela salva
    const w = p[f.win] || {};
    const s = hmToMinutes(w.start);
    const e = hmToMinutes(w.end);
    if (s !== null && e !== null && e >= s) {
      const half = Math.floor((e - s) / 2);
      document.getElementById(f.hm).value = minutesToHM(s + half);
      document.getElementById(f.bef).value = half;
      document.getElementById(f.aft).value = (e - s) - half;
    }
  });
}

function collectCalculatorFields() {
  const calc = {};
  CALC_FIELD_MAP.forEach(f => {
    calc[`${f.key}_hm`] = document.getElementById(f.hm).value;
    calc[`${f.key}_before`] = parseInt(document.getElementById(f.bef).value || '0', 10);
    calc[`${f.key}_after`] = parseInt(document.getElementById(f.aft).value || '0', 10);
  });
  return calc;
}

function applyToleranceCalculator(silent = false) {
  const calcWin = (hmId, befId, aftId, startOutId, endOutId) => {
    const hm = document.getElementById(hmId).value;
    const bef = parseInt(document.getElementById(befId).value || '0', 10);
    const aft = parseInt(document.getElementById(aftId).value || '0', 10);
    const mins = hmToMinutes(hm);
    if (mins !== null) {
      document.getElementById(startOutId).value = minutesToHM(mins - bef);
      document.getElementById(endOutId).value = minutesToHM(mins + aft);
    }
  };
  calcWin('calc-entry-hm', 'calc-entry-bef', 'calc-entry-aft', 'win-entry-start', 'win-entry-end');
  calcWin('calc-ls-hm', 'calc-ls-bef', 'calc-ls-aft', 'win-ls-start', 'win-ls-end');
  calcWin('calc-le-hm', 'calc-le-bef', 'calc-le-aft', 'win-le-start', 'win-le-end');
  calcWin('calc-exit-hm', 'calc-exit-bef', 'calc-exit-aft', 'win-exit-start', 'win-exit-end');
  if (!silent) {
    showToast('Janelas calculadas! Clique em "Salvar Perfil e Janelas" para gravar.', 'info');
  }
}

async function saveProfileSettings() {
  const active_profile = document.getElementById('prof-active-select').value;
  const profile_data = {
    name: active_profile,
    target_hours: parseFloat(document.getElementById('prof-target-hours').value || '6.0'),
    description: document.getElementById('prof-description').value.trim(),
    entry_window: {
      start: document.getElementById('win-entry-start').value,
      end: document.getElementById('win-entry-end').value
    },
    lunch_start_window: {
      start: document.getElementById('win-ls-start').value,
      end: document.getElementById('win-ls-end').value
    },
    lunch_end_window: {
      start: document.getElementById('win-le-start').value,
      end: document.getElementById('win-le-end').value
    },
    exit_window: {
      start: document.getElementById('win-exit-start').value,
      end: document.getElementById('win-exit-end').value
    },
    calculator: collectCalculatorFields()
  };
  try {
    const res = await apiCall('/api/config', 'POST', {
      action: 'save_profile',
      active_profile,
      profile_data
    });
    showToast(res.message, 'success');
    await loadConfigData();
    await loadDashboard();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function saveGeneralSettings() {
  const payload = {
    action: 'save_general',
    base_url: document.getElementById('cfg-base-url').value.trim(),
    email: document.getElementById('cfg-email').value.trim(),
    api_token: document.getElementById('cfg-api-token').value.trim(),
    default_issue: document.getElementById('cfg-default-issue').value.trim().toUpperCase(),
    default_comment: document.getElementById('cfg-default-comment').value.trim(),
    intermediate_lock_mode: document.getElementById('cfg-lock-mode').value,
    min_log_minutes: parseInt(document.getElementById('cfg-min-log').value || '15', 10),
    notifications_enabled: document.getElementById('cfg-notifications').checked,
    auto_log_on_exit: document.getElementById('cfg-auto-log').checked,
    autostart_enabled: document.getElementById('cfg-autostart').checked,
    update_source: document.getElementById('cfg-update-source').value.trim(),
    auto_update_on_start: document.getElementById('cfg-auto-update').checked
  };
  try {
    const res = await apiCall('/api/config', 'POST', payload);
    showToast(res.message, 'success');
    await loadConfigData();
    await loadDashboard();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function checkAppUpdate() {
  const box = document.getElementById('update-status-box');
  const src = document.getElementById('cfg-update-source').value.trim();
  box.style.display = 'block';
  box.style.background = 'var(--bg-subtle)';
  box.style.color = 'var(--text-main)';
  box.textContent = 'Verificando disponibilidade de atualização...';
  try {
    const res = await apiCall('/api/update', 'POST', { action: 'check', update_source: src });
    box.style.background = res.has_update ? 'var(--info-bg)' : 'var(--success-bg)';
    box.style.color = res.has_update ? 'var(--info)' : 'var(--success)';
    box.textContent = res.message;
  } catch (err) {
    box.style.background = 'var(--danger-bg)';
    box.style.color = 'var(--danger)';
    box.textContent = err.message;
  }
}

async function runAppUpdate() {
  const box = document.getElementById('update-status-box');
  const src = document.getElementById('cfg-update-source').value.trim();
  box.style.display = 'block';
  box.style.background = 'var(--bg-subtle)';
  box.style.color = 'var(--text-main)';
  box.textContent = 'Aplicando atualização de código (preservando suas configurações pessoais)...';
  try {
    const res = await apiCall('/api/update', 'POST', { action: 'update', update_source: src });
    box.style.background = 'var(--success-bg)';
    box.style.color = 'var(--success)';
    box.textContent = res.message;
    showToast('Atualização concluída!', 'success');
    await loadConfigData();
  } catch (err) {
    box.style.background = 'var(--danger-bg)';
    box.style.color = 'var(--danger)';
    box.textContent = err.message;
  }
}

async function publishCleanRelease() {
  const targetDir = document.getElementById('publish-target-dir').value.trim();
  const box = document.getElementById('update-status-box');
  if (!targetDir) {
    showToast('Informe o caminho da pasta compartilhada de destino.', 'error');
    return;
  }
  box.style.display = 'block';
  box.style.background = 'var(--bg-subtle)';
  box.style.color = 'var(--text-main)';
  box.textContent = 'Publicando arquivos de código limpos na pasta compartilhada...';
  try {
    const res = await apiCall('/api/update', 'POST', { action: 'publish', target_dir: targetDir });
    box.style.background = 'var(--success-bg)';
    box.style.color = 'var(--success)';
    box.textContent = res.message;
    showToast('Versão limpa publicada com sucesso!', 'success');
  } catch (err) {
    box.style.background = 'var(--danger-bg)';
    box.style.color = 'var(--danger)';
    box.textContent = err.message;
  }
}

async function testJiraConnection() {
  const box = document.getElementById('test-jira-result');
  box.style.display = 'block';
  box.style.background = 'var(--bg-subtle)';
  box.style.color = 'var(--text-main)';
  box.textContent = 'Testando autenticação com a API REST do Jira...';
  try {
    const res = await apiCall('/api/test-jira', 'POST', {});
    box.style.background = res.success ? 'var(--success-bg)' : 'var(--danger-bg)';
    box.style.color = res.success ? 'var(--success)' : 'var(--danger)';
    box.innerText = res.message;
  } catch (err) {
    box.style.background = 'var(--danger-bg)';
    box.style.color = 'var(--danger)';
    box.textContent = err.message;
  }
}

/* ==================== RELATORIOS ==================== */
async function loadReport(days = 7) {
  try {
    const res = await apiCall(`/api/report?days=${days}`);
    document.getElementById('rep-total-worked').textContent = res.total_period_formatted;
    document.getElementById('rep-total-target').textContent = res.total_target_formatted;
    const balEl = document.getElementById('rep-balance');
    balEl.textContent = res.balance_formatted;
    balEl.style.color = res.balance_positive ? 'var(--success)' : 'var(--danger)';
    document.getElementById('rep-days-count').textContent = `${res.days} dias`;
    document.getElementById('rep-raw-pre').textContent = res.raw_report;

    const tbody = document.getElementById('rep-table-tbody');
    tbody.innerHTML = res.rows.map(r => {
      const ticketsHtml = r.tickets.length > 0
        ? r.tickets.map(t => `<span class="ticket-pill">${escapeHtml(t.issue_key)}</span> <small>(${t.formatted})</small>`).join(' &nbsp; ')
        : (r.is_weekend ? '<span style="color:var(--text-muted);">[Fim de Semana]</span>' : '-');
      const badgeClass = r.status_label === 'Enviado'
        ? 'badge-running'
        : (r.status_label === 'Pendente' ? 'badge-paused' : 'badge-idle');
      return `
        <tr>
          <td><strong>${r.date}</strong></td>
          <td>${r.weekday}</td>
          <td>${ticketsHtml}</td>
          <td><strong>${r.total_formatted}</strong></td>
          <td>${r.target_formatted}</td>
          <td><span class="badge ${badgeClass}">${r.status_label}</span></td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    showToast(err.message, 'error');
  }
}

/* ==================== AVISOS E NOTIFICACOES DE EXPEDIENTE ==================== */
let alertsState = null;

async function loadAlertsData() {
  try {
    const data = await apiCall('/api/alerts/status');
    alertsState = data;
    renderAlertsData(data);
  } catch (err) {
    showToast('Erro ao carregar dados de avisos: ' + err.message, 'error');
  }
}

function renderAlertsData(data) {
  if (!data) return;
  const pName = document.getElementById('alert-profile-name');
  if (pName) pName.textContent = data.profile_name || '-';
  const pDesc = document.getElementById('alert-profile-desc');
  if (pDesc) pDesc.textContent = data.profile_desc || 'Turno configurado';
  const pExit = document.getElementById('alert-planned-exit');
  if (pExit) pExit.textContent = data.planned_exit_hm || '-';
  const pExitSub = document.getElementById('alert-planned-exit-sub');
  if (pExitSub) pExitSub.textContent = `Saída nominal do perfil ${data.profile_name}`;
  const pTrig = document.getElementById('alert-trigger-time');
  if (pTrig) pTrig.textContent = data.trigger_time_hm || '-';
  const pTrigSub = document.getElementById('alert-trigger-time-sub');
  if (pTrigSub) pTrigSub.textContent = `${data.warning_minutes} min antes de ${data.planned_exit_hm}`;

  const stEl = document.getElementById('alert-today-status');
  const stSub = document.getElementById('alert-today-status-sub');
  if (stEl && stSub) {
    if (!data.warning_enabled) {
      stEl.textContent = 'Desativado';
      stEl.style.color = 'var(--text-muted)';
      stSub.textContent = 'Avisos desligados na configuração';
    } else if (data.fired_today) {
      stEl.textContent = 'Já Disparado Hoje';
      stEl.style.color = 'var(--accent)';
      stSub.textContent = `Aviso acionado próximo a ${data.trigger_time_hm}`;
    } else {
      stEl.textContent = 'Aguardando Turno';
      stEl.style.color = 'var(--success)';
      stSub.textContent = `Disparará em torno de ${data.trigger_time_hm}`;
    }
  }

  const enabledChk = document.getElementById('cfg-alert-enabled');
  if (enabledChk) enabledChk.checked = Boolean(data.warning_enabled);
  const minInp = document.getElementById('cfg-alert-minutes');
  if (minInp) minInp.value = data.warning_minutes || 5;
  const popChk = document.getElementById('cfg-alert-popup');
  if (popChk) popChk.checked = Boolean(data.warning_popup);
  const toastChk = document.getElementById('cfg-alert-toast');
  if (toastChk) toastChk.checked = Boolean(data.notifications_enabled);

  onAlertEnabledChange();
  updateAlertCalculationHint();
  highlightQuickMinuteButton(data.warning_minutes);
}

function onAlertEnabledChange() {
  const enabledChk = document.getElementById('cfg-alert-enabled');
  const enabled = enabledChk ? enabledChk.checked : true;
  const ctrls = document.getElementById('alert-settings-controls');
  if (ctrls) {
    ctrls.style.opacity = enabled ? '1' : '0.45';
    ctrls.style.pointerEvents = enabled ? 'auto' : 'none';
  }
}

function highlightQuickMinuteButton(mins) {
  const segs = document.querySelectorAll('#tab-alerts .seg-btn');
  segs.forEach(btn => {
    const val = parseInt(btn.textContent, 10);
    if (val === parseInt(mins, 10)) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });
}

function setAlertMinutesQuick(mins) {
  const minInp = document.getElementById('cfg-alert-minutes');
  if (minInp) minInp.value = mins;
  highlightQuickMinuteButton(mins);
  updateAlertCalculationHint();
}

function onAlertMinutesInput() {
  const minInp = document.getElementById('cfg-alert-minutes');
  const minVal = parseInt(minInp ? minInp.value : '5', 10);
  highlightQuickMinuteButton(minVal);
  updateAlertCalculationHint();
}

function updateAlertCalculationHint() {
  const hintEl = document.getElementById('alert-calculation-hint');
  if (!hintEl) return;
  const minInp = document.getElementById('cfg-alert-minutes');
  const mins = parseInt(minInp ? minInp.value : '5', 10);
  const plannedHm = alertsState ? alertsState.planned_exit_hm : (document.getElementById('alert-planned-exit').textContent || '15:15');
  const planMinutes = hmToMinutes(plannedHm);
  if (planMinutes !== null && !isNaN(mins)) {
    const triggerMin = (planMinutes - mins + 1440) % 1440;
    const triggerHm = minutesToHM(triggerMin);
    hintEl.innerHTML = `Com saída planejada às <strong>${plannedHm}</strong>, o aviso disparará às <strong>${triggerHm}</strong> (${mins} minutos antes).`;
    const trigVal = document.getElementById('alert-trigger-time');
    if (trigVal) trigVal.textContent = triggerHm;
  } else {
    hintEl.textContent = '';
  }
}

async function saveAlertConfig() {
  const enabledChk = document.getElementById('cfg-alert-enabled');
  const enabled = enabledChk ? enabledChk.checked : true;
  const minInp = document.getElementById('cfg-alert-minutes');
  const minutes = parseInt(minInp ? minInp.value : '5', 10);
  const popChk = document.getElementById('cfg-alert-popup');
  const popup = popChk ? popChk.checked : true;
  const toastChk = document.getElementById('cfg-alert-toast');
  const toast = toastChk ? toastChk.checked : true;

  if (isNaN(minutes) || minutes < 1 || minutes > 60) {
    showToast('Informe uma antecedência entre 1 e 60 minutos.', 'error');
    return;
  }

  try {
    const res = await apiCall('/api/alerts/config', 'POST', {
      exit_warning_enabled: enabled,
      exit_warning_minutes: minutes,
      exit_warning_popup: popup,
      notifications_enabled: toast
    });
    showToast(res.message || 'Configurações de avisos gravadas com sucesso!', 'success');
    if (res.data) {
      alertsState = res.data;
      renderAlertsData(res.data);
    } else {
      await loadAlertsData();
    }
  } catch (err) {
    showToast('Erro ao salvar avisos: ' + err.message, 'error');
  }
}

async function testExitAlert() {
  try {
    showToast('Disparando janela de aviso pré-saída na sua tela...', 'info');
    const res = await apiCall('/api/alerts/test', 'POST', {});
    showToast(res.message || 'Janela de aviso disparada!', 'success');
  } catch (err) {
    showToast('Erro ao disparar aviso de teste: ' + err.message, 'error');
  }
}

async function refreshAll() {
  await loadDashboard(true);
  if (document.getElementById('tab-weekly').classList.contains('active')) {
    await loadWeeklyView(document.getElementById('weekly-ref-date').value);
  }
  if (document.getElementById('tab-worklogs').classList.contains('active')) {
    await loadJiraWorklogs();
  }
  showToast('Dados atualizados!', 'info');
}

window.addEventListener('DOMContentLoaded', () => {
  loadDashboard(true);
  setInterval(() => {
    loadDashboard(false);
  }, 5000);
});

/*__UI_FX_JS__*/

/*__ANALYTICS_JS__*/
</script>
</body>
</html>
"""

HTML_PAGE = (
    HTML_PAGE.replace("/*__THEME_CSS__*/", THEME_CSS)
    .replace("/*__EARLY_JS__*/", EARLY_JS)
    .replace("/*__UI_FX_JS__*/", UI_FX_JS)
    .replace("/*__ANALYTICS_JS__*/", ANALYTICS_JS)
    .replace("__LOGO_SVG__", LOGO_SVG)
)


class JiraBotWebHandler(BaseHTTPRequestHandler):
    """Handler HTTP para servir a Single-Page Application e os endpoints JSON da API local."""

    def log_message(self, format: str, *args: Any) -> None:
        logger.debug("%s - %s", self.address_string(), format % args)

    def _send_json(self, data: Dict[str, Any], status_code: int = 200) -> None:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        try:
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(payload)
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass

    def _send_html(self, html: str, status_code: int = 200) -> None:
        payload = html.encode("utf-8")
        try:
            self.send_response(status_code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(payload)
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass

    def _send_svg(self, svg: str) -> None:
        payload = svg.encode("utf-8")
        try:
            self.send_response(200)
            self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "public, max-age=3600")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(payload)
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass

    def _read_json_body(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw) if raw else {}

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        try:
            if path in ["/", "/index.html"]:
                self._send_html(HTML_PAGE)
                return

            if path in ["/favicon.svg", "/favicon.ico", "/logo.svg"]:
                self._send_svg(LOGO_SVG)
                return

            if path == "/api/analytics":
                start = (query.get("start", query.get("start_date", [""]))[0] or "").strip()
                end = (query.get("end", query.get("end_date", [""]))[0] or "").strip()
                days_raw = (query.get("days", ["30"])[0] or "30").strip()
                force = (query.get("refresh", ["0"])[0] == "1")
                if start and end:
                    self._send_json(get_analytics(start_date=start, end_date=end, force=force))
                else:
                    self._send_json(get_analytics(days=normalize_days(days_raw), force=force))
                return

            if path == "/api/status":
                self._send_json(build_dashboard_payload())
                return

            if path == "/api/alerts/status":
                self._send_json(build_alerts_payload())
                return

            if path == "/api/config":
                cfg = BotConfig.load()
                data = cfg.to_dict()
                # Protecao estrita: nunca expor api_token na resposta HTTP
                has_token = bool(cfg.jira.get_clean_token())
                data["jira"]["api_token"] = ""
                data["jira"]["has_token"] = has_token
                data["autostart_enabled"] = is_autostart_enabled()
                data["version_info"] = get_version_info()
                self._send_json(data)
                return

            if path == "/api/report":
                days = int(query.get("days", ["7"])[0])
                self._send_json(build_report_payload(days=days))
                return

            if path == "/api/weekly":
                ref_date = (query.get("ref_date", [""])[0] or "").strip()
                fetch_jira = (query.get("fetch_jira", ["1"])[0] != "0")
                self._send_json(build_weekly_payload(ref_date_str=ref_date, fetch_jira=fetch_jira))
                return

            if path == "/api/worklogs/range":
                s_date = (query.get("start_date", [""])[0] or "").strip()
                e_date = (query.get("end_date", [""])[0] or "").strip()
                cfg = BotConfig.load()
                state_mgr = StateManager()
                client = JiraClient(cfg.jira, state_mgr)
                worklogs = client.get_user_worklogs_by_date_range(s_date, e_date)
                self._send_json({"worklogs": worklogs})
                return

            if path == "/api/worklogs":
                days = int(query.get("days", ["14"])[0])
                issue_filter = (query.get("issue_key", [""])[0] or "").strip().upper()

                cfg = BotConfig.load()
                state_mgr = StateManager()
                client = JiraClient(cfg.jira, state_mgr)

                if issue_filter:
                    worklogs = client.get_formatted_issue_worklogs(issue_filter)
                else:
                    worklogs = client.get_user_recent_worklogs(days=days)

                is_8h = cfg.active_profile == "8h"
                def_ls = "12:00"
                def_le = "13:00" if is_8h else "13:30"

                for w in worklogs:
                    sec = int(w.get("time_spent_seconds", 0) or 0)
                    w["time_formatted"] = format_duration(sec)
                    w["hm_formatted"] = format_hm_from_seconds(sec)
                    w["schedule"] = state_mgr.get_or_infer_worklog_schedule(
                        w, default_lunch_start=def_ls, default_lunch_end=def_le
                    )

                self._send_json({"worklogs": worklogs})
                return

            self._send_json({"error": "Rota não encontrada"}, status_code=404)
        except Exception as e:
            logger.exception("Erro em GET %s", path)
            self._send_json({"error": str(e)}, status_code=500)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        try:
            body = self._read_json_body()

            if path == "/api/theme":
                theme = body.get("theme", "dark")
                cfg = BotConfig.load()
                cfg.theme = "light" if theme == "light" else "dark"
                cfg.save()
                self._send_json({"success": True, "theme": cfg.theme})
                return

            if path == "/api/update":
                action = body.get("action", "check")
                if action == "check":
                    res = check_for_updates(body.get("update_source"))
                    self._send_json(res)
                    return
                if action == "update":
                    res = perform_update(body.get("update_source"))
                    if not res.get("success"):
                        self._send_json({"error": res.get("message", "Falha ao atualizar")}, status_code=400)
                        return
                    self._send_json(res)
                    return
                if action == "publish":
                    res = publish_clean_release(body.get("target_dir", ""))
                    if not res.get("success"):
                        self._send_json({"error": res.get("message", "Falha ao publicar")}, status_code=400)
                        return
                    self._send_json(res)
                    return

            if path == "/api/service":
                action = body.get("action", "")
                cfg = BotConfig.load()
                state_mgr = StateManager()
                engine = BotEngine(config=cfg, state_manager=state_mgr)

                if action == "start_daemon":
                    pid = start_background()
                    self._send_json({"success": True, "message": f"Serviço iniciado em background (PID: {pid})."})
                elif action == "stop_daemon":
                    stop_background()
                    self._send_json({"success": True, "message": "Serviço em background encerrado."})
                elif action == "restart_daemon":
                    pid = restart_background()
                    self._send_json({"success": True, "message": f"Serviço reiniciado com sucesso (Novo PID: {pid})."})
                elif action == "manual_start":
                    engine.manual_start()
                    self._send_json({"success": True, "message": "Cronômetro iniciado/retomado com sucesso."})
                elif action == "manual_pause":
                    engine.manual_pause()
                    self._send_json({"success": True, "message": "Cronômetro pausado."})
                elif action == "simulate_lock":
                    st = engine.handle_lock()
                    self._send_json({"success": True, "message": f"Evento LOCK processado. Novo estado: {st.status}."})
                elif action == "simulate_unlock":
                    st = engine.handle_unlock()
                    self._send_json({"success": True, "message": f"Evento UNLOCK processado. Novo estado: {st.status}."})
                elif action == "test_popup":
                    show_pre_exit_popup(state_mgr, force=True)
                    self._send_json({"success": True, "message": "Janela gráfica de revisão pré-saída disparada."})
                elif action == "flush_queue":
                    client = JiraClient(cfg.jira, state_mgr)
                    count = client.flush_queue()
                    self._send_json({"success": True, "message": f"{count} item(ns) sincronizado(s) com o Jira."})
                elif action == "delete_queue_item":
                    item_id = body.get("item_id", "")
                    state_mgr.remove_from_queue(item_id)
                    self._send_json({"success": True, "message": "Item removido da fila offline."})
                else:
                    self._send_json({"error": f"Ação desconhecida: {action}"}, status_code=400)
                return

            if path == "/api/today/schedule":
                cfg = BotConfig.load()
                state_mgr = StateManager()
                state = state_mgr.load_state()
                res = state.apply_shift_schedule(
                    start_hm=body.get("start_hm", ""),
                    lunch_start_hm=body.get("lunch_start_hm", ""),
                    lunch_end_hm=body.get("lunch_end_hm", ""),
                    end_hm=body.get("end_hm", ""),
                    default_issue=cfg.jira.default_issue,
                )
                if not res.get("success"):
                    self._send_json({"error": res.get("message", "Horário inválido")}, status_code=400)
                    return
                state_mgr.save_state(state)
                dur_str = format_duration(state.get_total_seconds())
                self._send_json({
                    "success": True,
                    "message": f"Horários do expediente atualizados! Tempo líquido calculado: {dur_str}.",
                })
                return

            if path == "/api/today/intervals":
                action = body.get("action", "")
                cfg = BotConfig.load()
                state_mgr = StateManager()
                state = state_mgr.load_state()
                active_issue = (body.get("issue_key") or state.target_issue or cfg.jira.default_issue).strip().upper()

                if action in ["add", "update"]:
                    st_dt = _parse_hm(state.date_str, body.get("start_hm", ""))
                    en_dt = _parse_hm(state.date_str, body.get("end_hm", ""))
                    if not st_dt:
                        self._send_json({"error": "Horário de início inválido."}, status_code=400)
                        return
                    if en_dt and en_dt < st_dt:
                        self._send_json({"error": "Horário de fim não pode ser anterior ao início."}, status_code=400)
                        return

                    new_inter = TimeInterval(
                        start=st_dt.isoformat(),
                        end=en_dt.isoformat() if en_dt else None,
                        issue_key=active_issue,
                        comment=(body.get("comment") or "").strip() or None,
                    )
                    if action == "add":
                        state.intervals.append(new_inter)
                        msg = "Novo intervalo adicionado ao dia de hoje."
                    else:
                        idx = int(body.get("index", -1))
                        if 0 <= idx < len(state.intervals):
                            state.intervals[idx] = new_inter
                            msg = f"Intervalo #{idx + 1} atualizado com sucesso."
                        else:
                            self._send_json({"error": "Índice de intervalo inválido."}, status_code=400)
                            return

                    state.intervals.sort(key=lambda x: x.start)
                    if any(i.end is None for i in state.intervals):
                        state.status = "RUNNING"
                    state_mgr.save_state(state)
                    self._send_json({"success": True, "message": msg})
                    return

                if action == "delete":
                    idx = int(body.get("index", -1))
                    if 0 <= idx < len(state.intervals):
                        state.intervals.pop(idx)
                        state_mgr.save_state(state)
                        self._send_json({"success": True, "message": f"Intervalo #{idx + 1} excluído."})
                    else:
                        self._send_json({"error": "Índice de intervalo inválido."}, status_code=400)
                    return

            if path == "/api/today/ticket":
                action = body.get("action", "")
                cfg = BotConfig.load()
                state_mgr = StateManager()
                client = JiraClient(cfg.jira, state_mgr)

                if action == "switch":
                    issue_key = (body.get("issue_key") or "").strip().upper()
                    comment = (body.get("comment") or "").strip()
                    engine = BotEngine(config=cfg, state_manager=state_mgr)
                    engine.switch_ticket(issue_key, comment=comment if comment else None)
                    self._send_json({"success": True, "message": f"Ticket ativo alterado para {issue_key}."})
                    return

                if action == "set_comment":
                    issue_key = (body.get("issue_key") or "").strip().upper()
                    comment = (body.get("comment") or "").strip()
                    state = state_mgr.load_state()
                    state.no_comment = bool(body.get("no_comment", False))
                    if issue_key:
                        state.set_issue_comment(issue_key, comment)
                    state_mgr.save_state(state)
                    self._send_json({"success": True, "message": f"Descrição de {issue_key} atualizada."})
                    return

                if action == "toggle_no_comment":
                    state = state_mgr.load_state()
                    state.no_comment = bool(body.get("no_comment", False))
                    state_mgr.save_state(state)
                    msg = "Configurado para enviar SEM descrição." if state.no_comment else "Envio de descrição reativado."
                    self._send_json({"success": True, "message": msg})
                    return

                if action == "transfer":
                    src = (body.get("source_issue") or "").strip().upper()
                    tgt = (body.get("target_issue") or "").strip().upper()
                    t_str = (body.get("time_str") or "").strip()
                    sec = parse_duration_input(t_str) if t_str else None
                    engine = BotEngine(config=cfg, state_manager=state_mgr)
                    transferred = engine.transfer_today_hours(source_issue=src, target_issue=tgt, seconds=sec)
                    if transferred <= 0:
                        self._send_json({"error": f"Nenhuma hora disponível em {src} para transferir hoje."}, status_code=400)
                        return
                    self._send_json({
                        "success": True,
                        "message": f"Transferido {format_duration(transferred)} de {src} para {tgt}.",
                    })
                    return

                if action == "log_now":
                    no_comment = bool(body.get("no_comment", False))
                    created_ids: List[str] = []
                    state_before = state_mgr.load_state()
                    shift_summary = state_before.get_shift_times_summary()

                    def _on_trigger(issue: str, sec: int, start_iso: str, comm: Optional[str] = None) -> bool:
                        res = client.submit_worklog(
                            issue_key=issue,
                            time_spent_seconds=sec,
                            started_iso=start_iso,
                            comment="" if comm == "__EMPTY__" else comm,
                            no_comment=(comm == "__EMPTY__"),
                        )
                        if res.get("status") == "success":
                            wid = str(res.get("worklog_id", ""))
                            if wid:
                                created_ids.append(wid)
                                state_mgr.save_worklog_schedule(wid, shift_summary)
                            return True
                        return False

                    engine = BotEngine(config=cfg, state_manager=state_mgr, on_worklog_trigger=_on_trigger)
                    total_sec = engine.manual_log(no_comment=no_comment)
                    self._send_json({
                        "success": True,
                        "message": f"Lançamento concluído! Total processado: {format_duration(total_sec)}.",
                        "worklog_ids": created_ids,
                    })
                    return

            # Criacao em Lote (Multiplos Dias / Semanas / Multiplos Tickets)
            if path == "/api/worklogs/batch-create":
                cfg = BotConfig.load()
                state_mgr = StateManager()
                client = JiraClient(cfg.jira, state_mgr)

                entries = body.get("entries", [])
                no_comment = bool(body.get("no_comment", False))
                if not entries:
                    self._send_json({"error": "Nenhum lançamento informado no lote."}, status_code=400)
                    return

                success_count = 0
                days_launched: set[str] = set()
                tickets_launched: List[str] = []
                errors: List[str] = []
                fallback_cache: Dict[str, str] = {}

                for item in entries:
                    d_str = (item.get("date") or "")[:10]
                    issue_key = (item.get("issue_key") or cfg.jira.default_issue or "ATIVDIV-32").strip().upper()
                    start_hm = (item.get("start_hm") or "07:45").strip()
                    ls_hm = (item.get("lunch_start_hm") or "").strip()
                    le_hm = (item.get("lunch_end_hm") or "").strip()
                    end_hm = (item.get("end_hm") or "15:15").strip()
                    raw_comment = (item.get("comment") or "").strip()

                    # Se o intervalo [start_hm, end_hm] ocorre inteiramente antes ou depois do almoco, ignora o almoco
                    st_dt_chk = _parse_hm(d_str, start_hm)
                    ls_dt_chk = _parse_hm(d_str, ls_hm)
                    le_dt_chk = _parse_hm(d_str, le_hm)
                    en_dt_chk = _parse_hm(d_str, end_hm)
                    if st_dt_chk and ls_dt_chk and le_dt_chk and en_dt_chk and en_dt_chk >= st_dt_chk and ls_dt_chk <= le_dt_chk:
                        if en_dt_chk <= ls_dt_chk or st_dt_chk >= le_dt_chk:
                            ls_hm = ""
                            le_hm = ""

                    calc = calculate_shift_schedule(
                        date_str=d_str,
                        start_hm=start_hm,
                        lunch_start_hm=ls_hm,
                        lunch_end_hm=le_hm,
                        end_hm=end_hm,
                        issue_key=issue_key,
                        comment=raw_comment,
                    )
                    if not calc.get("success") or int(calc.get("total_seconds", 0)) <= 0:
                        errors.append(f"{d_str} ({issue_key}): Horários inválidos")
                        continue

                    sec = int(calc["total_seconds"])
                    started_iso = calc["started_iso"]

                    if no_comment:
                        final_comment = ""
                    elif raw_comment:
                        final_comment = raw_comment
                    else:
                        if issue_key not in fallback_cache:
                            fallback_cache[issue_key] = get_fallback_description(issue_key, client)
                        final_comment = fallback_cache[issue_key]

                    try:
                        res = client.submit_worklog(
                            issue_key=issue_key,
                            time_spent_seconds=sec,
                            started_iso=started_iso,
                            comment=final_comment,
                            no_comment=no_comment,
                        )
                        wid = str(res.get("worklog_id", ""))
                        if wid:
                            state_mgr.save_worklog_schedule(wid, {
                                "start_hm": start_hm,
                                "lunch_start_hm": ls_hm,
                                "lunch_end_hm": le_hm,
                                "end_hm": end_hm,
                            })
                        success_count += 1
                        days_launched.add(d_str)
                        if issue_key not in tickets_launched:
                            tickets_launched.append(issue_key)
                    except Exception as e:
                        errors.append(f"{d_str} ({issue_key}): {e}")

                if success_count == 0 and errors:
                    self._send_json({"error": f"Falha ao lançar lote: {'; '.join(errors[:3])}"}, status_code=400)
                    return

                tickets_str = ", ".join(tickets_launched) if tickets_launched else "-"
                msg = (
                    f"Lote concluído! {success_count} de {len(entries)} apontamento(s) lançado(s) com sucesso "
                    f"em {len(days_launched)} dia(s) (Tickets: {tickets_str})."
                )
                if errors:
                    msg += f" ({len(errors)} falha(s): {'; '.join(errors[:2])})"
                self._send_json({
                    "success": True,
                    "created_count": success_count,
                    "days_count": len(days_launched),
                    "tickets": tickets_launched,
                    "errors": errors,
                    "message": msg,
                })
                return

            # Edicao / Migracao em Lote de Worklogs Selecionados
            if path == "/api/worklogs/batch-update":
                cfg = BotConfig.load()
                state_mgr = StateManager()
                client = JiraClient(cfg.jira, state_mgr)

                items = body.get("items", [])
                apply_ticket = bool(body.get("apply_ticket", False))
                target_issue = (body.get("target_issue") or "").strip().upper()
                apply_schedule = bool(body.get("apply_schedule", False))
                start_hm = (body.get("start_hm") or "07:45").strip()
                ls_hm = (body.get("lunch_start_hm") or "").strip()
                le_hm = (body.get("lunch_end_hm") or "").strip()
                end_hm = (body.get("end_hm") or "15:15").strip()
                apply_comment = bool(body.get("apply_comment", False))
                new_comment = (body.get("comment") or "").strip()

                updated_count = 0
                errors = []

                for it in items:
                    wid = str(it.get("worklog_id") or "").strip()
                    src_issue = (it.get("source_issue") or "").strip().upper()
                    d_str = (it.get("date_str") or date.today().isoformat())[:10]
                    if not wid or not src_issue:
                        continue

                    sec_to_use: Optional[int] = None
                    started_to_use: Optional[str] = None
                    if apply_schedule:
                        calc = calculate_shift_schedule(
                            date_str=d_str,
                            start_hm=start_hm,
                            lunch_start_hm=ls_hm,
                            lunch_end_hm=le_hm,
                            end_hm=end_hm,
                            issue_key=target_issue if apply_ticket else src_issue,
                        )
                        if not calc.get("success") or int(calc.get("total_seconds", 0)) <= 0:
                            errors.append(f"#{wid}: Horários inválidos")
                            continue
                        sec_to_use = int(calc["total_seconds"])
                        started_to_use = calc["started_iso"]

                    comm_to_use: Optional[str] = new_comment if apply_comment else None
                    dest_issue = target_issue if (apply_ticket and target_issue) else src_issue

                    if dest_issue != src_issue:
                        mig = client.migrate_worklog(
                            source_issue=src_issue,
                            target_issue=dest_issue,
                            worklog_id=wid,
                            override_seconds=sec_to_use,
                            override_started_iso=started_to_use,
                            override_comment=comm_to_use,
                        )
                        if mig.get("success"):
                            new_id = str(mig.get("new_worklog_id") or wid)
                            if apply_schedule:
                                state_mgr.delete_worklog_schedule(wid)
                                state_mgr.save_worklog_schedule(new_id, {
                                    "start_hm": start_hm,
                                    "lunch_start_hm": ls_hm,
                                    "lunch_end_hm": le_hm,
                                    "end_hm": end_hm,
                                })
                            updated_count += 1
                        else:
                            errors.append(f"#{wid}: {mig.get('message')}")
                    else:
                        upd = client.update_worklog_full(
                            issue_key=src_issue,
                            worklog_id=wid,
                            time_spent_seconds=sec_to_use,
                            started_iso=started_to_use,
                            comment=comm_to_use,
                        )
                        if upd.get("success"):
                            if apply_schedule:
                                state_mgr.save_worklog_schedule(wid, {
                                    "start_hm": start_hm,
                                    "lunch_start_hm": ls_hm,
                                    "lunch_end_hm": le_hm,
                                    "end_hm": end_hm,
                                })
                            updated_count += 1
                        else:
                            errors.append(f"#{wid}: {upd.get('message')}")

                if updated_count == 0 and errors:
                    self._send_json({"error": f"Falha na edição em lote: {'; '.join(errors[:3])}"}, status_code=400)
                    return
                self._send_json({
                    "success": True,
                    "updated_count": updated_count,
                    "message": f"Edição em lote concluída! {updated_count} de {len(items)} lançamento(s) atualizado(s).",
                })
                return

            # Exclusao em Lote
            if path == "/api/worklogs/batch-delete":
                cfg = BotConfig.load()
                state_mgr = StateManager()
                client = JiraClient(cfg.jira, state_mgr)
                items = body.get("items", [])
                deleted_count = 0
                for it in items:
                    wid = str(it.get("worklog_id") or "").strip()
                    iss = (it.get("issue_key") or "").strip().upper()
                    if wid and iss and client.delete_worklog(iss, wid):
                        state_mgr.delete_worklog_schedule(wid)
                        deleted_count += 1
                self._send_json({
                    "success": True,
                    "deleted_count": deleted_count,
                    "message": f"{deleted_count} de {len(items)} lançamento(s) excluído(s) do Jira com sucesso.",
                })
                return

            if path in ["/api/worklogs/create", "/api/worklogs/update"]:
                cfg = BotConfig.load()
                state_mgr = StateManager()
                client = JiraClient(cfg.jira, state_mgr)

                worklog_id = (body.get("worklog_id") or "").strip()
                source_issue = (body.get("source_issue") or "").strip().upper()
                target_issue = (body.get("target_issue") or "").strip().upper()
                date_str = (body.get("date_str") or date.today().isoformat())[:10]
                start_hm = (body.get("start_hm") or "08:00").strip()
                lunch_start_hm = (body.get("lunch_start_hm") or "").strip()
                lunch_end_hm = (body.get("lunch_end_hm") or "").strip()
                end_hm = (body.get("end_hm") or "").strip()
                manual_duration = bool(body.get("manual_duration", False))
                time_str = (body.get("time_str") or "").strip()
                no_comment = bool(body.get("no_comment", False))
                comment = "" if no_comment else (body.get("comment") or "").strip()

                schedule_meta = {
                    "start_hm": start_hm,
                    "lunch_start_hm": lunch_start_hm,
                    "lunch_end_hm": lunch_end_hm,
                    "end_hm": end_hm,
                }

                if not manual_duration and start_hm and end_hm:
                    calc = calculate_shift_schedule(
                        date_str=date_str,
                        start_hm=start_hm,
                        lunch_start_hm=lunch_start_hm,
                        lunch_end_hm=lunch_end_hm,
                        end_hm=end_hm,
                        issue_key=target_issue,
                        comment=comment,
                    )
                    if not calc.get("success"):
                        self._send_json({"error": calc.get("message", "Horários inválidos.")}, status_code=400)
                        return
                    total_seconds = int(calc["total_seconds"])
                    started_iso = calc["started_iso"]
                else:
                    total_seconds = parse_duration_input(time_str) or 0
                    st_dt = _parse_hm(date_str, start_hm or "08:00") or datetime.now()
                    started_iso = st_dt.isoformat()

                if total_seconds <= 0:
                    self._send_json({"error": "O tempo total líquido deve ser maior que zero."}, status_code=400)
                    return

                if path == "/api/worklogs/create":
                    if not no_comment and not comment:
                        comment = get_fallback_description(target_issue, client)
                    res = client.submit_worklog(
                        issue_key=target_issue,
                        time_spent_seconds=total_seconds,
                        started_iso=started_iso,
                        comment=comment,
                        no_comment=no_comment,
                    )
                    new_id = str(res.get("worklog_id", ""))
                    if new_id:
                        state_mgr.save_worklog_schedule(new_id, schedule_meta)
                    self._send_json({
                        "success": True,
                        "worklog_id": new_id,
                        "message": f"Worklog lançado com sucesso em {target_issue} ({format_duration(total_seconds)})!",
                    })
                    return

                if not worklog_id:
                    self._send_json({"error": "ID do worklog não informado."}, status_code=400)
                    return

                if source_issue and target_issue and source_issue != target_issue:
                    mig = client.migrate_worklog(
                        source_issue=source_issue,
                        target_issue=target_issue,
                        worklog_id=worklog_id,
                        override_seconds=total_seconds,
                        override_started_iso=started_iso,
                        override_comment=comment,
                    )
                    if not mig.get("success"):
                        self._send_json({"error": mig.get("message", "Falha ao migrar ticket.")}, status_code=400)
                        return
                    new_id = str(mig.get("new_worklog_id") or worklog_id)
                    state_mgr.delete_worklog_schedule(worklog_id)
                    state_mgr.save_worklog_schedule(new_id, schedule_meta)
                    self._send_json({
                        "success": True,
                        "worklog_id": new_id,
                        "message": mig.get("message", f"Lançamento migrado para {target_issue} e atualizado!"),
                    })
                    return
                else:
                    upd = client.update_worklog_full(
                        issue_key=target_issue,
                        worklog_id=worklog_id,
                        time_spent_seconds=total_seconds,
                        started_iso=started_iso,
                        comment=comment,
                    )
                    if not upd.get("success"):
                        self._send_json({"error": upd.get("message", "Falha ao atualizar worklog.")}, status_code=400)
                        return
                    state_mgr.save_worklog_schedule(worklog_id, schedule_meta)
                    self._send_json({
                        "success": True,
                        "worklog_id": worklog_id,
                        "message": f"Lançamento #{worklog_id} ({target_issue}) atualizado com sucesso!",
                    })
                    return

            if path == "/api/worklogs/delete":
                issue_key = (body.get("issue_key") or "").strip().upper()
                worklog_id = str(body.get("worklog_id") or "").strip()
                if not issue_key or not worklog_id:
                    self._send_json({"error": "Ticket e ID do worklog são obrigatórios."}, status_code=400)
                    return
                cfg = BotConfig.load()
                state_mgr = StateManager()
                client = JiraClient(cfg.jira, state_mgr)
                ok = client.delete_worklog(issue_key, worklog_id)
                if not ok:
                    self._send_json({"error": f"Não foi possível excluir o worklog {worklog_id} no Jira."}, status_code=400)
                    return
                state_mgr.delete_worklog_schedule(worklog_id)
                self._send_json({
                    "success": True,
                    "message": f"Lançamento #{worklog_id} excluído de {issue_key} com sucesso.",
                })
                return

            if path == "/api/config":
                action = body.get("action", "")
                cfg = BotConfig.load()

                if action == "save_profile":
                    active_prof = body.get("active_profile", cfg.active_profile)
                    p_data = body.get("profile_data", {})
                    if p_data:
                        prof = ShiftProfile.from_dict(p_data)
                        cfg.profiles[active_prof] = prof
                    cfg.active_profile = active_prof
                    cfg.save()
                    self._send_json({"success": True, "message": f"Perfil '{active_prof}' salvo e ativado com sucesso!"})
                    return

                if action == "save_general":
                    if body.get("base_url"):
                        cfg.jira.base_url = body["base_url"].strip().rstrip("/")
                    if "email" in body:
                        cfg.jira.email = body["email"].strip()
                    if body.get("api_token"):
                        cfg.jira.api_token = body["api_token"].strip()
                    if body.get("default_issue"):
                        cfg.jira.default_issue = body["default_issue"].strip().upper()
                    if "default_comment" in body:
                        cfg.jira.default_comment = body["default_comment"].strip()
                    if body.get("intermediate_lock_mode") in ["pause", "ignore"]:
                        cfg.intermediate_lock_mode = body["intermediate_lock_mode"]
                    if "min_log_minutes" in body:
                        cfg.min_log_minutes = int(body["min_log_minutes"])
                    if "notifications_enabled" in body:
                        cfg.notifications_enabled = bool(body["notifications_enabled"])
                    if "auto_log_on_exit" in body:
                        cfg.auto_log_on_exit = bool(body["auto_log_on_exit"])
                    if "exit_warning_enabled" in body:
                        cfg.exit_warning_enabled = bool(body["exit_warning_enabled"])
                    if "exit_warning_minutes" in body:
                        cfg.exit_warning_minutes = max(1, min(60, int(body["exit_warning_minutes"])))
                    if "exit_warning_popup" in body:
                        cfg.exit_warning_popup = bool(body["exit_warning_popup"])
                    if "update_source" in body:
                        cfg.update_source = body["update_source"].strip()
                    if "auto_update_on_start" in body:
                        cfg.auto_update_on_start = bool(body["auto_update_on_start"])

                    cfg.save()

                    if "autostart_enabled" in body:
                        from cli import set_windows_autostart
                        set_windows_autostart(bool(body["autostart_enabled"]))

                    self._send_json({"success": True, "message": "Configurações gravadas com sucesso!"})
                    return

            if path == "/api/alerts/test":
                state_mgr = StateManager()
                show_pre_exit_popup(state_mgr, force=True)
                self._send_json({"success": True, "message": "Janela gráfica de aviso pré-saída disparada com sucesso."})
                return

            if path == "/api/alerts/config":
                cfg = BotConfig.load()
                if "exit_warning_enabled" in body:
                    cfg.exit_warning_enabled = bool(body["exit_warning_enabled"])
                if "exit_warning_minutes" in body:
                    cfg.exit_warning_minutes = max(1, min(60, int(body["exit_warning_minutes"])))
                if "exit_warning_popup" in body:
                    cfg.exit_warning_popup = bool(body["exit_warning_popup"])
                if "notifications_enabled" in body:
                    cfg.notifications_enabled = bool(body["notifications_enabled"])
                cfg.save()
                self._send_json({
                    "success": True,
                    "message": "Configurações de avisos de expediente gravadas com sucesso!",
                    "data": build_alerts_payload(),
                })
                return

            if path == "/api/test-jira":
                cfg = BotConfig.load()
                client = JiraClient(cfg.jira)
                res = client.test_connection()
                self._send_json(res)
                return

            self._send_json({"error": "Rota POST não encontrada"}, status_code=404)
        except Exception as e:
            logger.exception("Erro em POST %s", path)
            self._send_json({"error": str(e)}, status_code=500)


def is_port_in_use(port: int = 8765) -> bool:
    """Verifica se ja existe um servidor ativo escutando na porta local."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def start_embedded_web_server(port: int = 8765) -> Optional[ReusableThreadingHTTPServer]:
    """
    Inicia o servidor HTTP do Painel Web em uma thread daemon embutida (usada pelo daemon.py).
    Retorna a instancia do servidor ou None se a porta ja estiver em uso.
    """
    if is_port_in_use(port):
        logger.info(f"Servidor Web ja esta ativo na porta {port}.")
        return None
    try:
        server = ReusableThreadingHTTPServer(("127.0.0.1", port), JiraBotWebHandler)
        t = threading.Thread(target=server.serve_forever, name="JiraBotWebServerThread", daemon=True)
        t.start()
        logger.info(f"Servidor Web do JiraBot iniciado em background em http://127.0.0.1:{port}")
        return server
    except Exception as e:
        logger.warning(f"Erro ao iniciar servidor Web embutido na porta {port}: {e}")
        return None


def ensure_background_web_server(port: int = 8765) -> str:
    """
    Garante que o servidor do Painel Web esteja rodando de forma persistente em background
    (mesmo que o usuario feche o terminal) e retorna a URL de acesso.
    """
    url = f"http://127.0.0.1:{port}"
    if is_port_in_use(port):
        return url

    # Inicia ou reinicia o servico em background (que ja sobe o servidor Web na porta 8765)
    start_background()
    for _ in range(15):
        if is_port_in_use(port):
            return url
        time.sleep(0.2)

    # Caso o daemon ja estivesse rodando em versao antiga sem o servidor Web, reinicia-o
    restart_background()
    for _ in range(15):
        if is_port_in_use(port):
            return url
        time.sleep(0.2)

    # Fallback: inicia processo pythonw.exe dedicado para o web_panel.py
    python_exe = sys.executable
    pythonw = Path(python_exe).parent / "pythonw.exe"
    exe = str(pythonw) if pythonw.exists() else python_exe
    script = Path(__file__).resolve()
    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
    subprocess.Popen(
        [exe, str(script), "--standalone", str(port)],
        creationflags=flags,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )
    time.sleep(0.6)
    return url


def run_web_server(port: int = 8765, open_browser: bool = True, standalone: bool = False) -> None:
    """
    Garante o servidor Web ativo em segundo plano e abre o navegador,
    ou executa em loop standalone quando chamado pelo processo de background.
    """
    if standalone:
        server = ReusableThreadingHTTPServer(("127.0.0.1", port), JiraBotWebHandler)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
        return

    url = ensure_background_web_server(port=port)
    print("\n" + "=" * 65)
    print("          PAINEL WEB INTERATIVO - JIRABOT ATIVO")
    print("=" * 65)
    print(f"  Endereco : {url}")
    print("  Modo     : Persistente em Background (voce pode fechar esta janela)")
    print("=" * 65 + "\n")

    if open_browser:
        webbrowser.open(url)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--standalone":
        p = int(sys.argv[2]) if len(sys.argv) > 2 else 8765
        run_web_server(port=p, open_browser=False, standalone=True)
    else:
        run_web_server()
