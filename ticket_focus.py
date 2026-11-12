"""Piloto local de sugestões de ticket a partir da janela em foco."""

import ctypes
from ctypes import wintypes
from datetime import datetime, timedelta
import hashlib
from http.client import HTTPConnection
import json
from pathlib import PureWindowsPath
import re
from threading import RLock
import unicodedata
from uuid import uuid4


TICKET_KEY = re.compile(r"(?<![A-Z0-9])([A-Z][A-Z0-9]*-\d+)(?![A-Z0-9])", re.IGNORECASE)


def local_focus_request(path, payload=None, *, port=8765, timeout=20):
    connection = HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        method = "GET" if payload is None else "POST"
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        connection.request(method, path, body, {"Content-Type": "application/json"})
        response = connection.getresponse()
        return response.status, json.loads(response.read())
    finally:
        connection.close()


def rank_assigned_tickets(context, tickets):
    def words(value):
        normalized = unicodedata.normalize("NFKD", value.casefold())
        plain = "".join(char for char in normalized if not unicodedata.combining(char))
        return set(re.findall(r"[a-z0-9]{2,}", plain))

    terms = words(context)
    ranked = []
    for ticket in tickets:
        key = ticket["key"]
        summary = ticket.get("summary") or ""
        matches = terms & words(summary)
        if matches:
            ranked.append((len(matches), key, summary))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [{"chave": key, "titulo": summary} for _, key, summary in ranked[:10]]


def read_work_window(applications):
    """Lê o título apenas depois de validar o executável da janela."""
    user = ctypes.WinDLL("user32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    user.GetForegroundWindow.restype = wintypes.HWND
    user.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    user.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = (
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)
    )
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)

    window = user.GetForegroundWindow()
    pid = wintypes.DWORD()
    if not window or not user.GetWindowThreadProcessId(window, ctypes.byref(pid)):
        return None
    process = kernel.OpenProcess(0x1000, False, pid.value)
    if not process:
        return None
    try:
        path = ctypes.create_unicode_buffer(32768)
        size = wintypes.DWORD(len(path))
        if not kernel.QueryFullProcessImageNameW(process, 0, path, ctypes.byref(size)):
            return None
    finally:
        kernel.CloseHandle(process)
    application = PureWindowsPath(path.value).name.casefold()
    if application not in applications:
        return None
    title = ctypes.create_unicode_buffer(1024)
    if not user.GetWindowTextW(window, title, len(title)) or user.GetForegroundWindow() != window:
        return None
    return application, title.value


