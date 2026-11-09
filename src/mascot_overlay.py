"""Desktop pet Windows: PNGs em cache e física independente do daemon.

Entrada direta: python -m src.mascot_overlay demo --theme normal
"""
import random
import ctypes
from ctypes import wintypes
from pathlib import Path
import sys
import time

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mascote_runtime.control import read_json, update_preferences
from mascote_runtime.native import root_handle
from mascote_runtime.window import MascotWindow, work_area

WALK_SPEED = 10
PLAYBACK_RATE = 2 / 3


class PetPhysics:
    """Movimentação testável, em pixels por segundo e com relógio injetado."""
    def __init__(self, rng=None):
        self.rng = rng or random.Random()
        self.mode = "idle"
        self.until = 0.0
        self.direction = 1
        self.last_tick = None
        self.fraction = 0.0
        self.hanging = False
        self.remaining = []
        self.action_space = None
        self.falling = False
        self.velocity_y = 0.0
        self.fall_fraction = 0.0
        self.fall_origin = 0
        self.fall_height = 0
        self.high_fall = False
        self.recovery_seconds = 0.0
        self.recovery_elapsed = None

    def drop(self, x, y, size, area, monitor_top, animate_fall=False):
        self.mode, self.until, self.last_tick, self.fraction = "idle", 0.0, None, 0.0
        left, top, right, bottom = area
        x = max(left, min(x, right - size))
        self.hanging = y <= monitor_top + 20
        self.velocity_y = self.fall_fraction = 0.0
        self.recovery_elapsed = None
        self.high_fall = False
        y = max(top, min(y, bottom - size))
        self.fall_origin = y
        self.fall_height = bottom - size - y
        self.falling = not self.hanging and self.fall_height > 0
        self.high_fall = self.falling and animate_fall and self.recovery_seconds > 0 and self.fall_height >= size
        if self.hanging:
            return x, monitor_top
        return x, y

    def step(self, now, x, y, size, area, active=True, reduced=False, override=None):
        dt = 0 if self.last_tick is None else max(0, min(now - self.last_tick, .25))
        self.last_tick = now
        left, top, right, bottom = area
        if not active or reduced or not self.recovery_seconds:
            self.high_fall = False
            self.recovery_elapsed = None
        if self.falling and active and not reduced:
            self.velocity_y = min(240, self.velocity_y + 360 * dt)
            self.fall_fraction += self.velocity_y * dt
            distance = int(self.fall_fraction)
            self.fall_fraction -= distance
            y = min(bottom - size, y + distance)
            self.falling = y < bottom - size
            if self.falling:
                if self.high_fall:
                    return "fall", x, y, False
                return override or "idle", x, y, False
            self.velocity_y = self.fall_fraction = 0.0
            if self.high_fall:
                self.recovery_elapsed = 0.0
                dt = 0.0
            self.high_fall = False
        if self.recovery_elapsed is not None:
            self.recovery_elapsed += dt
            if self.recovery_elapsed < self.recovery_seconds:
                return "recover", x, y, False
            self.recovery_elapsed = None
        if override is not None:
            return override, x, y, False
        if self.hanging:
            return "swing", x, y, False
        on_ground = y >= bottom - size - 15
        if reduced or not active:
            return "idle", x, y, False
        if on_ground:
            y = bottom - size
        if now >= self.until:
            space = ("idle", "walk", "sit", "drink", "backpack") if on_ground else ("idle", "sit")
            if self.action_space != space or not self.remaining:
                self.remaining = list(space)
                self.action_space = space
            candidates = [a for a in self.remaining if a != self.mode] or self.remaining
            chosen = self.rng.choice(candidates)
            self.mode = chosen if chosen in candidates else candidates[0]
            self.remaining.remove(self.mode)
            durations = {"idle": (5, 8), "sit": (8, 12), "drink": (6, 8), "backpack": (6, 8), "walk": (4, 7)}
            self.until = now + self.rng.uniform(*durations[self.mode])
        if self.mode == "walk" and on_ground:
            self.fraction += dt * WALK_SPEED
            delta = int(self.fraction)
            self.fraction -= delta
            x += self.direction * delta
            if x <= left:
                x, self.direction = left, 1
            elif x >= right - size:
                x, self.direction = right - size, -1
            return "walk", x, y, self.direction < 0
        return self.mode, x, y, False


