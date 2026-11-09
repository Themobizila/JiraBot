import unittest
from .catalog import load_catalog, load_frames
from .playback import AnimationPlayer


class HDPlaybackTests(unittest.TestCase):
    def setUp(self):
        self.model = load_catalog()["models"]["normal"]
        self.player = AnimationPlayer(self.model["actions"])

    def test_approved_catalog_and_seasonal_fallback(self):
        self.assertTrue(self.model["walk_faces_left"])
        self.assertEqual(sum(self.model["actions"]["swing"]["duration_ms"]),3200)
        self.assertEqual(len(self.model["actions"]["backpack"]["files"]),23)
        self.assertNotIn("duration_ms",load_catalog()["models"]["natal"]["actions"]["idle"])

    def test_variable_durations_and_complete_cycle(self):
        self.player.seated=True
        self.player.sample("backpack",0)
        self.assertEqual(self.player.sample("backpack",.64)[1],0)
        self.assertEqual(self.player.sample("backpack",.66)[1],1)
        self.assertEqual(self.player.sample("backpack",4.66)[1],0)

    def test_short_api_request_finishes_backpack(self):
        self.player.seated=True
        self.player.sample("backpack",0)
        self.assertEqual(self.player.sample("idle",1)[0],"backpack")
        self.assertEqual(self.player.sample("idle",4.66)[0],"stand_up")

    def test_sit_and_stand_are_independent_one_shots(self):
        self.assertEqual(self.player.sample("sit",0)[0],"sit_down")
        self.assertEqual(self.player.sample("sit",2.01)[0],"sit")
        self.assertEqual(self.player.sample("walk",3)[0],"stand_up")
        self.assertEqual(self.player.sample("walk",5.01)[0],"walk")

    def test_drag_interrupts_transition(self):
        self.player.sample("sit",0)
        self.assertEqual(self.player.sample("walk",.1,immediate=True)[0],"walk")
        self.assertFalse(self.player.seated)

    def test_short_reaction_during_transition_is_not_lost(self):
        self.player.sample("sit",0)
        self.player.sample("backpack",1)
        self.assertEqual(self.player.sample("idle",2.01)[0],"backpack")
        self.assertEqual(self.player.sample("idle",4.02)[0],"backpack")
        self.assertEqual(self.player.sample("idle",5)[0],"backpack")

    def test_backpack_stays_seated_and_coffee_stands_up(self):
        self.assertEqual(self.player.sample("backpack",0)[0],"sit_down")
        self.assertEqual(self.player.sample("backpack",2.01)[0],"backpack")
        self.assertEqual(self.player.sample("sit",6.67)[0],"sit")
        self.assertEqual(self.player.sample("drink",7)[0],"stand_up")
        self.assertEqual(self.player.sample("drink",9.01)[0],"drink")

    def test_ground_rotation_includes_all_five_actions(self):
        import random
        from src.mascot_overlay import PetPhysics
        pet=PetPhysics(random.Random(7));now=0;seen=set()
        for _ in range(5):
            action,*_=pet.step(now,100,640,160,(0,0,1000,800))
            seen.add(action);now=pet.until+.01
        self.assertEqual(seen,{"idle","walk","sit","drink","backpack"})

    def test_window_does_not_walk_while_backpack_finishes(self):
        from unittest.mock import Mock,patch
        from src.mascot_overlay import DesktopPetWindow
        from .behavior import Behavior
        app=DesktopPetWindow.__new__(DesktopPetWindow)
        app.running,app.demo,app.behavior=True,False,Behavior()
        app.prefs={"reduced_motion":False};app.x,app.y,app.size=20,640,160
        app.physics=Mock(hanging=False,falling=False)
        app.physics.step.return_value=("walk",22,640,False)
        app.model=self.model;app.player=AnimationPlayer(self.model["actions"])
        app.player.seated=True;app.player.sample("backpack",0)
        app.frames={"backpack":["bag"]*23}
        app.root,app.sprite,app.place=Mock(),Mock(),Mock()
        with patch("src.mascot_overlay.work_area",return_value=(0,0,1000,800)),patch("src.mascot_overlay.time.monotonic",return_value=1):
            app.animate()
        app.place.assert_not_called()
        self.assertEqual(app.action,"backpack")

    def test_ground_alignment_and_transparent_top_anchors(self):
        frames=load_frames(self.model,256)
        for action,group in frames.items():
            if action!="swing":
                self.assertEqual(max(f.getchannel("A").getbbox()[3] for f in group),256)
            else:
                self.assertTrue(all(f.getchannel("A").getbbox()[1]==0 for f in group))
        self.assertEqual(len(frames["walk"]),12)

    def test_walk_stop_uses_the_exact_walk_and_recovery_endpoints(self):
        frames = load_frames(self.model, 256, actions=("walk", "walk_stop", "idle_quad", "recover"))
        self.assertEqual(frames["walk"][-1].tobytes(), frames["walk_stop"][0].tobytes())
        self.assertEqual(frames["walk_stop"][-1].tobytes(), frames["idle_quad"][0].tobytes())
        self.assertEqual(frames["recover"][-1].tobytes(), frames["idle_quad"][0].tobytes())

    def test_autonomous_walk_finishes_stride_and_holds_quad_pose_in_both_directions(self):
        from unittest.mock import Mock, patch
        from src.mascot_overlay import DesktopPetWindow, PetPhysics
        from .behavior import Behavior

        area = (0, 0, 1000, 800)
        for direction in (-1, 1):
            with self.subTest(direction=direction):
                rng = Mock()
                rng.choice.side_effect = lambda candidates: "idle" if "idle" in candidates else candidates[0]
                rng.uniform.return_value = 6
                app = DesktopPetWindow.__new__(DesktopPetWindow)
                app.running, app.demo, app.behavior = True, False, Behavior()
                app.prefs = {"reduced_motion": False}
                app.x, app.y, app.size = 200, 544, 256
                app.physics = PetPhysics(rng)
                app.physics.mode, app.physics.until, app.physics.direction = "walk", .5, direction
                app.model = self.model
                app.player = AnimationPlayer(self.model["actions"])
                app.frames = {name: [f"left-{name}-{i}" for i in range(len(spec["files"]))]
                              for name, spec in self.model["actions"].items()}
                app.mirrored_walk = [f"right-walk-{i}" for i in range(12)]
                app.mirrored_ground = {"walk_stop": [f"right-walk_stop-{i}" for i in range(5)],
                                       "idle_quad": ["right-idle_quad-0"]}
                app.root, app.sprite = Mock(), Mock()

                def place(x, y):
                    app.x, app.y = x, y

                app.place = place
                trace = []
                with patch("src.mascot_overlay.work_area", return_value=area), patch("src.mascot_overlay.time.monotonic") as clock:
                    for tick in range(42):
                        clock.return_value = tick / 10
                        app.animate()
                        trace.append((app.action, app.frame, app.x, app._displayed_photo))
                self.assertEqual(trace[21][0], "walk")
                self.assertGreater((trace[21][2] - trace[5][2]) * direction, 0)
                stop = [entry for entry in trace if entry[0] == "walk_stop"]
                self.assertEqual(sorted({entry[1] for entry in stop}), list(range(5)))
                self.assertEqual(len({entry[2] for entry in stop}), 1)
                side = "left" if direction < 0 else "right"
                self.assertEqual(stop[0][3], f"{side}-walk_stop-0")
                self.assertEqual(trace[-1][3], f"{side}-idle_quad-0")

    def test_high_drop_renders_airborne_poses_then_one_ground_recovery(self):
        from unittest.mock import Mock, patch
        from src.mascot_overlay import DesktopPetWindow, PetPhysics
        from .behavior import Behavior

        area = (0, 0, 1000, 800)
        app = DesktopPetWindow.__new__(DesktopPetWindow)
        app.running, app.demo = True, True
        app.behavior = Behavior()
        app.prefs = {"reduced_motion": False}
        app.size = 256
        app.physics = PetPhysics()
        app.physics.recovery_seconds = sum(self.model["actions"]["recover"]["duration_ms"]) / 1000
        app.x, app.y = 100, 240
        app.drag = (100, 240, 100, 240)
        app.behavior.dragging = True
        app.model, app.player = self.model, self.player
        app.frames = {name: list(range(len(action["files"]))) for name, action in self.model["actions"].items()}
        app.mirrored_walk = app.frames["walk"]
        app.root, app.sprite = Mock(), Mock()

        def place(x, y):
            app.x, app.y = x, y

        app.place = place
        trace = []
        with patch("src.mascot_overlay.work_area", return_value=area), patch("src.mascot_overlay.time.monotonic") as clock:
            app.release(Mock(x_root=100, y_root=240))
            for tick in range(180):
                clock.return_value = tick * .04
                app.animate()
                trace.append((app.action, app.frame, app.y))
        fall = [(index, y) for action, index, y in trace if action == "fall"]
        recover = [(index, y) for action, index, y in trace if action == "recover"]
        self.assertEqual(sorted({index for index, _ in fall}), list(range(5)))
        self.assertTrue(all(y < 544 for _, y in fall))
        self.assertEqual(sorted({index for index, _ in recover}), list(range(21)))
        self.assertTrue(all(y == 544 for _, y in recover))
        self.assertEqual([index for index, _ in recover], sorted(index for index, _ in recover))
        self.assertNotIn(trace[-1][0], {"fall", "recover"})

    def test_short_drops_and_models_without_recovery_use_ordinary_gravity(self):
        from src.mascot_overlay import PetPhysics

        area = (0, 0, 1000, 800)
        for height, recovery_seconds in ((255, 4.4), (300, 0)):
            pet = PetPhysics()
            pet.recovery_seconds = recovery_seconds
            x, y = pet.drop(100, 544 - height, 256, area, 0, animate_fall=True)
            seen = set()
            for tick in range(60):
                action, x, y, _ = pet.step(tick * .04, x, y, 256, area)
                seen.add(action)
            self.assertEqual(y, 544)
            self.assertTrue(seen.isdisjoint({"fall", "recover"}))

    def test_recovery_pauses_on_lock_and_can_be_interrupted_by_drag(self):
        from src.mascot_overlay import PetPhysics

        area = (0, 0, 1000, 800)
        pet = PetPhysics()
        pet.recovery_seconds = 4.4
        pet.recovery_elapsed = 1.0
        # O desbloqueio do overlay descarta o intervalo desde o último tick.
        pet.last_tick = None
        action, *_ = pet.step(100, 100, 544, 256, area)
        self.assertEqual(action, "recover")
        self.assertEqual(pet.recovery_elapsed, 1.0)
        action, *_ = pet.step(100.04, 100, 544, 256, area, active=False, override="walk")
        self.assertEqual(action, "walk")
        self.assertIsNone(pet.recovery_elapsed)

    def test_overlay_selects_correct_direction_for_left_facing_art(self):
        from unittest.mock import Mock, patch
        from src.mascot_overlay import DesktopPetWindow
        from .behavior import Behavior
        for moving_left, expected in [(True,"original"),(False,"mirrored")]:
            app=DesktopPetWindow.__new__(DesktopPetWindow)
            app.running,app.demo,app.behavior=True,False,Behavior()
            app.prefs={"reduced_motion":False}
            app.x,app.y,app.size=20,640,160
            app.physics=Mock(hanging=False,falling=False)
            app.physics.step.return_value=("walk",20,640,moving_left)
            app.model=self.model
            app.player=AnimationPlayer(self.model["actions"])
            app.frames={"walk":["original"]*12}
            app.mirrored_walk=["mirrored"]*12
            app.root,app.sprite=Mock(),Mock()
            with patch("src.mascot_overlay.work_area",return_value=(0,0,1000,800)):
                app.animate()
            app.sprite.configure.assert_called_once_with(image=expected)


if __name__=="__main__":
    unittest.main()
