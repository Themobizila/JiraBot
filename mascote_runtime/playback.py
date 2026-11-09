"""Playback por duração real e transições de postura, sem dependência gráfica."""
from bisect import bisect_right
from itertools import accumulate


class AnimationPlayer:
    SEATED_ACTIONS = {"sit", "backpack"}
    TRANSITIONS = {"sit_down", "stand_up", "walk_stop"}
    def __init__(self, actions):
        self.actions = actions
        self.action = None
        self.started = 0
        self.seated = False
        self.pending = None

    def at_last_walk_frame(self, now):
        if self.action != "walk" or "walk_stop" not in self.actions:
            return False
        durations = self.actions["walk"]["duration_ms"]
        total = sum(durations)
        elapsed = max(0, (now - self.started) * 1000) % total
        return elapsed >= total - durations[-1]

    def sample(self, target, now, immediate=False, progress=None):
        previous = self.action
        if immediate:
            self.seated = False
            self.pending = None
        elif self.action in self.TRANSITIONS and target in {"drink", "backpack"}:
            self.pending = target
        if self.action in {"drink", "backpack"} and target != self.action and not immediate:
            if (now-self.started)*1000 < sum(self.actions[self.action]["duration_ms"]):
                target = self.action
        if self.action in self.TRANSITIONS:
            length = sum(self.actions[self.action]["duration_ms"]) / 1000
            if immediate:
                self.action = None
                self.seated = False
            elif now - self.started >= length:
                self.seated = self.action == "sit_down"
                self.action = None
                if self.pending:
                    target, self.pending = self.pending, None
        if self.action not in self.TRANSITIONS:
            desired = target
            if not immediate:
                if target != "walk" and self.at_last_walk_frame(now):
                    desired = "walk_stop"
                elif target in self.SEATED_ACTIONS and not self.seated and "sit_down" in self.actions:
                    desired = "sit_down"
                elif target not in self.SEATED_ACTIONS and self.seated and "stand_up" in self.actions:
                    desired = "stand_up"
                elif target == "idle" and previous in {"walk_stop", "idle_quad", "recover"} and "idle_quad" in self.actions:
                    desired = "idle_quad"
                if desired in self.TRANSITIONS and target in {"drink", "backpack"}:
                    self.pending = target
            if desired != self.action:
                self.action, self.started = desired, now
        durations = self.actions[self.action]["duration_ms"]
        total = sum(durations)
        elapsed = max(0, (now - self.started) * 1000)
        if progress is not None:
            elapsed = total * max(0, min(1, progress))
        elif self.action not in self.TRANSITIONS:
            elapsed %= total
        index = min(len(durations) - 1, bisect_right(list(accumulate(durations)), elapsed))
        remaining = sum(durations[:index+1]) - elapsed
        return self.action, index, max(1, remaining)
