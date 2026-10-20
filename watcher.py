"""
Modulo de monitoramento de eventos de sessao do Windows (Lock e Unlock) via API Win32 nativa.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import logging
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger("JiraBot.Watcher")

# Constantes Win32
WM_WTSSESSION_CHANGE = 0x02B1
WM_DESTROY = 0x0002
WM_CLOSE = 0x0010

WTS_SESSION_LOCK = 0x7
WTS_SESSION_UNLOCK = 0x8
WTS_SESSION_LOGON = 0x5
WTS_SESSION_LOGOFF = 0x6

NOTIFY_FOR_THIS_SESSION = 0

LRESULT = ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long

# Tipos Win32 para WNDPROC
WNDPROC = ctypes.WINFUNCTYPE(
    LRESULT,
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
)

user32 = ctypes.windll.user32
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = LRESULT


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HICON),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


class SessionWatcher:
    """
    Listener em background de eventos de sessao do Windows (Lock/Unlock)
    utilizando a API WTSRegisterSessionNotification nativa.
    """

    def __init__(
        self,
        on_lock: Optional[Callable[[], None]] = None,
        on_unlock: Optional[Callable[[], None]] = None,
    ):
        self.on_lock = on_lock
        self.on_unlock = on_unlock
        self._hwnd: Optional[wintypes.HWND] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._wnd_proc_ref: Optional[WNDPROC] = None  # Manter referencia viva para o GC do Python

    def _wnd_proc(self, hwnd: wintypes.HWND, msg: int, wparam: int, lparam: int) -> int:
        if msg == WM_WTSSESSION_CHANGE:
            if wparam == WTS_SESSION_LOCK:
                logger.info("Evento detectado: Bloqueio de tela (WTS_SESSION_LOCK)")
                if self.on_lock:
                    try:
                        self.on_lock()
                    except Exception as e:
                        logger.error(f"Erro no callback on_lock: {e}")
            elif wparam == WTS_SESSION_UNLOCK:
                logger.info("Evento detectado: Desbloqueio de tela (WTS_SESSION_UNLOCK)")
                if self.on_unlock:
                    try:
                        self.on_unlock()
                    except Exception as e:
                        logger.error(f"Erro no callback on_unlock: {e}")
            return 0

        elif msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0

        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _run_loop(self) -> None:
        wtsapi32 = ctypes.windll.wtsapi32
        kernel32 = ctypes.windll.kernel32

        class_name = "JiraBot_SessionWatcher_Class"
        h_instance = kernel32.GetModuleHandleW(None)

        self._wnd_proc_ref = WNDPROC(self._wnd_proc)

        wnd_class = WNDCLASSW()
        wnd_class.lpfnWndProc = self._wnd_proc_ref
        wnd_class.hInstance = h_instance
        wnd_class.lpszClassName = class_name

        user32.RegisterClassW(ctypes.byref(wnd_class))

        self._hwnd = user32.CreateWindowExW(
            0,
            class_name,
            "JiraBot_SessionWatcher_Window",
            0,
            0, 0, 0, 0,
            0,
            0,
            h_instance,
            0,
        )

        if not self._hwnd:
            logger.error("Falha ao criar janela oculta para captura de sessao.")
            self._running = False
            return

        res = wtsapi32.WTSRegisterSessionNotification(self._hwnd, NOTIFY_FOR_THIS_SESSION)
        if not res:
            logger.error("Falha ao registrar WTSRegisterSessionNotification.")
        else:
            logger.info("WTSRegisterSessionNotification registrado com sucesso.")

        msg = wintypes.MSG()
        while self._running and user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        wtsapi32.WTSUnRegisterSessionNotification(self._hwnd)
        if self._hwnd:
            user32.DestroyWindow(self._hwnd)
            self._hwnd = None

    def start(self) -> None:
        """Inicia o ouvinte de sessao em uma thread dedicada."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, name="JiraBotWatcherThread", daemon=True)
        self._thread.start()
        logger.info("SessionWatcher iniciado em background.")

    def stop(self) -> None:
        """Encerra o ouvinte de sessao e destroi a janela oculta."""
        if not self._running:
            return
        self._running = False
        if self._hwnd:
            user32.PostMessageW(self._hwnd, WM_DESTROY, 0, 0)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        logger.info("SessionWatcher finalizado.")
