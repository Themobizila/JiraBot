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
import time
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
CMD_MINI_WINDOW = 1006

# Hotkey Win32
WM_HOTKEY = 0x0312
HOTKEY_MINI_WINDOW_ID = 2001
HOTKEY_MINI_WINDOW_ID_ALT = 2002
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000
VK_J = 0x4A  # Virtual Key 'J'

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
        self._last_hotkey_ts: float = 0.0

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
        user32_dll.AppendMenuW(hmenu, MF_STRING, CMD_MINI_WINDOW, "Mini Janela Flutuante (Ctrl+Alt+J ou Ctrl+Shift+J)")
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

        elif cmd == CMD_MINI_WINDOW:
            from mini_window import toggle_mini_window
            toggle_mini_window()

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

        elif msg == WM_HOTKEY:
            if wparam in (HOTKEY_MINI_WINDOW_ID, HOTKEY_MINI_WINDOW_ID_ALT):
                now_ts = time.time()
                if now_ts - self._last_hotkey_ts >= 0.4:
                    self._last_hotkey_ts = now_ts
                    logger.info(f"WM_HOTKEY detectada em _wnd_proc (id={wparam})! Alternando mini janela...")
                    try:
                        from mini_window import toggle_mini_window
                        toggle_mini_window()
                    except Exception as e:
                        logger.error(f"Erro ao processar hotkey em _wnd_proc: {e}")
                return 0

        elif msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0

        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _run_loop(self) -> None:
        shell32 = ctypes.windll.shell32
        kernel32 = ctypes.windll.kernel32

        try:
            from mini_window import _attach_to_interactive_desktop
            _attach_to_interactive_desktop()
        except Exception:
            pass

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

        # Registra hotkey global Ctrl + Alt + J para abrir/alternar a mini janela
        try:
            user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
            user32.RegisterHotKey.restype = wintypes.BOOL
            user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
            user32.UnregisterHotKey.restype = wintypes.BOOL

            # 1. Hotkey Primaria: Ctrl + Alt + J
            mod_primary = MOD_CONTROL | MOD_ALT | MOD_NOREPEAT
            reg_primary = user32.RegisterHotKey(self._hwnd, HOTKEY_MINI_WINDOW_ID, mod_primary, VK_J)
            if not reg_primary:
                reg_primary = user32.RegisterHotKey(self._hwnd, HOTKEY_MINI_WINDOW_ID, MOD_CONTROL | MOD_ALT, VK_J)
            logger.info(f"Hotkey global Ctrl+Alt+J registrada para a Mini Janela: {reg_primary}")

            # 2. Hotkey Secundaria: Ctrl + Shift + J
            mod_sec = MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT
            reg_sec = user32.RegisterHotKey(self._hwnd, HOTKEY_MINI_WINDOW_ID_ALT, mod_sec, VK_J)
            if not reg_sec:
                reg_sec = user32.RegisterHotKey(self._hwnd, HOTKEY_MINI_WINDOW_ID_ALT, MOD_CONTROL | MOD_SHIFT, VK_J)
            logger.info(f"Hotkey global alternativa Ctrl+Shift+J registrada: {reg_sec}")
        except Exception as e:
            logger.warning(f"Nao foi possivel registrar hotkeys globais: {e}")

        msg = wintypes.MSG()
        while self._running and user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) > 0:
            if msg.message == WM_HOTKEY and msg.wParam in (HOTKEY_MINI_WINDOW_ID, HOTKEY_MINI_WINDOW_ID_ALT):
                now_ts = time.time()
                if now_ts - self._last_hotkey_ts >= 0.4:
                    self._last_hotkey_ts = now_ts
                    logger.info(f"WM_HOTKEY detectada no loop GetMessageW (id={msg.wParam})! Alternando mini janela...")
                    try:
                        from mini_window import toggle_mini_window
                        toggle_mini_window()
                    except Exception as e:
                        logger.error(f"Erro ao processar toggle no loop: {e}")
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
        if self._hwnd:
            try:
                user32.UnregisterHotKey(self._hwnd, HOTKEY_MINI_WINDOW_ID)
                user32.UnregisterHotKey(self._hwnd, HOTKEY_MINI_WINDOW_ID_ALT)
            except Exception:
                pass
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
