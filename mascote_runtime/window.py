"""Janela flutuante, renderização em memória e interações do mascote."""
import ctypes
from ctypes import wintypes
from datetime import date
from pathlib import Path
import sys
import time
import tkinter as tk
import webbrowser

from .behavior import Behavior, mascot_theme
from .catalog import load_catalog, load_frames
from .native import show_sprite, single_instance
from .control import (BASE, PROJECT, atomic_json, preferences, read_json,
                      snapshot, update_preferences)


def work_area(x, y, fallback=(0, 0, 1280, 720), physical=False):
    if sys.platform != "win32":
        return fallback

    class MonitorInfo(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("monitor", wintypes.RECT),
                    ("work", wintypes.RECT), ("flags", wintypes.DWORD)]

    user = ctypes.windll.user32
    user.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
    user.MonitorFromPoint.restype = wintypes.HANDLE
    user.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MonitorInfo)]
    monitor = user.MonitorFromPoint(wintypes.POINT(x, y), 2)
    info = MonitorInfo()
    info.size = ctypes.sizeof(info)
    if user.GetMonitorInfoW(monitor, ctypes.byref(info)):
        r = info.monitor if physical else info.work
        return r.left, r.top, r.right, r.bottom
    return fallback


def clamp_position(x, y, size, area):
    left, top, right, bottom = area
    return max(left, min(x, right - size)), max(top, min(y, bottom - size))


def session_available():
    """Consulta a área de trabalho de entrada, sem trocar desktop ou permissões."""
    if sys.platform != "win32":
        return True
    user = ctypes.windll.user32
    user.OpenInputDesktop.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    user.OpenInputDesktop.restype = wintypes.HANDLE
    user.CloseDesktop.argtypes = [wintypes.HANDLE]
    desktop = user.OpenInputDesktop(0, False, 1)
    if not desktop:
        return None
    try:
        name = ctypes.create_unicode_buffer(256)
        needed = wintypes.DWORD()
        user.GetUserObjectInformationW.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
        if not user.GetUserObjectInformationW(desktop, 2, name, ctypes.sizeof(name), ctypes.byref(needed)):
            return None
        return name.value.lower() == "default"
    finally:
        user.CloseDesktop(desktop)


