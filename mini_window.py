"""
Modulo da Mini Janela Flutuante (Always on Top) do JiraBot.
Widget nativo compacto em Tkinter para monitoramento e controle rapido
do expediente de trabalho no canto da tela do Windows.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Garante resolucao de modulos do projeto independentemente do diretorio de trabalho
_BASE_DIR = str(Path(__file__).resolve().parent)
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)

import ctypes
from ctypes import wintypes
from datetime import datetime, date, timedelta, time
import json
import logging
import os
import subprocess
import tkinter as tk
from tkinter import ttk
from typing import Optional, Tuple, Any, Dict
import webbrowser

from config import BotConfig
from engine import BotEngine, format_duration
from storage import StateManager, DailyState, clean_jira_issue_key

logger = logging.getLogger("JiraBot.MiniWindow")

WINDOW_WIDTH = 370
WINDOW_HEIGHT = 168
COMPACT_HEIGHT = 56
WINDOW_TITLE = "JiraBot - Mini Widget"

# Paletas de cores fiéis aos temas do Painel Web (extraídas do design system oficial do JiraBot)
THEME_PALETTES: Dict[str, Dict[str, Any]] = {
    "halloween": {
        "name": "Halloween",
        "is_dark": True,
        "bg_body": "#0a0512",
        "bg_card": "#150a24",
        "bg_subtle": "#1e0f33",
        "border": "#381959",
        "border_strong": "#5a288e",
        "text_primary": "#f5edfc",
        "text_secondary": "#d8b4fe",
        "text_muted": "#9d7dbf",
        "primary": "#ff7518",
        "primary_hover": "#ffa34d",
        "success": "#22c55e",
        "warning": "#eab308",
        "danger": "#ef4444",
        "purple": "#a855f7",
        "btn_bg": "#24103a",
        "btn_primary_bg": "#b34700",
    },
    "dark": {
        "name": "Dark",
        "is_dark": True,
        "bg_body": "#0a0907",
        "bg_card": "#15110b",
        "bg_subtle": "#1d1810",
        "border": "#2b2418",
        "border_strong": "#4b3f26",
        "text_primary": "#f0e6d2",
        "text_secondary": "#d4c8ae",
        "text_muted": "#a39880",
        "primary": "#c8aa6e",
        "primary_hover": "#dcc287",
        "success": "#34b58c",
        "warning": "#e8913a",
        "danger": "#ef4a5f",
        "purple": "#c8aa6e",
        "btn_bg": "#1d1810",
        "btn_primary_bg": "#785a28",
    },
    "light": {
        "name": "Pergaminho",
        "is_dark": False,
        "bg_body": "#ece3cf",
        "bg_card": "#fbf6e9",
        "bg_subtle": "#f3ead6",
        "border": "#ddd0b0",
        "border_strong": "#c2b088",
        "text_primary": "#1d1710",
        "text_secondary": "#40362a",
        "text_muted": "#6d604a",
        "primary": "#8a6820",
        "primary_hover": "#6e5217",
        "success": "#1c7a58",
        "warning": "#b25d10",
        "danger": "#b2202f",
        "purple": "#8a6820",
        "btn_bg": "#f3ead6",
        "btn_primary_bg": "#9a7424",
    },
    "natal": {
        "name": "Natal",
        "is_dark": True,
        "bg_body": "#06120d",
        "bg_card": "#0c2018",
        "bg_subtle": "#122c21",
        "border": "#1e4635",
        "border_strong": "#2d6950",
        "text_primary": "#f1fbf6",
        "text_secondary": "#a3c9b7",
        "text_muted": "#78a18e",
        "primary": "#e63946",
        "primary_hover": "#f2646f",
        "success": "#2ec4b6",
        "warning": "#e76f51",
        "danger": "#e63946",
        "purple": "#2ec4b6",
        "btn_bg": "#122c21",
        "btn_primary_bg": "#9e1c26",
    },
    "ano_novo": {
        "name": "Ano Novo",
        "is_dark": True,
        "bg_body": "#07090d",
        "bg_card": "#0b0e14",
        "bg_subtle": "#131924",
        "border": "#243044",
        "border_strong": "#384c6e",
        "text_primary": "#f7f9fc",
        "text_secondary": "#a2b0c6",
        "text_muted": "#74839c",
        "primary": "#d4af37",
        "primary_hover": "#e6c35c",
        "success": "#38bdf8",
        "warning": "#fbbf24",
        "danger": "#ef4444",
        "purple": "#d4af37",
        "btn_bg": "#131924",
        "btn_primary_bg": "#8c721f",
    },
    "pascoa": {
        "name": "Páscoa",
        "is_dark": True,
        "bg_body": "#070d0b",
        "bg_card": "#0e1815",
        "bg_subtle": "#162722",
        "border": "#233d36",
        "border_strong": "#365f54",
        "text_primary": "#ecfdf5",
        "text_secondary": "#a7f3d0",
        "text_muted": "#78b89c",
        "primary": "#6ee7b7",
        "primary_hover": "#a7f3d0",
        "success": "#10b981",
        "warning": "#f59e0b",
        "danger": "#ef4444",
        "purple": "#6ee7b7",
        "btn_bg": "#162722",
        "btn_primary_bg": "#0f766e",
    },
}


def get_effective_theme(theme_pref: str = "auto") -> str:
    """Resolve o tema efetivo respeitando preferências manuais ou calendário sazonal do web_panel."""
    clean = (theme_pref or "auto").strip().lower()
    if clean != "auto":
        return clean if clean in THEME_PALETTES else "dark"
    now = datetime.now()
    m, d = now.month, now.day
    if (m == 10 and d >= 1) or (m == 11 and d <= 3):
        return "halloween"
    if m == 12 and 1 <= d <= 26:
        return "natal"
    if (m == 12 and d >= 27) or (m == 1 and d <= 6):
        return "ano_novo"
    if (m == 3 and d >= 20) or (m == 4 and d <= 25):
        return "pascoa"
    return "dark"


def _apply_dark_title_bar(root_or_hwnd: Any, dark: bool = True) -> None:
    """Aplica ou remove o tema escuro nativo do Windows 10/11 na barra de titulo da janela."""
    if sys.platform != "win32":
        return
    try:
        hwnd = None
        if hasattr(root_or_hwnd, "wm_frame"):
            frame_str = root_or_hwnd.wm_frame()
            hwnd = int(frame_str, 16) if frame_str else root_or_hwnd.winfo_id()
        elif hasattr(root_or_hwnd, "winfo_id"):
            hwnd = root_or_hwnd.winfo_id()
        else:
            hwnd = int(root_or_hwnd)

        if hwnd:
            dwmapi = ctypes.windll.dwmapi
            val = ctypes.c_int(1 if dark else 0)
            res = dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(val), ctypes.sizeof(val))
            if res != 0:
                dwmapi.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(val), ctypes.sizeof(val))
    except Exception:
        pass


def _attach_to_interactive_desktop() -> None:
    """Garante ancoragem no desktop interativo visivel do usuario (WinSta0\\Default)."""
    if sys.platform != "win32":
        return
    try:
        user32 = ctypes.windll.user32
        MAXIMUM_ALLOWED = 0x02000000
        hwinsta = user32.OpenWindowStationW("WinSta0", False, MAXIMUM_ALLOWED)
        if hwinsta:
            user32.SetProcessWindowStation(hwinsta)
        hdesk = user32.OpenDesktopW("Default", 0, False, MAXIMUM_ALLOWED)
        if hdesk:
            user32.SetThreadDesktop(hdesk)
    except Exception as e:
        logger.debug(f"Aviso ao ancorar desktop interativo: {e}")


def get_position_file_path() -> Path:
    """Retorna o caminho do arquivo de persistencia da posicao da mini janela."""
    base = Path.home() / ".jirabot"
    base.mkdir(parents=True, exist_ok=True)
    return base / "mini_window_pos.json"


def load_saved_position(screen_w: int, screen_h: int) -> Tuple[int, int]:
    """Recupera a ultima posicao gravada da janela ou posiciona no canto inferior direito."""
    pos_file = get_position_file_path()
    if pos_file.exists():
        try:
            with open(pos_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                x = int(data.get("x", 0))
                y = int(data.get("y", 0))
                if 0 <= x <= max(0, screen_w - 60) and 0 <= y <= max(0, screen_h - 40):
                    return x, y
        except Exception:
            pass

    # Padrao: canto inferior direito, logo acima da barra de tarefas
    x = max(20, screen_w - WINDOW_WIDTH - 24)
    y = max(20, screen_h - WINDOW_HEIGHT - 64)
    return x, y


def save_position(x: int, y: int) -> None:
    """Grava as coordenadas da janela no arquivo de persistencia."""
    pos_file = get_position_file_path()
    try:
        with open(pos_file, "w", encoding="utf-8") as f:
            json.dump({"x": int(x), "y": int(y)}, f)
    except Exception:
        pass


def toggle_mini_window() -> None:
    """
    Alterna o estado da mini janela flutuante:
    - Se nao existir: dispara a abertura em processo desacoplado.
    - Se ja estiver aberta e visivel em foco: fecha a janela (toggle off).
    - Se ja estiver aberta mas sem foco/minimizada: restaura e traz para o primeiro plano.
    """
    if sys.platform != "win32":
        launch_mini_window(detached=True)
        return

    try:
        user32 = ctypes.windll.user32
        user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
        user32.FindWindowW.restype = wintypes.HWND
        hwnd = user32.FindWindowW("TkTopLevel", WINDOW_TITLE)
        if not hwnd:
            hwnd = user32.FindWindowW(None, WINDOW_TITLE)

        if hwnd:
            fg_hwnd = user32.GetForegroundWindow()
            if fg_hwnd == hwnd:
                user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
            else:
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                user32.SetForegroundWindow(hwnd)
                user32.BringWindowToTop(hwnd)
            return
    except Exception as e:
        logger.debug(f"Erro ao alternar mini janela via Win32: {e}")

    launch_mini_window(detached=True)


def bring_existing_mini_window_to_top() -> bool:
    """Procura por uma janela existente com o titulo do widget e a traz para o primeiro plano."""
    if sys.platform != "win32":
        return False
    try:
        user32 = ctypes.windll.user32
        user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
        user32.FindWindowW.restype = wintypes.HWND
        hwnd = user32.FindWindowW("TkTopLevel", WINDOW_TITLE)
        if not hwnd:
            hwnd = user32.FindWindowW(None, WINDOW_TITLE)

        if hwnd:
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            user32.SetForegroundWindow(hwnd)
            user32.BringWindowToTop(hwnd)
            return True
    except Exception:
        pass
    return False


class MiniWidgetApp:
    """Aplicativo do widget flutuante compacto e moderno do JiraBot."""

    def __init__(self, root: tk.Tk, state_manager: Optional[StateManager] = None) -> None:
        self.root = root
        self.state_mgr = state_manager or StateManager()
        self.config = BotConfig.load()
        self.engine = BotEngine(config=self.config, state_manager=self.state_mgr)

        self.always_on_top = True
        self.is_compact = False
        self.drag_start_x = 0
        self.drag_start_y = 0

        self.root.title(WINDOW_TITLE)
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        start_x, start_y = load_saved_position(screen_w, screen_h)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{start_x}+{start_y}")
        self.root.update()

        _apply_dark_title_bar(self.root)

        self.current_theme = get_effective_theme(getattr(self.config, "theme", "auto"))
        self._init_theme_colors(self.current_theme)

        self.root.configure(bg=self.bg_color)
        _apply_dark_title_bar(self.root, dark=self.is_dark_theme)

        self._build_ui()
        self._bind_drag_events()
        self.root.protocol("WM_DELETE_WINDOW", self.close_app)
        self.root.bind("<Escape>", lambda e: self.close_app())

        # Inicia loop de atualizacao a cada 1 segundo
        self.update_state()

    def _init_theme_colors(self, theme_name: str) -> None:
        """Carrega os atributos de cor a partir da paleta correspondente ao tema do painel web."""
        palette = THEME_PALETTES.get(theme_name, THEME_PALETTES["dark"])
        self.current_theme = theme_name
        self.bg_color = palette["bg_card"]
        self.header_bg = palette["bg_body"]
        self.card_bg = palette["bg_subtle"]
        self.border_color = palette["border"]
        self.border_strong = palette["border_strong"]
        self.text_primary = palette["text_primary"]
        self.text_secondary = palette["text_secondary"]
        self.text_muted = palette["text_muted"]
        self.accent_color = palette["primary"]
        self.accent_hover = palette["primary_hover"]
        self.success_color = palette["success"]
        self.warning_color = palette["warning"]
        self.danger_color = palette["danger"]
        self.purple_color = palette.get("purple", palette["primary"])
        self.btn_bg = palette.get("btn_bg", palette["bg_subtle"])
        self.btn_primary_bg = palette.get("btn_primary_bg", palette["primary"])
        self.is_dark_theme = palette.get("is_dark", True)

    def apply_theme(self, theme_name: str) -> None:
        """Aplica dinamicamente uma nova paleta aos componentes da interface."""
        self._init_theme_colors(theme_name)
        _apply_dark_title_bar(self.root, dark=self.is_dark_theme)

        try:
            self.root.configure(bg=self.bg_color)
            if hasattr(self, "main_frame"):
                self.main_frame.configure(bg=self.bg_color, highlightbackground=self.border_color)
                self.header_frame.configure(bg=self.header_bg)
                self.status_canvas.configure(bg=self.header_bg)
                self.title_label.configure(bg=self.header_bg, fg=self.text_secondary)
                self.status_label.configure(bg=self.header_bg, fg=self.text_primary)
                self.btn_mode.configure(bg=self.header_bg, fg=self.text_secondary, activebackground=self.header_bg, activeforeground=self.text_primary)
                self.btn_pin.configure(bg=self.header_bg, fg=self.accent_color, activebackground=self.header_bg, activeforeground=self.text_primary)
                self.btn_web.configure(bg=self.header_bg, fg=self.text_secondary, activebackground=self.header_bg, activeforeground=self.text_primary)

                self.full_container.configure(bg=self.bg_color)
                self.body_frame.configure(bg=self.bg_color)
                self.left_box.configure(bg=self.bg_color)
                self.right_box.configure(bg=self.bg_color)
                self.timer_label.configure(bg=self.bg_color, fg=self.text_primary)
                self.meta_label.configure(bg=self.bg_color, fg=self.text_secondary)
                self.ticket_label.configure(bg=self.bg_color, fg=self.accent_color)
                self.desc_container.configure(bg=self.bg_color)
                self.desc_label.configure(bg=self.bg_color, fg=self.text_secondary)
                self.btn_quick_edit_desc.configure(bg=self.bg_color, fg=self.text_muted, activebackground=self.bg_color, activeforeground=self.text_primary)

                self.progress_container.configure(bg=self.bg_color)
                self.progress_canvas.configure(bg=self.card_bg)
                self.info_row.configure(bg=self.bg_color)
                self.exit_label.configure(bg=self.bg_color, fg=self.accent_color)
                self.pct_label.configure(bg=self.bg_color, fg=self.text_secondary)

                self.footer_frame.configure(bg=self.bg_color)
                self.btn_switch.configure(bg=self.btn_bg, fg=self.accent_color, activebackground=self.border_strong, activeforeground=self.text_primary)
                self.btn_finish.configure(bg=self.card_bg, fg=self.success_color, activebackground=self.border_strong, activeforeground=self.text_primary)
                self.hotkey_hint.configure(bg=self.bg_color, fg=self.text_muted)

                self.compact_frame.configure(bg=self.bg_color)
                self.compact_status_canvas.configure(bg=self.bg_color)
                self.compact_timer_label.configure(bg=self.bg_color, fg=self.text_primary)
                self.compact_ticket_label.configure(bg=self.bg_color, fg=self.accent_color)
                self.btn_compact_pause.configure(bg=self.btn_bg, fg=self.text_primary)
                self.btn_compact_expand.configure(bg=self.bg_color, fg=self.accent_color)
        except Exception as e:
            logger.debug(f"Erro ao reconfigurar tema visual da mini janela: {e}")

    def close_app(self) -> None:
        """Encerra a mini janela e finaliza o processo filho imediatamente."""
        try:
            self.root.destroy()
        except Exception:
            pass
        sys.exit(0)

    def _build_ui(self) -> None:
        # Container principal com borda sutil
        self.main_frame = tk.Frame(self.root, bg=self.bg_color, highlightbackground=self.border_color, highlightthickness=1)
        self.main_frame.pack(fill="both", expand=True)

        # 1. Barra de Cabecalho (Drag Bar)
        self.header_frame = tk.Frame(self.main_frame, bg=self.header_bg, height=26)
        self.header_frame.pack(fill="x", side="top")

        # Indicador de status (ponto circular desenhado em canvas)
        self.status_canvas = tk.Canvas(self.header_frame, width=12, height=12, bg=self.header_bg, highlightthickness=0)
        self.status_canvas.pack(side="left", padx=(8, 4), pady=5)
        self.status_dot = self.status_canvas.create_oval(2, 2, 10, 10, fill=self.success_color, outline="")

        self.title_label = tk.Label(
            self.header_frame,
            text="Status:",
            font=("Segoe UI", 8, "bold"),
            fg=self.text_secondary,
            bg=self.header_bg,
        )
        self.title_label.pack(side="left", pady=3)

        self.status_label = tk.Label(
            self.header_frame,
            text="Em execucao",
            font=("Segoe UI", 8),
            fg=self.text_primary,
            bg=self.header_bg,
        )
        self.status_label.pack(side="left", padx=(4, 0), pady=3)

        # Controles superiores (sem botao 'X' duplicado, utilizando o X nativo da janela)
        self.btn_mode = tk.Button(
            self.header_frame,
            text="Mini",
            font=("Segoe UI", 7, "bold"),
            fg=self.text_secondary,
            bg=self.header_bg,
            activeforeground=self.text_primary,
            activebackground=self.header_bg,
            bd=0,
            cursor="hand2",
            padx=4,
            command=self.toggle_compact_mode,
        )
        self.btn_mode.pack(side="right", padx=(2, 6))

        self.btn_pin = tk.Button(
            self.header_frame,
            text="Topo",
            font=("Segoe UI", 7, "bold"),
            fg=self.accent_color,
            bg=self.header_bg,
            activeforeground=self.text_primary,
            activebackground=self.header_bg,
            bd=0,
            cursor="hand2",
            padx=4,
            command=self.toggle_always_on_top,
        )
        self.btn_pin.pack(side="right", padx=2)

        self.btn_web = tk.Button(
            self.header_frame,
            text="Painel",
            font=("Segoe UI", 7),
            fg=self.text_secondary,
            bg=self.header_bg,
            activeforeground=self.text_primary,
            activebackground=self.header_bg,
            bd=0,
            cursor="hand2",
            padx=4,
            command=self.open_web_panel,
        )
        self.btn_web.pack(side="right", padx=2)

        # ==================== MODO COMPLETO (PADRAO) ====================
        self.full_container = tk.Frame(self.main_frame, bg=self.bg_color)
        self.full_container.pack(fill="both", expand=True)

        # 2. Corpo do Widget: Cronometro e Chamado Ativo
        self.body_frame = tk.Frame(self.full_container, bg=self.bg_color)
        self.body_frame.pack(fill="x", padx=10, pady=(6, 2))

        # Coluna Esquerda: Cronometro e Meta
        self.left_box = tk.Frame(self.body_frame, bg=self.bg_color)
        self.left_box.pack(side="left", fill="y")

        self.timer_label = tk.Label(
            self.left_box,
            text="00:00:00",
            font=("Segoe UI", 18, "bold"),
            fg=self.text_primary,
            bg=self.bg_color,
        )
        self.timer_label.pack(anchor="w")

        self.meta_label = tk.Label(
            self.left_box,
            text="Meta: 8.0h (0%)",
            font=("Segoe UI", 8),
            fg=self.text_secondary,
            bg=self.bg_color,
        )
        self.meta_label.pack(anchor="w")

        # Coluna Direita: Chamado Atual e Descricao com Edicao Rapida
        self.right_box = tk.Frame(self.body_frame, bg=self.bg_color)
        self.right_box.pack(side="right", fill="both", expand=True, padx=(12, 0))

        self.ticket_label = tk.Label(
            self.right_box,
            text="SEM_TICKET",
            font=("Segoe UI", 11, "bold"),
            fg=self.accent_color,
            bg=self.bg_color,
            anchor="e",
            cursor="hand2",
        )
        self.ticket_label.pack(anchor="e", fill="x")
        self.ticket_label.bind("<Button-1>", lambda e: self.show_switch_dialog())

        self.desc_container = tk.Frame(self.right_box, bg=self.bg_color)
        self.desc_container.pack(anchor="e", fill="x")

        self.desc_label = tk.Label(
            self.desc_container,
            text="-",
            font=("Segoe UI", 8),
            fg=self.text_secondary,
            bg=self.bg_color,
            anchor="e",
            cursor="hand2",
        )
        self.desc_label.pack(side="right")
        self.desc_label.bind("<Button-1>", lambda e: self.show_edit_comment_dialog())

        self.btn_quick_edit_desc = tk.Button(
            self.desc_container,
            text="✎",
            font=("Segoe UI", 8),
            fg=self.text_muted,
            bg=self.bg_color,
            activeforeground=self.text_primary,
            activebackground=self.bg_color,
            bd=0,
            cursor="hand2",
            padx=2,
            pady=0,
            command=self.show_edit_comment_dialog,
        )
        self.btn_quick_edit_desc.pack(side="right", padx=(0, 3))

        # 3. Barra de Progresso Visual da Carga Horaria
        self.progress_container = tk.Frame(self.full_container, bg=self.bg_color)
        self.progress_container.pack(fill="x", padx=10, pady=(2, 2))

        self.progress_canvas = tk.Canvas(
            self.progress_container,
            height=5,
            bg=self.card_bg,
            highlightthickness=0,
        )
        self.progress_canvas.pack(fill="x", expand=True)
        self.progress_bar = self.progress_canvas.create_rectangle(0, 0, 0, 5, fill=self.success_color, outline="")

        self.info_row = tk.Frame(self.progress_container, bg=self.bg_color)
        self.info_row.pack(fill="x", pady=(2, 0))

        self.exit_label = tk.Label(
            self.info_row,
            text="Saída estimada: ~--:--",
            font=("Segoe UI", 7, "bold"),
            fg=self.accent_color,
            bg=self.bg_color,
        )
        self.exit_label.pack(side="left")

        self.pct_label = tk.Label(
            self.info_row,
            text="0%",
            font=("Segoe UI", 7),
            fg=self.text_secondary,
            bg=self.bg_color,
        )
        self.pct_label.pack(side="right")

        # 4. Rodape: Botoes de Acao Rápida
        self.footer_frame = tk.Frame(self.full_container, bg=self.bg_color)
        self.footer_frame.pack(fill="x", padx=10, pady=(2, 6), side="bottom")

        self.btn_play_pause = tk.Button(
            self.footer_frame,
            text="Pausar",
            font=("Segoe UI", 8, "bold"),
            bg=self.btn_bg,
            fg=self.text_primary,
            activebackground=self.border_strong,
            activeforeground=self.text_primary,
            bd=0,
            cursor="hand2",
            padx=9,
            pady=2,
            command=self.toggle_pause,
        )
        self.btn_play_pause.pack(side="left", padx=(0, 5))

        self.btn_switch = tk.Button(
            self.footer_frame,
            text="Trocar Chamado",
            font=("Segoe UI", 8),
            bg=self.btn_bg,
            fg=self.accent_color,
            activebackground=self.border_strong,
            activeforeground=self.text_primary,
            bd=0,
            cursor="hand2",
            padx=7,
            pady=2,
            command=self.show_switch_dialog,
        )
        self.btn_switch.pack(side="left", padx=(0, 5))

        self.btn_finish = tk.Button(
            self.footer_frame,
            text="Encerrar Dia",
            font=("Segoe UI", 7, "bold"),
            bg=self.card_bg,
            fg=self.success_color,
            activebackground=self.border_strong,
            activeforeground=self.text_primary,
            bd=0,
            cursor="hand2",
            padx=6,
            pady=2,
            command=self.confirm_finish_day,
        )
        self.btn_finish.pack(side="left")

        self.hotkey_hint = tk.Label(
            self.footer_frame,
            text="Ctrl+Alt+J",
            font=("Segoe UI", 7),
            fg=self.text_muted,
            bg=self.bg_color,
        )
        self.hotkey_hint.pack(side="right")

        # ==================== MODO COMPACTO (MICRO WIDGET) ====================
        self.compact_frame = tk.Frame(self.main_frame, bg=self.bg_color)

        self.compact_status_canvas = tk.Canvas(self.compact_frame, width=10, height=10, bg=self.bg_color, highlightthickness=0)
        self.compact_status_canvas.pack(side="left", padx=(6, 4), pady=5)
        self.compact_status_dot = self.compact_status_canvas.create_oval(1, 1, 9, 9, fill=self.success_color, outline="")

        self.compact_timer_label = tk.Label(
            self.compact_frame,
            text="00:00:00",
            font=("Segoe UI", 12, "bold"),
            fg=self.text_primary,
            bg=self.bg_color,
        )
        self.compact_timer_label.pack(side="left", padx=(2, 8))

        self.compact_ticket_label = tk.Label(
            self.compact_frame,
            text="SEM_TICKET",
            font=("Segoe UI", 9, "bold"),
            fg=self.accent_color,
            bg=self.bg_color,
            cursor="hand2",
        )
        self.compact_ticket_label.pack(side="left", padx=(0, 8))
        self.compact_ticket_label.bind("<Button-1>", lambda e: self.show_switch_dialog())

        self.btn_compact_pause = tk.Button(
            self.compact_frame,
            text="Pausar",
            font=("Segoe UI", 7, "bold"),
            bg=self.btn_bg,
            fg=self.text_primary,
            bd=0,
            cursor="hand2",
            padx=6,
            pady=1,
            command=self.toggle_pause,
        )
        self.btn_compact_pause.pack(side="right", padx=(2, 4))

        self.btn_compact_expand = tk.Button(
            self.compact_frame,
            text="[+]",
            font=("Segoe UI", 7, "bold"),
            bg=self.bg_color,
            fg=self.accent_color,
            bd=0,
            cursor="hand2",
            padx=4,
            pady=1,
            command=self.toggle_compact_mode,
        )
        self.btn_compact_expand.pack(side="right", padx=2)

    def _bind_drag_events(self) -> None:
        """Permite arrastar a janela segurando o cabecalho ou a barra principal."""
        drag_widgets = (
            self.header_frame,
            self.title_label,
            self.status_label,
            self.compact_frame,
            self.compact_timer_label,
        )
        for widget in drag_widgets:
            widget.bind("<ButtonPress-1>", self._on_drag_start)
            widget.bind("<B1-Motion>", self._on_drag_motion)
            widget.bind("<ButtonRelease-1>", self._on_drag_release)

    def _on_drag_start(self, event: tk.Event) -> None:
        self.drag_start_x = event.x
        self.drag_start_y = event.y

    def _on_drag_motion(self, event: tk.Event) -> None:
        deltax = event.x - self.drag_start_x
        deltay = event.y - self.drag_start_y
        x = self.root.winfo_x() + deltax
        y = self.root.winfo_y() + deltay
        self.root.geometry(f"+{x}+{y}")

    def _on_drag_release(self, event: tk.Event) -> None:
        save_position(self.root.winfo_x(), self.root.winfo_y())

    def toggle_compact_mode(self) -> None:
        """Alterna entre o modo detalhado e o modo micro compacto."""
        self.is_compact = not self.is_compact
        cur_x = self.root.winfo_x()
        cur_y = self.root.winfo_y()

        if self.is_compact:
            self.full_container.pack_forget()
            self.compact_frame.pack(fill="both", expand=True)
            self.root.geometry(f"{WINDOW_WIDTH}x{COMPACT_HEIGHT}+{cur_x}+{cur_y}")
            self.btn_mode.configure(text="Mais", fg=self.accent_color)
        else:
            self.compact_frame.pack_forget()
            self.full_container.pack(fill="both", expand=True)
            self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{cur_x}+{cur_y}")
            self.btn_mode.configure(text="Mini", fg=self.text_secondary)
        self.update_state()

    def toggle_always_on_top(self) -> None:
        """Alterna a fixacao no topo."""
        self.always_on_top = not self.always_on_top
        self.root.attributes("-topmost", self.always_on_top)
        self.btn_pin.configure(
            text="Topo: Sim" if self.always_on_top else "Topo: Nao",
            fg=self.accent_color if self.always_on_top else self.text_secondary,
        )

    def open_web_panel(self) -> None:
        """Abre o painel web no navegador padrao."""
        webbrowser.open("http://127.0.0.1:8765")

    def toggle_pause(self) -> None:
        """Pausa ou retoma a contagem de tempo."""
        state = self.state_mgr.load_state()
        if state.status == "RUNNING":
            self.engine.manual_pause()
        else:
            self.engine.manual_start()
        self.update_state()

    def confirm_finish_day(self) -> None:
        """Solicita confirmacao rapida para encerrar o expediente e transmitir o worklog."""
        dlg = tk.Toplevel(self.root)
        dlg.title("Finalizar Expediente")
        dlg.attributes("-topmost", True)
        dlg.resizable(False, False)
        dlg.configure(bg=self.bg_color)

        dw, dh = 310, 135
        x = self.root.winfo_x() + 30
        y = self.root.winfo_y() + 20
        dlg.geometry(f"{dw}x{dh}+{x}+{y}")
        _apply_dark_title_bar(dlg, dark=self.is_dark_theme)

        state = self.state_mgr.load_state()
        tot_str = format_duration(state.get_total_seconds())

        tk.Label(
            dlg,
            text="Encerrar Expediente de Hoje?",
            font=("Segoe UI", 9, "bold"),
            fg=self.text_primary,
            bg=self.bg_color,
        ).pack(anchor="w", padx=14, pady=(12, 2))

        tk.Label(
            dlg,
            text=f"Total trabalhado acumulado: {tot_str}\nO cronômetro será finalizado e enviado ao Jira.",
            font=("Segoe UI", 8),
            fg=self.text_secondary,
            bg=self.bg_color,
            justify="left",
        ).pack(anchor="w", padx=14, pady=(0, 10))

        btn_box = tk.Frame(dlg, bg=self.bg_color)
        btn_box.pack(fill="x", padx=14, pady=4)

        def do_finish():
            dlg.destroy()
            self.engine.manual_log()
            self.update_state()

        btn_ok = tk.Button(
            btn_box,
            text="Sim, Encerrar",
            font=("Segoe UI", 8, "bold"),
            bg=self.btn_primary_bg,
            fg=self.text_primary if not self.is_dark_theme else "#ffffff",
            bd=0,
            padx=10,
            pady=3,
            cursor="hand2",
            command=do_finish,
        )
        btn_ok.pack(side="right", padx=(6, 0))

        btn_no = tk.Button(
            btn_box,
            text="Cancelar",
            font=("Segoe UI", 8),
            bg=self.btn_bg,
            fg=self.text_secondary,
            bd=0,
            padx=10,
            pady=3,
            cursor="hand2",
            command=dlg.destroy,
        )
        btn_no.pack(side="right")
        dlg.bind("<Escape>", lambda e: dlg.destroy())

    def show_edit_comment_dialog(self) -> None:
        """Abre modal rapido para atualizar a descricao da atividade corrente."""
        state = self.state_mgr.load_state()
        cur_issue = (self.engine.get_active_issue() or self.config.jira.default_issue or "SEM_TICKET").strip().upper()
        cur_desc = state.get_issue_comment(cur_issue)

        dlg = tk.Toplevel(self.root)
        dlg.title(f"Descrição - {cur_issue}")
        dlg.attributes("-topmost", True)
        dlg.resizable(False, False)
        dlg.configure(bg=self.bg_color)

        dw, dh = 330, 140
        x = self.root.winfo_x() + 20
        y = self.root.winfo_y() + 20
        dlg.geometry(f"{dw}x{dh}+{x}+{y}")
        _apply_dark_title_bar(dlg, dark=self.is_dark_theme)

        tk.Label(
            dlg,
            text=f"Descrição da atividade em {cur_issue}:",
            font=("Segoe UI", 8, "bold"),
            fg=self.text_primary,
            bg=self.bg_color,
        ).pack(anchor="w", padx=12, pady=(10, 2))

        entry_desc = tk.Entry(dlg, font=("Segoe UI", 9), bg=self.card_bg, fg=self.text_primary, insertbackground=self.text_primary, bd=1, relief="solid")
        entry_desc.insert(0, cur_desc)
        entry_desc.pack(fill="x", padx=12, pady=(0, 10))

        btn_box = tk.Frame(dlg, bg=self.bg_color)
        btn_box.pack(fill="x", padx=12, pady=4)

        def do_save():
            new_d = entry_desc.get().strip()
            state_cur = self.state_mgr.load_state()
            state_cur.set_issue_comment(cur_issue, new_d)
            self.state_mgr.save_state(state_cur)
            self.update_state()
            dlg.destroy()

        btn_confirm = tk.Button(
            btn_box,
            text="Salvar",
            font=("Segoe UI", 8, "bold"),
            bg=self.btn_primary_bg,
            fg=self.text_primary if not self.is_dark_theme else "#ffffff",
            bd=0,
            padx=12,
            pady=3,
            cursor="hand2",
            command=do_save,
        )
        btn_confirm.pack(side="right", padx=(6, 0))

        btn_cancel = tk.Button(
            btn_box,
            text="Cancelar",
            font=("Segoe UI", 8),
            bg=self.btn_bg,
            fg=self.text_secondary,
            bd=0,
            padx=10,
            pady=3,
            cursor="hand2",
            command=dlg.destroy,
        )
        btn_cancel.pack(side="right")

        entry_desc.focus_set()
        entry_desc.select_range(0, tk.END)
        dlg.bind("<Return>", lambda e: do_save())
        dlg.bind("<Escape>", lambda e: dlg.destroy())

    def show_switch_dialog(self) -> None:
        """Abre uma janela modal compacta para alternar o chamado ativo com suporte a tickets recentes."""
        dlg = tk.Toplevel(self.root)
        dlg.title("Trocar Chamado Ativo")
        dlg.attributes("-topmost", True)
        dlg.resizable(False, False)
        dlg.configure(bg=self.bg_color)

        dw, dh = 330, 195
        x = self.root.winfo_x() + 20
        y = self.root.winfo_y() + 15
        dlg.geometry(f"{dw}x{dh}+{x}+{y}")
        _apply_dark_title_bar(dlg, dark=self.is_dark_theme)

        state = self.state_mgr.load_state()
        cur_issue = (state.target_issue or self.config.jira.default_issue or "SEM_TICKET").strip().upper()
        cur_desc = state.get_issue_comment(cur_issue)

        # Monta lista de tickets recentes de hoje e configuracao padrao
        recent_issues = []
        for k in state.get_seconds_by_issue().keys():
            if k and k not in ("SEM_TICKET", "") and k not in recent_issues:
                recent_issues.append(k)
        if self.config.jira.default_issue and self.config.jira.default_issue not in recent_issues:
            recent_issues.append(self.config.jira.default_issue)
        if cur_issue not in recent_issues and cur_issue != "SEM_TICKET":
            recent_issues.insert(0, cur_issue)

        tk.Label(
            dlg,
            text="Chave do Chamado (selecione ou digite):",
            font=("Segoe UI", 8, "bold"),
            fg=self.text_primary,
            bg=self.bg_color,
        ).pack(anchor="w", padx=12, pady=(10, 2))

        combo_key = ttk.Combobox(dlg, values=recent_issues, font=("Segoe UI", 9))
        combo_key.set(cur_issue)
        combo_key.pack(fill="x", padx=12, pady=(0, 6))

        tk.Label(
            dlg,
            text="Descrição da atividade (opcional):",
            font=("Segoe UI", 8),
            fg=self.text_secondary,
            bg=self.bg_color,
        ).pack(anchor="w", padx=12, pady=(2, 2))

        entry_desc = tk.Entry(dlg, font=("Segoe UI", 9), bg=self.card_bg, fg=self.text_primary, insertbackground=self.text_primary, bd=1, relief="solid")
        entry_desc.insert(0, cur_desc)
        entry_desc.pack(fill="x", padx=12, pady=(0, 10))

        def on_combo_select(event=None):
            k = clean_jira_issue_key(combo_key.get().strip().upper())
            if k:
                saved_c = state.get_issue_comment(k)
                entry_desc.delete(0, tk.END)
                if saved_c:
                    entry_desc.insert(0, saved_c)

        combo_key.bind("<<ComboboxSelected>>", on_combo_select)

        btn_box = tk.Frame(dlg, bg=self.bg_color)
        btn_box.pack(fill="x", padx=12, pady=4)

        def do_switch():
            new_k = clean_jira_issue_key(combo_key.get().strip().upper())
            new_d = entry_desc.get().strip()
            if new_k:
                self.engine.switch_ticket(new_k, comment=new_d if new_d else None)
                self.update_state()
            dlg.destroy()

        btn_confirm = tk.Button(
            btn_box,
            text="Confirmar",
            font=("Segoe UI", 8, "bold"),
            bg=self.btn_primary_bg,
            fg=self.text_primary if not self.is_dark_theme else "#ffffff",
            bd=0,
            padx=12,
            pady=3,
            cursor="hand2",
            command=do_switch,
        )
        btn_confirm.pack(side="right", padx=(6, 0))

        btn_cancel = tk.Button(
            btn_box,
            text="Cancelar",
            font=("Segoe UI", 8),
            bg=self.btn_bg,
            fg=self.text_secondary,
            bd=0,
            padx=10,
            pady=3,
            cursor="hand2",
            command=dlg.destroy,
        )
        btn_cancel.pack(side="right")

        combo_key.focus_set()
        dlg.bind("<Return>", lambda e: do_switch())
        dlg.bind("<Escape>", lambda e: dlg.destroy())

    def update_state(self) -> None:
        """Loop de atualizacao do cronometro e informacoes em tempo real."""
        try:
            state = self.state_mgr.load_state()
            cfg = BotConfig.load()
            profile = cfg.get_active_profile()

            # Sincroniza dinamicamente o tema caso tenha sido alterado no painel web
            theme_pref = getattr(cfg, "theme", "auto") or "auto"
            eff_theme = get_effective_theme(theme_pref)
            if eff_theme != getattr(self, "current_theme", None):
                self.apply_theme(eff_theme)

            total_sec = state.get_total_seconds()
            status = state.status

            # Formata tempo acumulado HH:MM:SS
            h = total_sec // 3600
            m = (total_sec % 3600) // 60
            s = total_sec % 60
            timer_text = f"{h:02d}:{m:02d}:{s:02d}"
            self.timer_label.configure(text=timer_text)
            self.compact_timer_label.configure(text=timer_text)

            # Meta e percentual
            target_sec = int(profile.target_hours * 3600)
            pct = min(100, round((total_sec / target_sec) * 100)) if target_sec > 0 else 0
            remaining_sec = max(0, target_sec - total_sec)
            rem_h = remaining_sec // 3600
            rem_m = (remaining_sec % 3600) // 60
            rem_str = f"{rem_h}h {rem_m:02d}m" if remaining_sec > 0 else "Cumprida!"

            self.meta_label.configure(text=f"Meta: {profile.target_hours}h ({pct}%) • Restam: {rem_str}")
            self.pct_label.configure(text=f"{pct}%")

            # Status e cor do ponto
            if status == "RUNNING":
                dot_color = self.success_color
                status_text = "Em execucao"
                self.btn_play_pause.configure(text="Pausar", bg=self.btn_bg, fg=self.text_primary)
                self.btn_compact_pause.configure(text="Pausar", bg=self.btn_bg, fg=self.text_primary)
            elif status == "PAUSED_LUNCH":
                dot_color = self.warning_color
                status_text = "Pausa Almoco"
                self.btn_play_pause.configure(text="Retomar", bg=self.success_color, fg="#ffffff")
                self.btn_compact_pause.configure(text="Retomar", bg=self.success_color, fg="#ffffff")
            elif status == "COMPLETED":
                dot_color = self.purple_color
                status_text = "Concluido"
                self.btn_play_pause.configure(text="Retomar", bg=self.success_color, fg="#ffffff")
                self.btn_compact_pause.configure(text="Retomar", bg=self.success_color, fg="#ffffff")
            else:
                dot_color = self.warning_color
                status_text = "Pausado"
                self.btn_play_pause.configure(text="Retomar", bg=self.success_color, fg="#ffffff")
                self.btn_compact_pause.configure(text="Retomar", bg=self.success_color, fg="#ffffff")

            self.status_canvas.itemconfig(self.status_dot, fill=dot_color)
            self.compact_status_canvas.itemconfig(self.compact_status_dot, fill=dot_color)
            self.status_label.configure(text=status_text, fg=dot_color if status != "RUNNING" else self.text_primary)

            # Ticket ativo e descricao
            active_issue = (self.engine.get_active_issue() or cfg.jira.default_issue or "SEM_TICKET").strip().upper()
            self.ticket_label.configure(text=active_issue)
            self.compact_ticket_label.configure(text=active_issue)

            comment = state.get_issue_comment(active_issue)
            if not comment:
                comment = "Sem descrição cadastrada"
            if len(comment) > 26:
                comment = comment[:23] + "..."
            self.desc_label.configure(text=comment)

            # Barra de progresso visual
            try:
                c_w = self.progress_canvas.winfo_width()
                if c_w <= 10:
                    c_w = WINDOW_WIDTH - 24
                bar_w = max(0, min(c_w, int(c_w * (pct / 100.0))))
                fill_color = self.warning_color if pct >= 100 else (self.success_color if pct >= 80 else self.accent_color)
                self.progress_canvas.coords(self.progress_bar, 0, 0, bar_w, 5)
                self.progress_canvas.itemconfig(self.progress_bar, fill=fill_color)
            except Exception:
                pass

            # Previsao de saida estimada
            try:
                now_dt = datetime.now()
                ls_time = profile.get_planned_lunch_start_time()
                le_time = profile.get_planned_lunch_end_time()
                lunch_extra = 0
                # Se ainda nao almocou e o horario atual for antes da pausa planejada
                if status == "RUNNING" and now_dt.time() < ls_time:
                    lunch_extra = int((datetime.combine(now_dt.date(), le_time) - datetime.combine(now_dt.date(), ls_time)).total_seconds())

                est_exit_dt = now_dt + timedelta(seconds=remaining_sec + lunch_extra)
                est_hm = est_exit_dt.strftime("%H:%M")
                if remaining_sec <= 0:
                    self.exit_label.configure(text="Meta diária atingida!", fg=self.success_color)
                else:
                    self.exit_label.configure(text=f"Saída estimada: ~{est_hm} (Restam: {rem_str})", fg=self.accent_color)
            except Exception:
                pass

            # Exibe botao "Encerrar Dia" com destaque quando atingir 80% da carga
            if pct >= 80:
                self.btn_finish.pack(side="left")
            else:
                self.btn_finish.pack(side="left")

        except Exception as e:
            logger.debug(f"Erro no ciclo de atualizacao do widget: {e}")

        # Agenda proxima atualizacao em 1000ms
        self.root.after(1000, self.update_state)


def run_mini_window() -> None:
    """Executa a aplicacao da mini janela flutuante na thread principal."""
    _attach_to_interactive_desktop()
    if bring_existing_mini_window_to_top():
        logger.info("Janela existente do widget trazida para primeiro plano.")
        return

    root = tk.Tk()
    app = MiniWidgetApp(root)

    # Forca primeiro plano e foco no Windows
    root.attributes("-topmost", True)
    root.lift()
    root.focus_force()
    root.update()

    try:
        user32 = ctypes.windll.user32
        frame_str = root.wm_frame()
        hwnd = int(frame_str, 16) if frame_str else root.winfo_id()
        user32.AllowSetForegroundWindow(-1)
        user32.ShowWindow(hwnd, 5)  # SW_SHOW
        user32.SetForegroundWindow(hwnd)
        user32.BringWindowToTop(hwnd)
    except Exception:
        pass

    root.mainloop()
    sys.exit(0)


def launch_mini_window(detached: bool = True) -> None:
    """Dispara a mini janela em processo independente ou em primeiro plano."""
    if bring_existing_mini_window_to_top():
        logger.info("Janela existente do widget trazida para primeiro plano.")
        return

    if not detached:
        run_mini_window()
        return

    python_exe = sys.executable
    pythonw = Path(python_exe).parent / "pythonw.exe"
    exe = str(pythonw) if pythonw.exists() else python_exe
    script = Path(__file__).resolve()

    env = os.environ.copy()
    env["PYTHONPATH"] = str(script.parent) + os.pathsep + env.get("PYTHONPATH", "")
    env["PATH"] = str(Path(exe).parent) + os.pathsep + env.get("PATH", "")

    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0

    err_log_path = Path.home() / ".jirabot" / "mini_window_err.log"
    err_log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(err_log_path, "a", encoding="utf-8") as err_file:
        subprocess.Popen(
            [exe, str(script)],
            cwd=str(script.parent),
            env=env,
            creationflags=creationflags,
            stdout=err_file,
            stderr=err_file,
            stdin=subprocess.DEVNULL,
        )


if __name__ == "__main__":
    run_mini_window()
