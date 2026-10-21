"""
Modulo de analise de lancamentos (worklogs) do usuario no Jira para o Dashboard Analitico do JiraBot.

A funcao `build_analytics` e pura (sem rede) e recebe os dados ja coletados, o que facilita os testes.
A funcao `get_analytics` faz a coleta no Jira (com cache curto) e delega a agregacao.
"""

from __future__ import annotations

import logging
import statistics
import threading
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger("JiraBot.Analytics")

ANALYTICS_CACHE_TTL_SECONDS = 300
ALLOWED_PERIODS = (7, 14, 30, 60, 90, 180, 365)

_cache_lock = threading.Lock()
_cache: Dict[int, Dict[str, Any]] = {}


def format_hm(seconds: float) -> str:
    """Converte segundos em texto curto no formato '12h 05m' (ou '45m' quando menor que 1h)."""
    total = max(0, int(round(seconds)))
    hours, rest = divmod(total, 3600)
    minutes = rest // 60
    if hours > 0:
        return f"{hours}h {minutes:02d}m"
    return f"{minutes}m"


def _pct(part: float, whole: float) -> float:
    if not whole:
        return 0.0
    return round(part * 100.0 / whole, 1)


def normalize_days(raw: Any, default: int = 30) -> int:
    """Normaliza o periodo solicitado para um dos valores permitidos (evita consultas gigantes)."""
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    if value in ALLOWED_PERIODS:
        return value
    return min(ALLOWED_PERIODS, key=lambda allowed: abs(allowed - value))


