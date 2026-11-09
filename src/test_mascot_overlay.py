from datetime import datetime, date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

from mascote_runtime.behavior import Behavior, effective_theme, easter_sunday, mascot_theme
from mascote_runtime.control import worklog_activity
from src.mascot_overlay import PetPhysics, DesktopPetWindow


class SeasonalTests(TestCase):
    def test_auto_follows_web_theme_while_explicit_choice_stays_fixed(self):
        for theme, expected in [("dark", "normal"), ("light", "normal"), ("natal", "natal"), ("pascoa", "pascoa")]:
            self.assertEqual(mascot_theme({"theme": "auto", "web_theme": theme}), expected)
            self.assertEqual(mascot_theme({"theme": "halloween", "web_theme": theme}), "halloween")

    def test_auto_uses_requested_calendar_including_easter_window(self):
        prefs = {"theme": "auto", "web_theme": "auto"}
        for when, expected in [("2026-10-01", "normal"), ("2026-10-20", "halloween"), ("2026-11-03", "normal"), ("2027-01-05", "ano_novo"), ("2027-01-06", "normal"), ("2026-03-29", "pascoa"), ("2026-04-07", "pascoa"), ("2026-04-08", "normal")]:
            self.assertEqual(mascot_theme(prefs, date.fromisoformat(when)), expected)

    def test_exact_season_boundaries(self):
        for when, expected in [("2026-10-19", "normal"), ("2026-10-20", "halloween"), ("2026-11-02", "halloween"), ("2026-11-03", "normal"), ("2026-11-30", "normal"), ("2026-12-01", "natal"), ("2026-12-26", "natal"), ("2026-12-27", "ano_novo"), ("2027-01-05", "ano_novo"), ("2027-01-06", "normal")]:
            self.assertEqual(effective_theme("auto", datetime.fromisoformat(when)), expected)

    def test_easter_algorithm_and_window(self):
        for year, month, day in [(2024, 3, 31), (2025, 4, 20), (2026, 4, 5), (2027, 3, 28)]:
            easter = easter_sunday(year)
            self.assertEqual(easter, date(year, month, day))
            for delta, expected in [(-8, "normal"), (-7, "pascoa"), (2, "pascoa"), (3, "normal")]:
                self.assertEqual(effective_theme("auto", easter + timedelta(days=delta)), expected)


class PhysicsTests(TestCase):
    AREA = (0, 0, 1000, 800)

    def test_top_snap_and_hanging(self):
        pet = PetPhysics()
        self.assertEqual(pet.drop(400, 12, 160, self.AREA, 0), (400, 0))
        self.assertEqual(pet.step(1, 400, 0, 160, self.AREA)[0], "swing")
        pet.drop(400, 500, 160, self.AREA, 0)
        self.assertFalse(pet.hanging)

    def test_top_threshold_is_twenty_pixels(self):
        pet = PetPhysics()
        self.assertEqual(pet.drop(400, 20, 160, self.AREA, 0), (400, 0))
        self.assertTrue(pet.hanging)
        pet.drop(400, 21, 160, self.AREA, 0)
        self.assertFalse(pet.hanging)

    def test_gravity_lands_without_overshooting_taskbar(self):
        pet = PetPhysics()
        x, y = pet.drop(400, 450, 160, self.AREA, 0)
        positions = []
        for index in range(80):
            _action, x, y, _flip = pet.step(index / 12, x, y, 160, self.AREA)
            positions.append(y)
        self.assertEqual(y, 640)
        self.assertEqual(positions, sorted(positions))
        self.assertFalse(pet.falling)

    def test_negative_monitor_top(self):
        pet = PetPhysics()
        self.assertEqual(pet.drop(-700, -1070, 160, (-1000, -1080, 0, 0), -1080), (-700, -1080))

    def test_walking_direction_and_flip_at_edges(self):
        rng = Mock()
        rng.choice.return_value, rng.uniform.return_value = "walk", 5
        pet = PetPhysics(rng)
        pet.step(0, 838, 640, 160, self.AREA)
        action, x, _y, flip = pet.step(.25, 838, 640, 160, self.AREA)
        self.assertEqual((action, x, flip), ("walk", 840, True))
        action, x, _y, flip = pet.step(.5, 0, 640, 160, self.AREA)
        self.assertEqual((x, flip), (0, False))

    def test_reduced_motion_and_override_do_not_walk(self):
        pet = PetPhysics()
        self.assertEqual(pet.step(1, 400, 640, 160, self.AREA, reduced=True), ("idle", 400, 640, False))
        self.assertEqual(pet.step(2, 400, 640, 160, self.AREA, override="backpack"), ("backpack", 400, 640, False))