class TicketFocusPilot:
    def __init__(self):
        self.lock = RLock()
        self.assistant_suggestion = None
        self.configure((), 60)

    def configure(self, applications, dwell_seconds):
        with self.lock:
            self.applications = frozenset(applications)
            self.dwell_seconds = dwell_seconds
            self.context = None
            self.last_seen = None
            self.started = None
            self.checked = False
            self.suggestion = None
            self.last_unlinked = None
            self.bindings = {}

    def snapshot(self):
        with self.lock:
            now = datetime.now()
            suggestion = next(
                (item for item in (self.assistant_suggestion, self.suggestion) if item and now < item["expires"]),
                None,
            )
            unlinked = self.unlinked_context()
            return {
                "applications": sorted(self.applications),
                "seconds": self.dwell_seconds,
                "unlinked_application": unlinked[0] if unlinked else None,
                "unlinked_id": unlinked[1].hex() if unlinked else None,
                "suggestion": {
                    key: suggestion[key] for key in ("id", "issue", "summary", "application", "seconds", "reason")
                } if suggestion else None,
            }

    def reset(self):
        with self.lock:
            self.context = None
            self.last_seen = None
            self.suggestion = None
            self.assistant_suggestion = None
            self.last_unlinked = None

    def unlinked_context(self):
        with self.lock:
            if self.last_unlinked and datetime.now() - self.last_unlinked[1] < timedelta(minutes=2):
                return self.last_unlinked[0]
            return None

    def bind(self, context, issue):
        with self.lock:
            if not context or context != self.unlinked_context() or context[0] not in self.applications:
                return False
            self.bindings[context] = issue
            self.last_unlinked = None
            return True

    def observe(self, window, active_issue, now):
        with self.lock:
            if not window or window[0] not in self.applications:
                self.context = None
                self.last_seen = None
                return None
            application, title = window
            keys = {key.upper() for key in TICKET_KEY.findall(title)}
            fingerprint = (application, hashlib.sha256(title.casefold().encode("utf-8")).digest())
            context = (*fingerprint, active_issue)
            linked = self.bindings.get(fingerprint) if not keys else None
            if not keys and not linked:
                self.last_unlinked = (fingerprint, now)
            else:
                self.last_unlinked = None
            candidates = {linked} if linked else keys
            if context != self.context or not self.last_seen or now - self.last_seen > timedelta(seconds=35):
                if self.suggestion and self.suggestion["issue"] not in candidates:
                    self.suggestion = None
                self.context = context
                self.started = now
                self.checked = False
            self.last_seen = now
            if len(candidates) != 1 or active_issue in candidates or self.checked:
                return None
            elapsed = int((now - self.started).total_seconds())
            if elapsed < self.dwell_seconds:
                return None
            self.checked = True
            return context, candidates.pop(), self.started, elapsed, "vínculo confirmado" if linked else "chave no título"

    def offer(self, candidate, assigned, now):
        context, key, started, elapsed, reason = candidate
        match = next((issue for issue in assigned if issue.get("key") == key), None)
        with self.lock:
            if not match or self.context != context or self.started != started:
                return False
            self.suggestion = {
                "id": uuid4().hex, "issue": key, "summary": match.get("summary") or "",
                "application": context[0], "source": context[2],
                "started": started, "seconds": elapsed, "expires": now + timedelta(minutes=2), "reason": reason,
            }
            return True

    def offer_assistant(self, issue, summary, source, reason, now):
        with self.lock:
            existing = self.assistant_suggestion
            if existing and now < existing["expires"] and (existing["issue"], existing["source"]) == (issue, source):
                return None
            suggestion_id = uuid4().hex
            self.assistant_suggestion = {
                "id": suggestion_id, "issue": issue, "summary": summary, "application": "Assistente conectado",
                "source": source, "started": None, "seconds": None, "reason": reason,
                "expires": now + timedelta(minutes=5),
            }
            return suggestion_id

    def take(self, suggestion_id, *, require_focus_start=False):
        with self.lock:
            for attribute in ("assistant_suggestion", "suggestion"):
                result = getattr(self, attribute)
                if result and result["id"] == suggestion_id and datetime.now() < result["expires"]:
                    if require_focus_start and result["started"] is None:
                        return None
                    setattr(self, attribute, None)
                    return result
            return None

    def pending_assistant(self):
        with self.lock:
            item = self.assistant_suggestion
            if not item or datetime.now() >= item["expires"]:
                return None
            return {key: item[key] for key in ("id", "issue", "summary", "reason")}


focus_pilot = TicketFocusPilot()


class McpConnections:
    """Histórico em memória dos processos MCP que contataram o painel."""

    def __init__(self):
        self.lock = RLock()
        self.sessions = {}

    def record(self, session_id, event, client_name="", tool="", now=None):
        now = now or datetime.now().astimezone()
        with self.lock:
            previous = self.sessions.pop(session_id, None)
            if previous is None and (event == "closed" or not client_name.strip()):
                return
            item = previous or {"id": session_id, "name": client_name.strip(), "last_tool": None, "last_use": None}
            item.update(last_seen=now, closed=event == "closed")
            if client_name.strip():
                item["name"] = client_name.strip()
            if event == "tool":
                item.update(last_tool=tool, last_use=now.isoformat())
            self.sessions[session_id] = item
            if len(self.sessions) > 50:
                del self.sessions[next(iter(self.sessions))]

    def snapshot(self, now=None):
        now = now or datetime.now().astimezone()
        with self.lock:
            return [
                {
                    "id": item["id"], "name": item["name"],
                    "online": not item["closed"] and now - item["last_seen"] < timedelta(seconds=45),
                    "last_seen": item["last_seen"].isoformat(),
                    "last_tool": item["last_tool"], "last_use": item["last_use"],
                }
                for item in reversed(self.sessions.values())
            ]


mcp_connections = McpConnections()