class MascotWindow:
    COLOR = "#010203"
    LABELS = {"idle": "Esperar", "walk": "Andar", "drink": "Beber", "sit": "Sentar",
              "backpack": "Mochila", "swing": "Balanço"}

    def __init__(self, root, base, demo=False, theme=None):
        self.root, self.base, self.demo = root, Path(base), demo
        self.started = time.monotonic()
        self.behavior = Behavior()
        self.prefs = preferences(base)
        if theme:
            self.prefs["theme"] = theme
        self.demo_theme = theme
        self.catalog = load_catalog()
        self.theme = None
        self.size = None
        self.frames = {}
        self.action = None
        self.frame = 0
        self.frame_at = 0
        self.drag = None
        self.x, self.y = 0, 0
        self.running = True
        self.event_ids = {e.get("id") for e in read_json(self.base / "mascote_events.json", [])}
        root.title("JiraBot - Mascote" + (" - Demonstração" if demo else ""))
        root.withdraw()
        # Tk precisa mapear a janela gerenciada antes da retirada da moldura.
        root.overrideredirect(False)
        root.attributes("-topmost", True)
        root.configure(bg=self.COLOR)
        if sys.platform == "win32":
            root.attributes("-transparentcolor", self.COLOR)
        self.sprite = tk.Label(root, bg=self.COLOR, bd=0, padx=0, pady=0, highlightthickness=0)
        self.sprite.pack()
        self.menu = tk.Menu(root, tearoff=False)
        self.menu.add_command(label="Abrir painel", command=lambda: webbrowser.open("http://127.0.0.1:8765"))
        self.menu.add_command(label="Abrir mini janela", command=self.open_mini)
        actions = tk.Menu(self.menu, tearoff=False)
        for action, label in self.LABELS.items():
            actions.add_command(label=label, command=lambda a=action: self.preview(a))
        self.menu.add_cascade(label="Experimentar animação", menu=actions)
        themes = tk.Menu(self.menu, tearoff=False)
        for value, label in [("auto", "Automático"), ("normal", "Normal"), ("halloween", "Halloween"), ("natal", "Natal"), ("ano_novo", "Ano Novo"), ("pascoa", "Páscoa")]:
            themes.add_command(label=label, command=lambda v=value: self.set_option("theme", v))
        self.menu.add_cascade(label="Tema", menu=themes)
        self.menu.add_command(label="Alternar movimento reduzido", command=lambda: self.set_option("reduced_motion", not self.prefs["reduced_motion"]))
        self.menu.add_separator()
        self.menu.add_command(label="Desativar mascote", command=self.disable)
        for widget in (self.sprite,):
            widget.bind("<ButtonPress-1>", self.press)
            widget.bind("<B1-Motion>", self.move)
            widget.bind("<ButtonRelease-1>", self.release)
            widget.bind("<Button-3>", self.context_menu)
        root.bind("<Escape>", lambda _e: self.disable())
        root.protocol("WM_DELETE_WINDOW", self.disable)
        self.refresh_model()
        area = work_area(0, 0, (0, 0, root.winfo_screenwidth(), root.winfo_screenheight()))
        pos = self.prefs.get("position") or [area[2] - self.size - 30, area[3] - self.size - 60]
        self.place(*clamp_position(*pos, self.size, work_area(*pos, fallback=area)))
        root.deiconify()
        self.poll()
        self.animate()

    def refresh_model(self):
        from PIL import ImageTk
        resolved = mascot_theme(self.prefs)
        if resolved not in self.catalog["models"]:
            resolved = "normal"
        size = max(96, min(320, int(self.prefs["size"])))
        if (resolved, size) == (self.theme, self.size):
            return
        model = self.catalog["models"][resolved]
        groups = load_frames(model, size)
        images = {}
        for name, frames in groups.items():
            photos = []
            for frame in frames:
                # Tk/Windows usa chave de cor; alfa binário evita borda da cor-chave.
                frame.putalpha(frame.getchannel("A").point(lambda a: 255 if a >= 160 else 0))
                photos.append(ImageTk.PhotoImage(frame, master=self.root))
            images[name] = photos
        # Trocar a imagem visível antes de liberar o cache anterior evita um
        # quadro vazio durante mudanças de tema ou tamanho.
        first = images.get(self.action, images["idle"])[0]
        self.sprite.configure(image=first)
        self._displayed_photo = first
        self.frames, self.model = images, model
        self.theme, self.size = resolved, size
        self.action = None
        self.root.geometry(f"{size}x{size}")
        if self.x or self.y:
            self.place(*clamp_position(self.x, self.y, size, work_area(self.x, self.y)))

    def place(self, x, y):
        self.x, self.y = int(x), int(y)
        self.root.geometry(f"+{max(0, self.x)}+{max(0, self.y)}")
        if sys.platform == "win32":
            self.root.update_idletasks()
            user = ctypes.windll.user32
            user.GetParent.argtypes = [wintypes.HWND]
            user.GetParent.restype = wintypes.HWND
            user.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
            hwnd = user.GetParent(self.root.winfo_id()) or self.root.winfo_id()
            user.SetWindowPos(hwnd, None, self.x, self.y, 0, 0, 0x0015)

    def set_option(self, key, value):
        if self.demo:
            self.prefs[key] = value
            if key == "theme":
                self.demo_theme = value
        else:
            self.prefs = update_preferences({key: value}, self.base)
        self.refresh_model()

    def open_mini(self):
        import subprocess
        subprocess.Popen([sys.executable, str(PROJECT / "cli.py"), "mini", "--detached"], cwd=str(PROJECT), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

    def context_menu(self, event):
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def preview(self, action):
        from .behavior import Reaction
        self.behavior.reaction = Reaction(action, "Animação: " + self.LABELS[action], time.monotonic() + 5, 25)

    def press(self, event):
        self.drag = (event.x_root, event.y_root, self.x, self.y)
        self._last_drag_x = event.x_root

    def move(self, event):
        if self.drag:
            mx, my, x, y = self.drag
            px, py = x + event.x_root - mx, y + event.y_root - my
            self.place(*clamp_position(px, py, self.size, work_area(event.x_root, event.y_root)))

    def release(self, event):
        self.behavior.dragging = False
        self.drag = None
        if not self.demo:
            update_preferences({"position": [self.x, self.y]}, self.base)

    def poll(self):
        if not self.running:
            return
        now = time.monotonic()
        if not self.demo:
            self.prefs = preferences(self.base)
            if not self.prefs["enabled"]:
                self.close()
                return
            self.behavior.snapshot(snapshot(self.base), now)
            events = read_json(self.base / "mascote_events.json", [])
            for event in events:
                eid = event.get("id")
                if eid not in self.event_ids and event.get("day") == date.today().isoformat() and time.time() - event.get("at", 0) < 120:
                    self.behavior.trigger(event.get("name"), now, eid, event.get("activity_id"))
                self.event_ids.add(eid)
            if len(self.event_ids) > 256:
                self.event_ids = {e.get("id") for e in events}
        else:
            actions = list(self.LABELS)
            self.preview(actions[int((now - self.started) / 3) % len(actions)])
        availability = True if self.demo else session_available()
        self.behavior.locked = availability is False or self.behavior.session_locked
        visible = False
        if self.behavior.locked:
            self.root.withdraw()
        else:
            visible = show_sprite(self.root, self.x, self.y, self.size, self.size, borderless=not self.demo)
        self.refresh_model()
        action, message = self.behavior.current(now)
        if self.demo:
            message = "Demonstração: " + self.LABELS[action]
        phase = "suspended" if self.behavior.locked else ("running" if visible else "error")
        if phase == "error":
            message = "O processo abriu, mas a janela não ficou visível. Reative o mascote."
        atomic_json(self.base / "mascote_runtime.json", {"phase": phase, "heartbeat": time.time(), "action": action, "render_action": self.action or action, "theme": self.theme, "message": message, "visible": visible, "session_available": availability, "position": [self.x, self.y]})
        self.root.after(1000, self.poll)

    def animate(self):
        if not self.running:
            return
        now = time.monotonic()
        action, _ = self.behavior.current(now)
        reduced = self.prefs["reduced_motion"] or self.behavior.locked
        if action != self.action:
            self.action, self.frame, self.frame_at = action, 0, now
        frames = self.frames.get(action, self.frames["idle"])
        fps = self.model["actions"].get(action, {}).get("fps", 5)
        if not reduced and now - self.frame_at >= 1 / fps:
            self.frame = (self.frame + 1) % len(frames)
            self.frame_at = now
        self.sprite.configure(image=frames[0 if reduced else self.frame])
        self.root.after(500 if reduced else 40, self.animate)

    def disable(self):
        if not self.demo:
            update_preferences({"enabled": False}, self.base)
        self.close()

    def close(self):
        if not self.running:
            return
        self.running = False
        atomic_json(self.base / "mascote_runtime.json", {"phase": "stopped", "heartbeat": time.time(), "message": ""})
        self.root.destroy()


def run(base=BASE, demo=False, seconds=0, theme=None):
    base = Path(base)
    with single_instance("Mascote", base) as acquired:
        if acquired:
            _run_window(base, demo, seconds, theme)


def _run_window(base, demo, seconds, theme):
    root = None
    try:
        root = tk.Tk()
        from src.mascot_overlay import DesktopPetWindow
        app = DesktopPetWindow(root, base, demo=demo, theme=theme)
        def callback_error(exc_type, _value, _traceback):
            import traceback
            traceback.print_exception(exc_type, _value, _traceback)
            app.running = False
            atomic_json(base / "mascote_runtime.json", {"phase": "error", "heartbeat": time.time(), "message": "Falha visual do mascote: " + exc_type.__name__})
            try:
                root.destroy()
            except tk.TclError:
                pass
        root.report_callback_exception = callback_error
        if seconds > 0:
            root.after(seconds * 1000, app.close)
        root.mainloop()
    except Exception as exc:
        atomic_json(base / "mascote_runtime.json", {"phase": "error", "heartbeat": time.time(), "message": "Falha visual do mascote: " + type(exc).__name__})
        if root:
            try:
                root.destroy()
            except tk.TclError:
                pass
        raise
