"""Testes isolados: dados fictícios e nenhum acesso ao Jira."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch, Mock

from .behavior import Behavior, effective_theme
from .catalog import load_catalog, load_frames, rectangles, align_frames, character_anchor, sprite_rectangles
from . import control
from .window import clamp_position


class BehaviorTests(unittest.TestCase):
    def setUp(self):
        self.engine = Behavior()

    def state(self, status, ticket="TEST-1", day="2026-10-30", now=0):
        self.engine.snapshot({"status": status, "target_issue": ticket, "date_str": day}, now)

    def test_states_and_no_false_success(self):
        for status, action in [("RUNNING", "idle"), ("PAUSED_LUNCH", "drink"), ("PAUSED_AWAY", "sit"), ("COMPLETED", "sit")]:
            self.state(status)
            self.assertEqual(self.engine.current(0)[0], action)
        self.assertNotIn("sucesso", self.engine.current(0)[1])

    def test_reaction_returns_to_current_state(self):
        self.state("RUNNING")
        self.engine.trigger("ticket", 0)
        self.state("PAUSED_LUNCH", now=1)
        self.assertEqual(self.engine.current(1)[0], "backpack")
        self.assertEqual(self.engine.current(4)[0], "drink")

    def test_error_priority_and_deduplication(self):
        self.engine.trigger("worklog_error", 0, "error-1")
        self.assertFalse(self.engine.trigger("click", 1))
        self.assertFalse(self.engine.trigger("worklog_error", 10, "error-1"))
        self.assertEqual(self.engine.current(11)[0], "idle")

    def test_day_change_drops_reaction_and_ticket_event(self):
        self.state("RUNNING")
        self.engine.trigger("worklog_success", 0)
        self.state("IDLE", ticket="TEST-2", day="2026-10-31", now=1)
        self.assertEqual(self.engine.current(1)[0], "idle")

    def test_first_snapshot_does_not_replay_ticket(self):
        self.state("RUNNING")
        self.assertIsNone(self.engine.reaction)
        self.state("RUNNING", ticket="TEST-2", now=1)
        self.assertEqual(self.engine.current(1)[0], "backpack")

    def test_drag_lock_priorities(self):
        self.engine.trigger("worklog_success", 0)
        self.engine.dragging = True
        self.assertEqual(self.engine.current(1)[0], "walk")
        self.engine.locked = True
        self.assertEqual(self.engine.current(1)[0], "sit")

    def test_seasons_and_fallback(self):
        self.assertEqual(effective_theme("auto", datetime(2026, 10, 30)), "halloween")
        self.assertEqual(effective_theme("auto", datetime(2026, 12, 30)), "ano_novo")
        self.assertEqual(effective_theme("auto", datetime(2026, 12, 25)), "natal")
        self.assertEqual(effective_theme("pascoa"), "pascoa")
        self.assertEqual(effective_theme("light"), "normal")


class CatalogTests(unittest.TestCase):
    def test_all_themes_frames_in_bounds(self):
        from PIL import Image
        data = load_catalog()
        self.assertEqual(set(data["models"]), {"normal", "halloween", "natal", "ano_novo", "pascoa"})
        for model in data["models"].values():
            self.assertTrue(model["sprite_frames"])
            for action in model["actions"].values():
                if "duration_ms" in action:
                    self.assertEqual(len(action["files"]), len(action["duration_ms"]))
                else:
                    self.assertEqual(len(action["files"]), 16)
                for file in action["files"]:
                    with Image.open(file) as im:
                        self.assertEqual(im.mode, "RGBA")
            groups = load_frames(model, 128)
            self.assertEqual(sum(len(v) for v in groups.values()), sum(len(a["files"]) for a in model["actions"].values()))
            for frames in groups.values():
                for frame in frames:
                    self.assertEqual(frame.size, (128, 128))
                    self.assertIsNotNone(frame.getchannel("A").getbbox())

    def test_explicit_rectangles(self):
        self.assertEqual(rectangles({"frames": [[0, 0.5, 0.5, 1]]}, 100, 200), [(0, 100, 50, 200)])

    def test_mirrored_cache_reads_only_the_active_walk_frames(self):
        from PIL import Image
        model = load_catalog()["models"]["ano_novo"]
        with patch("PIL.Image.open", wraps=Image.open) as opened:
            groups = load_frames(model, 160, actions=("walk",))
        self.assertEqual(set(groups), {"walk"})
        self.assertEqual(len(groups["walk"]), 16)
        self.assertEqual(opened.call_count, 16)
        self.assertTrue(all("ano_novo" in str(call.args[0]) for call in opened.call_args_list))

    def test_band_division_does_not_cut_neighboring_pose(self):
        from PIL import Image, ImageDraw
        image = Image.new("RGBA", (100, 30))
        draw = ImageDraw.Draw(image)
        draw.rectangle((10, 0, 55, 29), fill="red")
        draw.rectangle((65, 0, 90, 29), fill="blue")
        boxes = sprite_rectangles({"band": [0, 1], "count": 2}, image)
        self.assertTrue(55 < boxes[0][2] < 65)
        self.assertEqual(boxes[0][2], boxes[1][0])
        explicit = {"frames": [[0, 0, 0.5, 1], [0.5, 0, 1, 1]]}
        self.assertEqual(sprite_rectangles(explicit, image), [(0, 0, 50, 30), (50, 0, 100, 30)])

    def test_invalid_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "invalid.json"
            path.write_text('{"version": 2, "models": {}}')
            with self.assertRaises(ValueError):
                load_catalog(path)

    def test_clamp_negative_monitor_and_offscreen(self):
        self.assertEqual(clamp_position(-2200, 1000, 180, (-1920, 0, 0, 1080)), (-1920, 900))

    def test_transparent_margins_do_not_move_or_mirror_character(self):
        from PIL import Image, ImageDraw
        frames = []
        for x, y in [(4, 4), (15, 9), (25, 2)]:
            image = Image.new("RGBA", (60, 40))
            draw = ImageDraw.Draw(image)
            draw.rectangle((x, y, x + 10, y + 20), fill="red")
            draw.rectangle((x + 11, y, x + 20, y + 20), fill="blue")
            frames.append(image)
        result = align_frames({"idle": frames}, 60)["idle"]
        self.assertEqual(result[0].tobytes(), result[1].tobytes())
        self.assertEqual(result[1].tobytes(), result[2].tobytes())
        box = result[0].getchannel("A").getbbox()
        self.assertEqual(result[0].getpixel((box[0], box[1]))[:3], (255, 0, 0))
        self.assertEqual(result[0].getpixel((box[2] - 1, box[1]))[:3], (0, 0, 255))

    def test_detached_effect_does_not_shift_body_anchor(self):
        from PIL import Image, ImageDraw
        image = Image.new("RGBA", (60, 40))
        ImageDraw.Draw(image).rectangle((20, 10, 40, 35), fill="brown")
        expected = character_anchor(image)
        image.putpixel((58, 1), (255, 255, 255, 255))
        self.assertEqual(character_anchor(image), expected)

    def test_animation_preserves_frame_order_without_moving_window(self):
        from .window import MascotWindow
        app = MascotWindow.__new__(MascotWindow)
        app.running = True
        app.behavior = Mock()
        app.behavior.locked = False
        app.behavior.current.return_value = ("walk", "")
        app.prefs = {"reduced_motion": False, "roaming": True}
        app.frames = {"idle": ["idle"], "walk": ["first", "second", "third"]}
        app.model = {"actions": {"walk": {"fps": 1}}}
        app.action, app.frame, app.frame_at = None, 0, 0
        app.x, app.y = 40, 80
        app.sprite, app.root, app.place = Mock(), Mock(), Mock()
        with patch("mascote_runtime.window.time.monotonic", side_effect=[1, 2, 3, 4]):
            for _ in range(4):
                app.animate()
        self.assertEqual([c.kwargs["image"] for c in app.sprite.configure.call_args_list], ["first", "second", "third", "first"])
        app.place.assert_not_called()
        self.assertEqual((app.x, app.y), (40, 80))


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)

    def test_disabled_default_and_corrupt_file(self):
        self.assertFalse(control.preferences(self.base)["enabled"])
        (self.base / "mascote_settings.json").write_text('{"enabled":"false", "size": -1, "theme": []}')
        self.assertEqual(control.preferences(self.base), control.DEFAULTS)
        (self.base / "mascote_settings.json").write_text("broken")
        self.assertFalse(control.preferences(self.base)["enabled"])

    def test_validation(self):
        for change in [{"enabled": "false"}, {"size": 0}, {"theme": "unknown"}, {"position": [1]}, {"bad": 1}, {"roaming": True}]:
            with self.assertRaises(ValueError):
                control.update_preferences(change, self.base)

    def test_concurrent_updates_preserve_unrelated_fields(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(control.update_preferences, {"theme": "natal"}, self.base)
            b = pool.submit(control.update_preferences, {"size": 128}, self.base)
            a.result()
            b.result()
        self.assertEqual(control.preferences(self.base)["theme"], "natal")
        self.assertEqual(control.preferences(self.base)["size"], 128)

    def test_start_once_and_disable_does_not_kill_any_pid(self):
        with patch.object(control.subprocess, "Popen") as spawn:
            control.configure({"enabled": True}, self.base)
            control.configure({"enabled": True}, self.base)
            self.assertEqual(spawn.call_count, 1)
            control.configure({"enabled": False}, self.base)
            self.assertFalse(control.preferences(self.base)["enabled"])
            self.assertEqual(spawn.call_count, 1)

    def test_expired_heartbeat_not_reported_running(self):
        control.atomic_json(self.base / "mascote_runtime.json", {"phase": "running", "heartbeat": time.time() - 30})
        self.assertFalse(control.status(self.base)["running"])

    def test_process_alive_is_not_enough_to_claim_visible(self):
        path = self.base / "mascote_runtime.json"
        control.atomic_json(path, {"phase": "running", "heartbeat": time.time(), "visible": False})
        self.assertFalse(control.status(self.base)["running"])
        control.atomic_json(path, {"phase": "running", "heartbeat": time.time(), "visible": True})
        self.assertTrue(control.status(self.base)["running"])
        control.atomic_json(path, {"phase": "error", "heartbeat": 0, "message": "Erro visual"})
        self.assertEqual(control.status(self.base)["phase"], "error")

    def test_events_bounded_and_only_when_enabled(self):
        control.publish_event("worklog_success", self.base)
        self.assertFalse((self.base / "mascote_events.json").exists())
        control.update_preferences({"enabled": True}, self.base)
        for _ in range(35):
            control.publish_event("worklog_start", self.base)
        events = control.read_json(self.base / "mascote_events.json", [])
        self.assertEqual(len(events), 32)
        self.assertEqual(len({e["id"] for e in events}), 32)

    def test_snapshot_only_current_day_and_minimal_keys(self):
        control.atomic_json(self.base / "state.json", {"date_str": "2020-01-01", "status": "RUNNING"})
        self.assertEqual(control.snapshot(self.base)["status"], "IDLE")
        control.atomic_json(self.base / "state.json", {"date_str": date.today().isoformat(), "status": "RUNNING", "target_issue": "TEST-1", "unrelated": "ignored"})
        self.assertEqual(set(control.snapshot(self.base)), {"date_str", "status", "target_issue"})
        control.service_heartbeat(False, self.base)
        self.assertEqual(control.snapshot(self.base)["status"], "IDLE")

    def test_disable_between_configure_and_launch_is_respected(self):
        control.update_preferences({"enabled": False}, self.base)
        with patch.object(control.subprocess, "Popen") as spawn:
            control.launch(self.base, activate=False)
        spawn.assert_not_called()


class IntegrationTests(unittest.TestCase):
    def test_native_mutex_between_processes(self):
        import subprocess
        import sys
        if sys.platform != "win32":
            self.skipTest("Mutex Win32")
        script = "from mascote_runtime.native import single_instance; import sys,time;\nwith single_instance('ProcessTest',sys.argv[1]) as owner:\n print(int(owner),flush=True)\n time.sleep(2 if owner else 0)"
        with tempfile.TemporaryDirectory() as temp:
            processes = [subprocess.Popen([sys.executable, "-c", script, temp], cwd=str(control.PROJECT), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=subprocess.CREATE_NO_WINDOW) for _ in range(2)]
            results = [p.communicate(timeout=8) for p in processes]
            self.assertEqual([p.returncode for p in processes], [0, 0], results)
            self.assertEqual(sorted(out.strip() for out, _err in results), ["0", "1"])

    def test_web_open_mini_is_idempotent_request(self):
        from web_panel import JiraBotWebHandler
        handler = JiraBotWebHandler.__new__(JiraBotWebHandler)
        handler.path = "/api/mini-widget/open"
        handler._read_json_body = lambda: {}
        handler._send_json = Mock()
        with patch("mini_window.launch_mini_window") as launch, patch("mini_window.toggle_mini_window") as toggle:
            handler.do_POST()
            handler.do_POST()
        self.assertEqual(launch.call_count, 2)
        toggle.assert_not_called()

    def test_native_mutex_excludes_second_owner(self):
        import sys
        if sys.platform != "win32":
            self.skipTest("Mutex Win32")
        from .native import single_instance
        with tempfile.TemporaryDirectory() as temp:
            with single_instance("Teste", temp) as first:
                self.assertTrue(first)
                with single_instance("Teste", temp) as second:
                    self.assertFalse(second)
            with single_instance("Teste", temp) as third:
                self.assertTrue(third)

    def test_mini_window_does_not_create_second_ui(self):
        from contextlib import contextmanager
        import mini_window
        order = []
        @contextmanager
        def occupied(*_args):
            order.append("mutex")
            yield False
        with patch("mascote_runtime.native.single_instance", occupied), patch.object(mini_window, "_attach_to_interactive_desktop", side_effect=lambda: order.append("desktop")), patch.object(mini_window, "_run_single_mini_window") as create, patch.object(mini_window, "bring_existing_mini_window_to_top") as focus:
            mini_window.run_mini_window()
        create.assert_not_called()
        focus.assert_called_once()
        self.assertEqual(order, ["desktop", "mutex"])

    def test_mini_desktop_attachment_preserves_64_bit_handles(self):
        import mini_window
        from ctypes import wintypes
        user = Mock()
        user.OpenWindowStationW.return_value = 0x100000001
        user.OpenDesktopW.return_value = 0x100000002
        with patch("ctypes.windll.user32", user):
            mini_window._attach_to_interactive_desktop()
        self.assertIs(user.OpenWindowStationW.restype, wintypes.HANDLE)
        self.assertIs(user.OpenDesktopW.restype, wintypes.HANDLE)
        user.SetProcessWindowStation.assert_called_once_with(0x100000001)
        user.SetThreadDesktop.assert_called_once_with(0x100000002)

    def test_hotkey_message_not_dispatched_twice(self):
        import tray
        import ctypes
        from ctypes import wintypes
        user = Mock()
        user.CreateWindowExW.return_value = 123
        user.RegisterClassW.return_value = 1
        def get_message(pointer, *_args):
            if not hasattr(get_message, "sent"):
                get_message.sent = True
                message = ctypes.cast(pointer, ctypes.POINTER(wintypes.MSG)).contents
                message.message = tray.WM_HOTKEY
                message.wParam = tray.HOTKEY_MINI_WINDOW_ID
                return 1
            return 0
        user.GetMessageW.side_effect = get_message
        icon = tray.SystemTrayIcon(engine=Mock())
        icon._running = True
        with patch.object(tray, "user32", user), patch("ctypes.windll.kernel32.GetModuleHandleW", return_value=1), patch("ctypes.windll.shell32.Shell_NotifyIconW", return_value=1), patch("mini_window._attach_to_interactive_desktop"), patch("mini_window.toggle_mini_window") as toggle, patch.object(tray, "get_icon_handle", return_value=1):
            icon._run_loop()
        toggle.assert_called_once()
        user.DispatchMessageW.assert_not_called()

    def test_web_routes_without_jira(self):
        from web_panel import JiraBotWebHandler
        handler = JiraBotWebHandler.__new__(JiraBotWebHandler)
        handler.path = "/api/mascot"
        handler._send_json = Mock()
        payload = {"preferences": {"enabled": False}, "phase": "stopped", "running": False}
        with patch("mascote_runtime.control.status", return_value=payload):
            handler.do_GET()
        handler._send_json.assert_called_with(payload)
        handler._read_json_body = lambda: {"enabled": False}
        with patch("mascote_runtime.control.configure", return_value=payload) as configure:
            handler.do_POST()
        configure.assert_called_once_with({"enabled": False})
        handler._read_json_body = lambda: {"enabled": "invalid"}
        with patch("mascote_runtime.control.configure", side_effect=ValueError("inválido")):
            handler.do_POST()
        self.assertEqual(handler._send_json.call_args.kwargs["status_code"], 400)

    def test_updater_allows_model_manifest_only_in_scoped_directory(self):
        from updater import is_allowed_app_file
        self.assertTrue(is_allowed_app_file(Path("mascote/modelos/modelo.json")))
        self.assertFalse(is_allowed_app_file(Path("other/settings.json")))
        self.assertFalse(is_allowed_app_file(Path("mascote/modelos/config.json")))

    def test_engine_events_follow_actual_result(self):
        from config import BotConfig
        from engine import BotEngine
        from storage import StateManager, TimeInterval
        with tempfile.TemporaryDirectory() as temp:
            manager = StateManager(base_dir=Path(temp))
            engine = BotEngine(config=BotConfig(), state_manager=manager)
            engine.state.intervals = [TimeInterval(start="2026-10-30T08:00:00", end="2026-10-30T09:00:00", issue_key="TEST-1")]
            engine.state.issue_comments = {"TEST-1": "Atividade fictícia de teste."}
            engine.on_worklog_trigger = lambda *_a: False
            with patch.object(engine, "_mascot_event") as event:
                engine._trigger_worklog_all_issues()
                self.assertEqual([c.args[0] for c in event.call_args_list], ["worklog_start", "worklog_error"])
            engine.on_worklog_trigger = lambda *_a: True
            with patch.object(engine, "_mascot_event") as event:
                engine._trigger_worklog_all_issues()
                self.assertEqual([c.args[0] for c in event.call_args_list], ["worklog_start", "worklog_success"])


if __name__ == "__main__":
    unittest.main()