class DesktopPetWindow(MascotWindow):
    """Reutiliza controles, mutex e transparência sem duplicar o cronômetro."""
    def __init__(self, *args, **kwargs):
        self.physics = PetPhysics()
        self.mirrored_walk = []
        self._move_handle = None
        self._animation_after = None
        self._animation_paused = False
        super().__init__(*args, **kwargs)
        if not getattr(self, "running", True):
            return
        if sys.platform == "win32":
            try:
                if self.root.winfo_exists():
                    self._move_handle = root_handle(self.root)
            except Exception:
                pass
        saved = self.prefs.get("position") or [self.x, self.y]
        physical = work_area(*saved, physical=True)
        x, y = self.physics.drop(self.x, self.y, self.size, work_area(self.x, self.y), physical[1])
        if (x, y) != (self.x, self.y):
            self.place(x, y)

    def place(self, x, y):
        # Em movimento, não pedir layout Tk + repintura antes do movimento
        # nativo: isso reposicionava a mesma janela duas vezes a cada quadro.
        handle = getattr(self, "_move_handle", None)
        if handle and sys.platform == "win32":
            self.x, self.y = int(x), int(y)
            user = ctypes.windll.user32
            user.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
            if user.SetWindowPos(handle, None, self.x, self.y, 0, 0, 0x0015):
                return
        super().place(x, y)

    def refresh_model(self):
        previous = (getattr(self, "theme", None), getattr(self, "size", None))
        super().refresh_model()
        if previous != (self.theme, self.size):
            from mascote_runtime.playback import AnimationPlayer
            self.player = AnimationPlayer(self.model["actions"]) if "duration_ms" in self.model["actions"]["idle"] else None
            actions = self.model["actions"]
            fall_durations = actions.get("fall", {}).get("duration_ms")
            recovery_durations = actions.get("recover", {}).get("duration_ms")
            self.physics.recovery_seconds = 0.0
            if self.player is not None and fall_durations and recovery_durations:
                self.physics.recovery_seconds = sum(recovery_durations) / 1000
            from PIL import ImageTk, ImageOps
            from mascote_runtime.catalog import load_frames
            # Somente o tema ativo e suas poses de caminhada espelhadas.
            frames = load_frames(self.model, self.size, actions=("walk",))["walk"]
            self.mirrored_walk = [ImageTk.PhotoImage(ImageOps.mirror(frame), master=self.root) for frame in frames]
            if self.physics.hanging:
                self.place(self.x, work_area(self.x, self.y, physical=True)[1])

    def move(self, event):
        if self.drag:
            mx, my, x, y = self.drag
            if not self.behavior.dragging and abs(event.x_root - mx) + abs(event.y_root - my) < 4:
                return
            previous_x = getattr(self, "_last_drag_x", mx)
            if event.x_root != previous_x:
                self._drag_flip = event.x_root < previous_x
            self._last_drag_x = event.x_root
            self.behavior.dragging = True
            px, py = x + event.x_root - mx, y + event.y_root - my
            physical = work_area(event.x_root, event.y_root, physical=True)
            area = work_area(event.x_root, event.y_root)
            self.place(max(area[0], min(px, area[2] - self.size)), max(physical[1], min(py, area[3] - self.size)))

    def release(self, event):
        if not self.behavior.dragging:
            self.drag = None
            return
        area = work_area(event.x_root, event.y_root)
        monitor = work_area(event.x_root, event.y_root, physical=True)
        x, y = self.physics.drop(self.x, self.y, self.size, area, monitor[1],
                                 animate_fall=not self.prefs["reduced_motion"])
        self.place(x, y)
        self.behavior.dragging = False
        self.drag = None
        self._last_drag_x = None
        if not self.demo:
            update_preferences({"position": [x, y]}, self.base)

    def poll(self):
        service = read_json(self.base / "mascote_service.json", {})
        if not self.demo and service and service.get("running") is False:
            self.close()  # A preferência permanece ativada para o próximo daemon.
            return
        super().poll()
        if not self.running:
            return
        locked = self.behavior.locked or self.behavior.session_locked
        if locked:
            timer = getattr(self, "_animation_after", None)
            if timer is not None:
                self.root.after_cancel(timer)
                self._animation_after = None
            self._animation_paused = True
        elif getattr(self, "_animation_paused", False):
            self._animation_paused = False
            self.frame_at = time.monotonic()
            self.physics.last_tick = None
            self.animate()

    def animate(self):
        self._animation_after = None
        if not self.running:
            return
        now = time.monotonic()
        action, _message = self.behavior.current(now)
        locked = self.behavior.locked or self.behavior.session_locked
        if locked:
            self._animation_paused = True
            return
        reduced = self.prefs["reduced_motion"]
        reaction = self.behavior.reaction is not None and self.behavior.reaction.until > now
        override = action if self.demo or self.behavior.dragging or reaction or self.behavior.active_requests or self.behavior.status in {"PAUSED_LUNCH", "PAUSED_AWAY"} else None
        action, x, y, flip = self.physics.step(now, self.x, self.y, self.size, work_area(self.x, self.y), active=not self.behavior.dragging, reduced=reduced, override=override)
        if self.behavior.dragging:
            action, flip = "walk", getattr(self, "_drag_flip", False)
        player = getattr(self, "player", None)
        if player is not None:
            immediate = self.behavior.dragging or self.physics.hanging or self.physics.falling or action == "recover" or reduced
            progress = None
            if action == "fall":
                distance = max(0, y - self.physics.fall_origin)
                progress = min(1, distance / self.physics.fall_height) ** .5
            elif action == "recover":
                progress = self.physics.recovery_elapsed / self.physics.recovery_seconds
            shown, index, remaining = player.sample(action, now, immediate=immediate, progress=progress)
            if shown != "walk" and action == "walk":
                x = self.x
            if (x, y) != (self.x, self.y):
                self.place(x, y)
            self.action, self.frame = shown, index
            mirror = not flip if self.model.get("walk_faces_left") else flip
            frames = self.mirrored_walk if shown == "walk" and mirror else self.frames[shown]
            photo = frames[0 if reduced else index]
            if photo is not getattr(self, "_displayed_photo", None):
                self.sprite.configure(image=photo)
                self._displayed_photo = photo
            delay = 40 if action == "fall" else max(1, min(100, round(remaining)))
            self._animation_after = self.root.after(500 if reduced else delay, self.animate)
            return
        if (x, y) != (self.x, self.y):
            self.place(x, y)
        if action != self.action:
            self.action, self.frame, self.frame_at = action, 0, now
        frames = self.mirrored_walk if action == "walk" and flip else self.frames.get(action, self.frames["idle"])
        fps = max(1, min(24, self.model["actions"].get(action, {}).get("fps", 12))) * PLAYBACK_RATE
        steps = int((now - self.frame_at) * fps)
        if not reduced and steps > 0:
            self.frame = (self.frame + steps) % len(frames)
            self.frame_at += steps / fps
        photo = frames[0 if reduced else self.frame]
        if photo is not getattr(self, "_displayed_photo", None):
            self.sprite.configure(image=photo)
            self._displayed_photo = photo
        # Compensar o atraso do timer Windows sem aumentar a frequência alvo.
        delay = 500 if reduced else max(1, round((self.frame_at + 1 / fps - time.monotonic()) * 1000))
        self._animation_after = self.root.after(delay, self.animate)


if __name__ == "__main__":
    from mascote_runtime.control import command
    command()
