"""
Modulo de integracao com a Bandeja do Sistema (Windows System Tray) via Win32 API pura.
Utiliza o icone personalizado do JiraBot em assets/jirabot.ico.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import logging
from pathlib import Path
import threading
from typing import Callable, Optional

from config import BotConfig
from engine import BotEngine, format_duration
from notifier import send_notification
from storage import StateManager

logger = logging.getLogger("JiraBot.Tray")

# Constantes Win32
WM_USER = 0x0400
WM_TRAYICON = WM_USER + 20
WM_COMMAND = 0x0111
WM_RBUTTONUP = 0x0205
WM_LBUTTONDBLCLK = 0x0203
WM_DESTROY = 0x0002

NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002

NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004

TPM_RIGHTBUTTON = 0x0002
TPM_RETURNCMD = 0x0100

MF_STRING = 0x0000
MF_SEPARATOR = 0x0800
MF_DISABLED = 0x0002

IMAGE_ICON = 1
LR_LOADFROMFILE = 0x0010
LR_DEFAULTSIZE = 0x0040
IDI_APPLICATION = 32512

# IDs de Comandos do Menu
CMD_STATUS = 1001
CMD_TOGGLE_PAUSE = 1002
CMD_LOG_NOW = 1003
CMD_EXIT = 1004
CMD_WEB_PANEL = 1005

LRESULT = ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long

WNDPROC = ctypes.WINFUNCTYPE(
    LRESULT,
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
)

# Declarar explicitamente tipos de retorno e argumentos Win32
user32 = ctypes.windll.user32
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = LRESULT

user32.LoadImageW.argtypes = [
    wintypes.HINSTANCE,
    wintypes.LPCWSTR,
    wintypes.UINT,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
]
user32.LoadImageW.restype = wintypes.HANDLE


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uTimeoutOrVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", ctypes.c_byte * 16),
        ("hBalloonIcon", wintypes.HICON),
    ]


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


def get_icon_handle() -> wintypes.HICON:
    """Carrega o icone personalizado assets/jirabot.ico se existir, ou fallback do sistema."""
    icon_path = Path(__file__).parent / "assets" / "jirabot.ico"
    if icon_path.exists():
        try:
            hicon = user32.LoadImageW(
                None,
                str(icon_path.resolve()),
                IMAGE_ICON,
                0,
                0,
                LR_LOADFROMFILE | LR_DEFAULTSIZE,
            )
            if hicon:
                return hicon
        except Exception as e:
            logger.warning(f"Falha ao carregar icone customizado {icon_path}: {e}")

    return user32.LoadIconW(None, ctypes.cast(IDI_APPLICATION, wintypes.LPCWSTR))


class SystemTrayIcon:
    """Icone da Bandeja do Sistema para acompanhamento visual e controle do JiraBot."""

    def __init__(
        self,
        engine: Optional[BotEngine] = None,
        on_exit_request: Optional[Callable[[], None]] = None,
    ):
        self.engine = engine or BotEngine()
        self.on_exit_request = on_exit_request
        self._hwnd: Optional[wintypes.HWND] = None
        self._hicon: Optional[wintypes.HICON] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._wnd_proc_ref: Optional[WNDPROC] = None

    def _show_menu(self) -> None:
        user32_dll = ctypes.windll.user32
        pt = wintypes.POINT()
        user32_dll.GetCursorPos(ctypes.byref(pt))

        hmenu = user32_dll.CreatePopupMenu()
        self.engine.refresh_state()
        state = self.engine.state

        total_str = format_duration(state.get_total_seconds())
        active_issue = self.engine.get_active_issue() or "Nenhum"

        title_str = f"JiraBot: {state.status} ({total_str})"
        user32_dll.AppendMenuW(hmenu, MF_STRING | MF_DISABLED, 0, title_str)
        user32_dll.AppendMenuW(hmenu, MF_STRING | MF_DISABLED, 0, f"Ticket Ativo: {active_issue}")
        user32_dll.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)

        user32_dll.AppendMenuW(hmenu, MF_STRING, CMD_WEB_PANEL, "Abrir Painel Web no Navegador")
        user32_dll.AppendMenuW(hmenu, MF_STRING, CMD_STATUS, "Ver Status Detalhado")
        toggle_label = "Pausar Cronometro" if state.status == "RUNNING" else "Retomar Cronometro"
        user32_dll.AppendMenuW(hmenu, MF_STRING, CMD_TOGGLE_PAUSE, toggle_label)
        user32_dll.AppendMenuW(hmenu, MF_STRING, CMD_LOG_NOW, "Lancar Horas no Jira Agora")
        user32_dll.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)
        user32_dll.AppendMenuW(hmenu, MF_STRING, CMD_EXIT, "Encerrar JiraBot")

        user32_dll.SetForegroundWindow(self._hwnd)
        cmd = user32_dll.TrackPopupMenu(
            hmenu,
            TPM_RIGHTBUTTON | TPM_RETURNCMD,
            pt.x,
            pt.y,
            0,
            self._hwnd,
            None,
        )
        user32_dll.DestroyMenu(hmenu)

        self._handle_command(cmd)

    def _handle_command(self, cmd: int) -> None:
        if cmd == CMD_WEB_PANEL:
            import socket
            import subprocess
            import sys
            import webbrowser
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                is_up = (s.connect_ex(("127.0.0.1", 8765)) == 0)
            if is_up:
                webbrowser.open("http://127.0.0.1:8765")
            else:
                python_exe = sys.executable
                pythonw = Path(python_exe).parent / "pythonw.exe"
                exe = str(pythonw) if pythonw.exists() else python_exe
                script = Path(__file__).parent / "web_panel.py"
                flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
                subprocess.Popen(
                    [exe, str(script)],
                    creationflags=flags,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                )

        elif cmd == CMD_STATUS:
            self.engine.refresh_state()
            state = self.engine.state
            total_str = format_duration(state.get_total_seconds())
            msg = f"Status: {state.status}\nTempo Hoje: {total_str}\nTicket: {self.engine.get_active_issue() or 'Nenhum'}"
            send_notification("JiraBot - Status", msg, True)

        elif cmd == CMD_TOGGLE_PAUSE:
            self.engine.refresh_state()
            if self.engine.state.status == "RUNNING":
                self.engine.manual_pause()
            else:
                self.engine.manual_start()

        elif cmd == CMD_LOG_NOW:
            self.engine.manual_log()
            send_notification("JiraBot", "Horas lancadas no Jira com sucesso.", True)

        elif cmd == CMD_EXIT:
            if self.on_exit_request:
                self.on_exit_request()
            self.stop()

    def _wnd_proc(self, hwnd: wintypes.HWND, msg: int, wparam: int, lparam: int) -> int:
        if msg == WM_TRAYICON:
            if lparam == WM_RBUTTONUP:
                self._show_menu()
                return 0
            elif lparam == WM_LBUTTONDBLCLK:
                self._handle_command(CMD_STATUS)
                return 0

        elif msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0

        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _run_loop(self) -> None:
        shell32 = ctypes.windll.shell32
        kernel32 = ctypes.windll.kernel32

        class_name = "JiraBot_TrayIcon_Class"
        h_instance = kernel32.GetModuleHandleW(None)

        self._wnd_proc_ref = WNDPROC(self._wnd_proc)

        self._hicon = get_icon_handle()

        wnd_class = WNDCLASSW()
        wnd_class.lpfnWndProc = self._wnd_proc_ref
        wnd_class.hInstance = h_instance
        wnd_class.lpszClassName = class_name
        wnd_class.hIcon = self._hicon

        user32.RegisterClassW(ctypes.byref(wnd_class))

        self._hwnd = user32.CreateWindowExW(
            0,
            class_name,
            "JiraBot_TrayIcon_Window",
            0,
            0, 0, 0, 0,
            0,
            0,
            h_instance,
            0,
        )

        if not self._hwnd:
            logger.error("Falha ao criar janela oculta para TrayIcon.")
            self._running = False
            return

        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self._hwnd
        nid.uID = 1
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = WM_TRAYICON
        nid.hIcon = self._hicon
        nid.szTip = "JiraBot - Monitor de Horas"

        res = shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))
        logger.info(f"Shell_NotifyIconW registrado: {res}")

        msg = wintypes.MSG()
        while self._running and user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
        if self._hwnd:
            user32.DestroyWindow(self._hwnd)
            self._hwnd = None

    def start(self) -> None:
        """Inicia o icone da bandeja em background."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, name="JiraBotTrayThread", daemon=True)
        self._thread.start()
        logger.info("SystemTrayIcon iniciado.")

    def stop(self) -> None:
        """Remove o icone e finaliza o loop da bandeja."""
        if not self._running:
            return
        self._running = False
        if self._hwnd:
            user32.PostMessageW(self._hwnd, WM_DESTROY, 0, 0)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        logger.info("SystemTrayIcon finalizado.")