def build_analytics(
    issues: Dict[str, Dict[str, Any]],
    worklogs: List[Dict[str, Any]],
    days: int = 30,
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Agrega os lancamentos do usuario em indicadores para o dashboard.

    issues: mapa chave -> {summary, issue_type, status, status_category, completed_date, completed_by_me}
    worklogs: lista de {issue_key, date (YYYY-MM-DD), time_spent_seconds, comment}
    """
    today = today or date.today()
    days = max(1, int(days))
    start = today - timedelta(days=days - 1)
    start_str = start.isoformat()
    end_str = today.isoformat()

    entries: List[Dict[str, Any]] = []
    for w in worklogs:
        day_str = str(w.get("date") or "")[:10]
        if not (start_str <= day_str <= end_str):
            continue
        key = str(w.get("issue_key") or "").strip().upper()
        if not key:
            continue
        seconds = int(w.get("time_spent_seconds") or 0)
        entries.append({
            "key": key,
            "date": day_str,
            "seconds": seconds,
            "has_comment": bool(str(w.get("comment") or "").strip()),
        })

    issues_upper = {str(k).upper(): v for k, v in (issues or {}).items()}

    def type_of(key: str) -> str:
        meta = issues_upper.get(key) or {}
        return str(meta.get("issue_type") or "Sem tipo")

    total_seconds = sum(e["seconds"] for e in entries)
    total_worklogs = len(entries)

    seconds_by_ticket: Dict[str, int] = defaultdict(int)
    worklogs_by_ticket: Dict[str, int] = defaultdict(int)
    comments_by_ticket: Dict[str, int] = defaultdict(int)
    last_day_by_ticket: Dict[str, str] = {}
    for e in entries:
        seconds_by_ticket[e["key"]] += e["seconds"]
        worklogs_by_ticket[e["key"]] += 1
        if e["has_comment"]:
            comments_by_ticket[e["key"]] += 1
        if e["date"] > last_day_by_ticket.get(e["key"], ""):
            last_day_by_ticket[e["key"]] = e["date"]

    tickets = sorted(seconds_by_ticket.keys())
    tickets_total = len(tickets)

    # ---- Tipos de ticket ----
    type_seconds: Dict[str, int] = defaultdict(int)
    type_worklogs: Dict[str, int] = defaultdict(int)
    type_tickets: Dict[str, set] = defaultdict(set)
    for e in entries:
        t = type_of(e["key"])
        type_seconds[t] += e["seconds"]
        type_worklogs[t] += 1
        type_tickets[t].add(e["key"])

    by_type: List[Dict[str, Any]] = []
    for t in type_seconds:
        by_type.append({
            "type": t,
            "seconds": type_seconds[t],
            "formatted": format_hm(type_seconds[t]),
            "hours": round(type_seconds[t] / 3600.0, 2),
            "percent_time": _pct(type_seconds[t], total_seconds),
            "worklogs": type_worklogs[t],
            "percent_worklogs": _pct(type_worklogs[t], total_worklogs),
            "tickets": len(type_tickets[t]),
        })
    by_type_time = sorted(by_type, key=lambda x: (-x["seconds"], x["type"]))
    by_type_count = sorted(by_type, key=lambda x: (-x["worklogs"], x["type"]))

    # ---- Descricao dos lancamentos ----
    with_desc = sum(1 for e in entries if e["has_comment"])
    without_desc = total_worklogs - with_desc
    tk_with = tk_without = tk_partial = 0
    for key in tickets:
        c = comments_by_ticket.get(key, 0)
        n = worklogs_by_ticket[key]
        if c == n:
            tk_with += 1
        elif c == 0:
            tk_without += 1
        else:
            tk_partial += 1
    description = {
        "worklogs_total": total_worklogs,
        "worklogs_with": with_desc,
        "worklogs_without": without_desc,
        "worklogs_with_pct": _pct(with_desc, total_worklogs),
        "worklogs_without_pct": _pct(without_desc, total_worklogs),
        "tickets_total": tickets_total,
        "tickets_with": tk_with,
        "tickets_partial": tk_partial,
        "tickets_without": tk_without,
        "tickets_with_pct": _pct(tk_with, tickets_total),
        "tickets_partial_pct": _pct(tk_partial, tickets_total),
        "tickets_without_pct": _pct(tk_without, tickets_total),
    }

    # ---- Tickets finalizados pelo usuario no Jira ----
    completed_by_day: Dict[str, List[str]] = defaultdict(list)
    completed_keys: List[str] = []
    for key in tickets:
        meta = issues_upper.get(key) or {}
        if not meta.get("completed_by_me"):
            continue
        done_day = str(meta.get("completed_date") or "")[:10] or last_day_by_ticket.get(key, "")
        if not (start_str <= done_day <= end_str):
            continue
        completed_by_day[done_day].append(key)
        completed_keys.append(key)
    completed_total = len(completed_keys)
    weeks = days / 7.0
    months = days / 30.4375
    completed_seconds = sum(seconds_by_ticket[k] for k in completed_keys)

    # ---- Evolucao diaria ----
    day_tickets: Dict[str, set] = defaultdict(set)
    day_worklogs: Dict[str, int] = defaultdict(int)
    day_seconds: Dict[str, int] = defaultdict(int)
    for e in entries:
        day_tickets[e["date"]].add(e["key"])
        day_worklogs[e["date"]] += 1
        day_seconds[e["date"]] += e["seconds"]

    evolution: List[Dict[str, Any]] = []
    cumulative = 0
    cursor = start
    while cursor <= today:
        ds = cursor.isoformat()
        done_today = len(completed_by_day.get(ds, []))
        cumulative += done_today
        evolution.append({
            "date": ds,
            "weekday": cursor.weekday(),
            "tickets": len(day_tickets.get(ds, ())),
            "keys": sorted(day_tickets.get(ds, ())),
            "worklogs": day_worklogs.get(ds, 0),
            "seconds": day_seconds.get(ds, 0),
            "hours": round(day_seconds.get(ds, 0) / 3600.0, 2),
            "completed": done_today,
            "completed_cumulative": cumulative,
        })
        cursor += timedelta(days=1)

    # ---- Tempo por ticket ----
    per_ticket_values = [seconds_by_ticket[k] for k in tickets]
    avg_ticket = (total_seconds / tickets_total) if tickets_total else 0
    median_ticket = statistics.median(per_ticket_values) if per_ticket_values else 0
    avg_completed = (completed_seconds / completed_total) if completed_total else 0

    # ---- Top tickets ----
    top_keys = sorted(tickets, key=lambda k: (-seconds_by_ticket[k], k))[:8]
    top_tickets = []
    for key in top_keys:
        meta = issues_upper.get(key) or {}
        top_tickets.append({
            "key": key,
            "summary": str(meta.get("summary") or ""),
            "type": type_of(key),
            "seconds": seconds_by_ticket[key],
            "formatted": format_hm(seconds_by_ticket[key]),
            "percent_time": _pct(seconds_by_ticket[key], total_seconds),
            "worklogs": worklogs_by_ticket[key],
            "completed": key in completed_keys,
        })

    days_with_logs = len([d for d in day_seconds if day_seconds[d] > 0])

    return {
        "available": True,
        "period_days": days,
        "start_date": start_str,
        "end_date": end_str,
        "totals": {
            "seconds": total_seconds,
            "formatted": format_hm(total_seconds),
            "worklogs": total_worklogs,
            "tickets": tickets_total,
            "days_with_logs": days_with_logs,
        },
        "by_type_time": by_type_time,
        "by_type_count": by_type_count,
        "description": description,
        "completion": {
            "total": completed_total,
            "avg_per_week": round(completed_total / weeks, 2) if weeks else 0,
            "avg_per_month": round(completed_total / months, 2) if months else 0,
            "keys": completed_keys,
        },
        "time_per_ticket": {
            "avg_seconds": int(round(avg_ticket)),
            "avg_formatted": format_hm(avg_ticket),
            "median_seconds": int(round(median_ticket)),
            "median_formatted": format_hm(median_ticket),
            "avg_completed_seconds": int(round(avg_completed)),
            "avg_completed_formatted": format_hm(avg_completed),
        },
        "evolution": evolution,
        "top_tickets": top_tickets,
    }


def get_analytics(days: int = 30, force: bool = False) -> Dict[str, Any]:
    """Coleta os dados no Jira e devolve o payload do dashboard (com cache de alguns minutos)."""
    from config import BotConfig
    from jira_client import JiraClient
    from storage import StateManager

    days = normalize_days(days)
    now_ts = time.time()

    with _cache_lock:
        cached = _cache.get(days)
        if cached and not force and (now_ts - cached["ts"]) < ANALYTICS_CACHE_TTL_SECONDS:
            return cached["payload"]

    cfg = BotConfig.load()
    if not cfg.jira.get_clean_base_url() or not cfg.jira.get_clean_token():
        return {
            "available": False,
            "period_days": days,
            "message": "Jira não configurado. Informe a URL e o token na aba Configurações para ver o dashboard.",
        }

    client = JiraClient(cfg.jira, StateManager())
    try:
        data = client.get_user_analytics_data(days)
    except Exception as exc:
        logger.warning("Falha ao coletar dados analiticos do Jira: %s", exc)
        return {
            "available": False,
            "period_days": days,
            "message": f"Não foi possível consultar o Jira agora: {exc}",
        }

    payload = build_analytics(data.get("issues", {}), data.get("worklogs", []), days=days)
    payload["generated_at"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    with _cache_lock:
        _cache[days] = {"ts": now_ts, "payload": payload}
    return payload
