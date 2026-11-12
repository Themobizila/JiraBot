"""
Modulo de notificacoes locais para o Windows (JiraBot).
"""

from __future__ import annotations

import logging
from pathlib import Path
import subprocess
import sys

logger = logging.getLogger("JiraBot.Notifier")


def send_ticket_prompt(port: int, suggestion_id: str, enabled: bool, theme: str = "auto") -> bool:
    """Abre um aviso independente do navegador e da mini janela."""
    if not enabled:
        return False
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    try:
        subprocess.Popen(
            [str(pythonw if pythonw.exists() else sys.executable), str(Path(__file__).resolve()), str(port), suggestion_id, theme],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError:
        logger.exception("Falha ao abrir aviso de troca de ticket")
        if suggestion_id != "test":
            send_notification("JiraBot", "Há uma sugestão de troca de ticket no Painel do Dia.")
        return False
    return True


def _round_ticket_prompt(popup) -> None:
    from ctypes import windll, wintypes

    create_region = windll.gdi32.CreateRoundRectRgn
    create_region.argtypes = [wintypes.INT] * 6
    create_region.restype = wintypes.HRGN
    set_region = windll.user32.SetWindowRgn
    set_region.argtypes = [wintypes.HWND, wintypes.HRGN, wintypes.BOOL]
    set_region.restype = wintypes.INT
    delete_region = windll.gdi32.DeleteObject
    delete_region.argtypes = [wintypes.HANDLE]
    delete_region.restype = wintypes.BOOL

    hwnd = int(popup.wm_frame(), 16)
    diameter = round(popup.winfo_fpixels("0.55i"))
    region = create_region(0, 0, popup.winfo_width(), popup.winfo_height(), diameter, diameter)
    if region and not set_region(hwnd, region, True):
        delete_region(region)


def show_ticket_prompt(port: int, suggestion_id: str, theme: str = "auto") -> None:
    import tkinter as tk
    from threading import Thread
    from time import monotonic
    import winsound

    from mini_window import THEME_PALETTES, _attach_to_interactive_desktop, get_effective_theme
    from ticket_focus import local_focus_request

    def pending():
        status, payload = local_focus_request("/api/ticket-focus/pending", port=port, timeout=0.4)
        return payload.get("suggestion") if status == 200 else None

    is_test = suggestion_id == "test"
    if is_test:
        suggestion = {"issue": "TESTE-123", "summary": "Este é um aviso de demonstração."}
    else:
        try:
            suggestion = pending()
        except (OSError, ValueError):
            return
        if not suggestion or suggestion["id"] != suggestion_id:
            return

    _attach_to_interactive_desktop()
    popup = tk.Tk()
    popup.withdraw()
    popup.title("JiraBot | Troca de ticket")
    popup.overrideredirect(True)
    popup.attributes("-topmost", True)
    popup.resizable(False, False)
    palette = THEME_PALETTES[get_effective_theme(theme)]
    background, surface, border = palette["bg_card"], palette["bg_subtle"], palette["border_strong"]
    text, muted, accent = palette["text_primary"], palette["text_secondary"], palette["primary"]
    button_text = "#0a0805" if palette["is_dark"] else "#ffffff"
    card = tk.Frame(popup, bg=background, highlightthickness=1, highlightbackground=border)
    card.pack(fill="both", expand=True)
    header = tk.Frame(card, bg=background)
    header.pack(fill="x", padx=20, pady=(12, 0))
    brand = tk.Label(header, text="JiraBot", bg=background, fg=accent, font=("Segoe UI", 11, "bold"))
    brand.pack(side="left")
    drag_widgets = [header, brand]
    if is_test:
        badge = tk.Label(
            header, text="Demonstração", bg=surface, fg=muted, padx=7, pady=2, font=("Segoe UI", 9),
        )
        badge.pack(side="left", padx=(10, 0))
        drag_widgets.append(badge)
    tk.Button(
        header, text="Fechar", command=popup.destroy, bg=background, fg=muted,
        activebackground=surface, activeforeground=text, bd=0, cursor="hand2", font=("Segoe UI", 9),
    ).pack(side="right")
    drag_x = drag_y = 0

    def start_drag(event):
        nonlocal drag_x, drag_y
        drag_x = event.x_root - popup.winfo_x()
        drag_y = event.y_root - popup.winfo_y()

    def move_popup(event):
        popup.geometry(f"+{event.x_root - drag_x}+{event.y_root - drag_y}")

    for widget in drag_widgets:
        widget.configure(cursor="fleur")
        widget.bind("<ButtonPress-1>", start_drag)
        widget.bind("<B1-Motion>", move_popup)

    tk.Frame(card, bg=border, height=1).pack(fill="x", padx=20, pady=(8, 0))

    content = tk.Frame(card, bg=background)
    content.pack(fill="x", padx=20, pady=(10, 16))
    tk.Label(
        content, text="Trocar o ticket em foco?", bg=background, fg=text,
        font=("Segoe UI", 18, "bold"), anchor="w",
    ).pack(fill="x")
    ticket = tk.Frame(content, bg=surface, padx=12, pady=9)
    ticket.pack(fill="x", pady=(12, 0))
    tk.Label(
        ticket, text=suggestion["issue"], bg=surface, fg=accent,
        font=("Segoe UI", 11, "bold"), anchor="w",
    ).pack(fill="x")
    if suggestion["summary"]:
        tk.Label(
            ticket, text=suggestion["summary"], bg=surface, fg=text,
            font=("Segoe UI", 10), wraplength=352, justify="left", anchor="w",
        ).pack(fill="x", pady=(3, 0))
    actions = tk.Frame(content, bg=background)
    actions.pack(fill="x", pady=(14, 0))
    error = tk.Label(content, bg=background, fg=text, wraplength=370, justify="left", anchor="w")

    def answer(action):
        if is_test:
            popup.destroy()
            return
        try:
            status, response = local_focus_request(
                "/api/ticket-focus", {"action": action, "id": suggestion_id}, port=port, timeout=2,
            )
        except (OSError, ValueError):
            status, response = 0, {"error": "O JiraBot está indisponível."}
        if status == 200:
            popup.destroy()
        else:
            error.configure(text=response.get("error", "A sugestão não está mais disponível."))
            error.pack(fill="x", pady=(8, 0))

    tk.Button(
        actions, text="Trocar agora", command=lambda: answer("switch"), bg=accent, fg=button_text,
        activebackground=palette["primary_hover"], activeforeground=button_text, bd=0, padx=15, pady=7,
        cursor="hand2", font=("Segoe UI", 10, "bold"),
    ).pack(side="right")
    tk.Button(
        actions, text="Ignorar", command=lambda: answer("ignore"), bg=surface, fg=text,
        activebackground=border, activeforeground=text, bd=0, padx=15, pady=7,
        cursor="hand2", font=("Segoe UI", 10),
    ).pack(side="right", padx=(0, 8))
    popup.bind("<Escape>", lambda _event: popup.destroy())
    popup.update_idletasks()
    width = max(420, popup.winfo_reqwidth())
    height = popup.winfo_reqheight()
    popup.geometry(f"+{max(0, popup.winfo_screenwidth() - width - 32)}+48")
    popup.minsize(width, height)
    rounded_size = None

    def round_on_resize(event):
        nonlocal rounded_size
        size = (event.width, event.height)
        if event.widget is popup and size != rounded_size:
            rounded_size = size
            _round_ticket_prompt(popup)

    popup.bind("<Configure>", round_on_resize)
    popup.deiconify()

    def play_alert():
        audio = Path(__file__).resolve().parent / "assets" / "notifications" / "palmeiras-radio-globo.wav"
        try:
            winsound.PlaySound(str(audio), winsound.SND_FILENAME | winsound.SND_NODEFAULT)
        except RuntimeError:
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)

    deadline = monotonic() + 300

    def refresh():
        try:
            current = pending()
            if not current or current["id"] != suggestion_id:
                popup.destroy()
                return
        except (OSError, ValueError):
            pass
        if monotonic() >= deadline:
            popup.destroy()
        else:
            popup.after(1500, refresh)

    if is_test:
        popup.after(20000, popup.destroy)
    else:
        popup.after(1500, refresh)
    Thread(target=play_alert, daemon=True).start()
    popup.mainloop()


def send_notification(title: str, message: str, enabled: bool = True) -> None:
    """Envia uma notificacao nativa no Windows usando PowerShell/BurntToast sem travar a thread."""
    if not enabled:
        return

    logger.info(f"Notificacao: [{title}] {message}")

    # Escapar aspas simples para script PowerShell
    safe_title = title.replace("'", "''")
    safe_msg = message.replace("'", "''")

    ps_script = f"""
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
    [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
    $template = @"
    <toast>
        <visual>
            <binding template="ToastGeneric">
                <text>{safe_title}</text>
                <text>{safe_msg}</text>
            </binding>
        </visual>
    </toast>
"@
    $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
    $xml.LoadXml($template)
    $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
    $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("JiraBot")
    $notifier.Show($toast)
    """

    try:
        # Executa em segundo plano sem janela
        subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
    except Exception as e:
        logger.debug(f"Falha ao enviar notificacao PowerShell: {e}")


if __name__ == "__main__":
    show_ticket_prompt(int(sys.argv[1]), sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "auto")