class EventTests(TestCase):
    def test_new_sources_use_all_sixteen_real_frames_without_old_aliases(self):
        from mascote_runtime.catalog import load_catalog
        actions = load_catalog()["models"]["halloween"]["actions"]
        self.assertEqual(len(set(actions["idle"]["files"])), 16)
        self.assertEqual(Path(actions["idle"]["files"][0]).name, "frame_00.png")
        self.assertEqual(Path(actions["walk"]["files"][15]).name, "frame_15.png")

    def test_native_move_does_not_request_second_tk_layout(self):
        app = DesktopPetWindow.__new__(DesktopPetWindow)
        app._move_handle, app.root = 123, Mock()
        with patch("ctypes.windll.user32.SetWindowPos", return_value=True) as move:
            app.place(11, 22)
        move.assert_called_once_with(123, None, 11, 22, 0, 0, 0x0015)
        app.root.geometry.assert_not_called()
        app.root.update_idletasks.assert_not_called()
        self.assertEqual((app.x, app.y), (11, 22))

    def test_locked_session_pauses_rendering(self):
        app = DesktopPetWindow.__new__(DesktopPetWindow)
        app.running, app.behavior = True, Behavior()
        app.behavior.session_locked = True
        app.root, app.sprite = Mock(), Mock()
        app.animate()
        app.root.after.assert_not_called()
        self.assertTrue(app._animation_paused)
        app.sprite.configure.assert_not_called()

    def test_lock_cancels_timer_and_unlock_resumes_once(self):
        app = DesktopPetWindow.__new__(DesktopPetWindow)
        app.running, app.demo, app.base = True, False, Path("fake")
        app.behavior, app.physics, app.root = Behavior(), Mock(), Mock()
        app._animation_after, app._animation_paused = "render-timer", False
        app.animate = Mock()
        with patch("src.mascot_overlay.read_json", return_value={}), patch("mascote_runtime.window.MascotWindow.poll"), patch("src.mascot_overlay.time.monotonic", return_value=10):
            app.behavior.session_locked = True
            app.poll()
            app.root.after_cancel.assert_called_once_with("render-timer")
            app.animate.assert_not_called()
            app.behavior.session_locked = False
            app.poll()
            app.poll()
        app.animate.assert_called_once()
        self.assertEqual(app.frame_at, 10)
        self.assertIsNone(app.physics.last_tick)

    def test_renderer_slows_to_eight_fps_without_dropping_frames(self):
        app = DesktopPetWindow.__new__(DesktopPetWindow)
        app.running, app.demo, app.behavior = True, False, Behavior()
        app.behavior.status = "RUNNING"
        app.prefs = {"reduced_motion": False}
        app.x, app.y, app.size = 20, 640, 160
        app.physics = Mock()
        app.physics.step.return_value = ("walk", 20, 640, True)
        app.action, app.frame, app.frame_at = "walk", 0, 0
        app.frames = {"idle": ["idle"], "walk": list(range(16))}
        app.mirrored_walk = [f"left-{i}" for i in range(16)]
        app.model = {"actions": {"walk": {"fps": 12}}}
        app.root, app.sprite = Mock(), Mock()
        with patch("src.mascot_overlay.work_area", return_value=(0, 0, 1000, 800)), patch("src.mascot_overlay.time.monotonic", return_value=.25):
            app.animate()
        app.sprite.configure.assert_called_once_with(image="left-2")
        self.assertEqual(app.root.after.call_args.args[0], 125)
        app.sprite.configure.reset_mock()
        with patch("src.mascot_overlay.work_area", return_value=(0, 0, 1000, 800)), patch("src.mascot_overlay.time.monotonic", return_value=.30):
            app.animate()
        app.sprite.configure.assert_not_called()

        with patch("src.mascot_overlay.work_area", return_value=(0,0,1000,800)), patch("src.mascot_overlay.time.monotonic", return_value=1.875):
            app.animate()
        self.assertEqual(app.frame, 15)
        with patch("src.mascot_overlay.work_area", return_value=(0,0,1000,800)), patch("src.mascot_overlay.time.monotonic", return_value=2 + 1e-9):
            app.animate()
        self.assertEqual(app.frame, 0)

    def test_daemon_publishes_session_events(self):
        from daemon import JiraBotService
        service = JiraBotService.__new__(JiraBotService)
        service.state_manager, service.engine = Mock(), Mock()
        with patch("mascote_runtime.control.publish_event") as publish:
            service._on_session_lock()
            service._on_session_unlock()
        self.assertEqual([c.args[0] for c in publish.call_args_list], ["Windows_Lock", "Windows_Unlock"])
        service.engine.handle_lock.assert_called_once()
        service.engine.handle_unlock.assert_called_once()

    def test_overlay_closes_with_daemon_without_disabling_preference(self):
        from mascote_runtime.control import atomic_json, preferences, update_preferences
        with TemporaryDirectory() as temp:
            base = Path(temp)
            update_preferences({"enabled": True}, base)
            atomic_json(base / "mascote_service.json", {"running": False})
            app = DesktopPetWindow.__new__(DesktopPetWindow)
            app.base, app.demo, app.close = base, False, Mock()
            app.poll()
            app.close.assert_called_once()
            self.assertTrue(preferences(base)["enabled"])

    def test_session_events_and_concurrent_requests(self):
        state = Behavior()
        state.trigger("jira_request_start", 1, activity_id="first")
        state.trigger("jira_request_start", 1, activity_id="second")
        self.assertEqual(state.current(2)[0], "backpack")
        state.trigger("jira_request_end", 3, activity_id="first")
        self.assertEqual(state.current(3)[0], "backpack")
        state.trigger("Windows_Lock", 3)
        self.assertEqual(state.current(4)[0], "sit")
        state.trigger("Windows_Unlock", 4)
        state.trigger("jira_request_end", 4, activity_id="second")
        self.assertEqual(state.current(5)[0], "idle")
        state.trigger("exit_warning", 5)
        self.assertEqual(state.current(6)[0], "drink")

    def test_short_request_still_displays_backpack(self):
        state = Behavior()
        state.trigger("jira_request_start", 1, activity_id="fast")
        state.trigger("jira_request_end", 1.05, activity_id="fast")
        self.assertEqual(state.current(1.1)[0], "backpack")
        self.assertEqual(state.current(6)[0], "idle")

    def test_click_leaves_current_action_unchanged(self):
        state = Behavior()
        state.trigger("exit_warning", 1)
        self.assertFalse(state.trigger("click", 2))
        self.assertEqual(state.current(2)[0], "drink")

    def test_click_release_does_not_reset_physics_or_snap(self):
        app = DesktopPetWindow.__new__(DesktopPetWindow)
        app.behavior = Behavior()
        app.physics, app.place = Mock(), Mock()
        app.x, app.y, app.drag = 40, 60, None
        event = Mock(x_root=10, y_root=20)
        app.press(event)
        self.assertFalse(app.behavior.dragging)
        app.release(event)
        app.physics.drop.assert_not_called()
        app.place.assert_not_called()

    def test_drag_uses_walk_and_mouse_direction(self):
        app = DesktopPetWindow.__new__(DesktopPetWindow)
        app.behavior = Behavior()
        app.size = 160
        app.x, app.y, app.drag = 40, 60, None
        app.place = Mock()
        app.press(Mock(x_root=100, y_root=100))
        with patch("src.mascot_overlay.work_area", return_value=(0,0,1000,800)):
            app.move(Mock(x_root=110,y_root=100))
            self.assertEqual(app.behavior.current(1)[0], "walk")
            self.assertFalse(app._drag_flip)
            app.move(Mock(x_root=105,y_root=100))
            self.assertTrue(app._drag_flip)

    def test_ground_cycle_covers_idle_walk_sit(self):
        rng = Mock()
        rng.choice.side_effect = lambda choices: choices[0]
        rng.uniform.side_effect = lambda low, high: low
        pet = PetPhysics(rng)
        seen = []
        now = 0
        for _ in range(3):
            action, x, y, _flip = pet.step(now, 300, 640, 160, (0,0,1000,800))
            seen.append(action)
            self.assertEqual(y,640)
            self.assertGreaterEqual(pet.until-now,4)
            now = pet.until + .01
        self.assertEqual(set(seen), {"idle","walk","sit"})

    def test_visible_sprite_does_not_rebuild_frame_each_poll(self):
        import ctypes
        from ctypes import wintypes
        from mascote_runtime.native import show_sprite
        root, user = Mock(), Mock()
        root.winfo_viewable.return_value = True
        root.winfo_id.return_value = 100
        user.GetParent.return_value = 200
        user.GetWindowLongPtrW.side_effect = lambda _hwnd, index: 0x80000000 if index == -16 else 0x80
        user.IsWindowVisible.return_value = True
        def rectangle(_hwnd,pointer):
            rect = ctypes.cast(pointer,ctypes.POINTER(wintypes.RECT)).contents
            rect.left,rect.top,rect.right,rect.bottom = 10,20,170,180
            return True
        user.GetWindowRect.side_effect = rectangle
        with patch("ctypes.windll.user32", user):
            self.assertTrue(show_sprite(root,10,20,160,160))
        user.SetWindowLongPtrW.assert_not_called()
        user.ShowWindow.assert_not_called()
        user.SetWindowPos.assert_not_called()

    def test_activity_end_is_emitted_on_failure_without_payload(self):
        client = Mock()
        client.state_manager.base_dir = Path("fake")
        @worklog_activity
        def failing(self, **_kwargs):
            raise ValueError("failure")
        with patch("mascote_runtime.control.publish_event") as publish:
            with self.assertRaises(ValueError):
                failing(client, issue_key="TEST-1", comment="private")
        calls = publish.call_args_list
        self.assertEqual([c.args[0] for c in calls], ["jira_request_start", "jira_request_end"])
        self.assertEqual(calls[0].kwargs["activity_id"], calls[1].kwargs["activity_id"])
        self.assertNotIn("private", str(calls))

    def test_failed_visual_event_does_not_change_operation_result(self):
        @worklog_activity
        def operation(self):
            return "ok"
        with patch("mascote_runtime.control.publish_event", side_effect=OSError):
            self.assertEqual(operation(Mock()), "ok")
