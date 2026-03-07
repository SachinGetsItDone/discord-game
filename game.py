"""
game.py  –  Game state for Penalty Shootout bot.

Two modes:
  TOURNAMENT  – host assigns shooter & goalkeeper, N shots, highest goals wins
  FRIENDLY    – 2 players, roles assigned RANDOMLY at match start, fixed all game

Scoring: only GOALS count. Saves score nothing.
All shots played out — winner = most goals. Draw possible.
"""

import random
import discord
from dataclasses import dataclass, field
from typing import Optional

DIRECTIONS = {
    "left":   "⬅️ LEFT",
    "centre": "⬆️ CENTRE",
    "right":  "➡️ RIGHT",
}

MODE_TOURNAMENT = "tournament"
MODE_FRIENDLY   = "friendly"


@dataclass
class Game:
    mode:        str
    host:        discord.Member
    shooter:     discord.Member   # fixed for entire match
    goalkeeper:  discord.Member   # fixed for entire match
    total_shots: int = 5

    score_shooter:    int = 0
    score_goalkeeper: int = 0
    round_num:        int = 1

    voted: set = field(default_factory=set)

    # internal per-round choices (set via record_choice)
    _choice_shooter:    Optional[str] = field(default=None, repr=False)
    _choice_goalkeeper: Optional[str] = field(default=None, repr=False)

    # ── Factories ────────────────────────────────────────────────────

    @classmethod
    def tournament(cls, host, shooter, goalkeeper, total_shots=5):
        return cls(
            mode=MODE_TOURNAMENT,
            host=host,
            shooter=shooter,
            goalkeeper=goalkeeper,
            total_shots=total_shots,
        )

    @classmethod
    def friendly(cls, player_a, player_b, total_shots=5):
        """Randomly assign shooter and goalkeeper."""
        if random.random() < 0.5:
            shooter, goalkeeper = player_a, player_b
        else:
            shooter, goalkeeper = player_b, player_a
        return cls(
            mode=MODE_FRIENDLY,
            host=player_a,
            shooter=shooter,
            goalkeeper=goalkeeper,
            total_shots=total_shots,
        )

    # ── State helpers ────────────────────────────────────────────────

    def is_over(self) -> bool:
        return self.round_num > self.total_shots

    def get_winner(self) -> Optional[discord.Member]:
        if not self.is_over():
            return None
        if self.score_shooter > self.score_goalkeeper:
            return self.shooter
        if self.score_goalkeeper > self.score_shooter:
            return self.goalkeeper
        return None  # draw

    def is_draw(self) -> bool:
        return self.is_over() and self.score_shooter == self.score_goalkeeper

    def shots_remaining(self) -> int:
        return max(0, self.total_shots - self.round_num + 1)

    # ── Choice recording ─────────────────────────────────────────────

    def record_choice(self, player: discord.Member, direction: str) -> bool:
        """Store direction for shooter or goalkeeper. Returns True when both done."""
        if player.id == self.shooter.id:
            self._choice_shooter = direction
        elif player.id == self.goalkeeper.id:
            self._choice_goalkeeper = direction
        self.voted.add(player.id)
        return self._choice_shooter is not None and self._choice_goalkeeper is not None

    def resolve_round(self) -> dict:
        s_dir = self._choice_shooter
        k_dir = self._choice_goalkeeper
        is_goal = s_dir != k_dir

        result = {
            "is_goal":     is_goal,
            "shooter_dir": DIRECTIONS[s_dir],
            "keeper_dir":  DIRECTIONS[k_dir],
            "shooter_raw": s_dir,
            "keeper_raw":  k_dir,
        }

        # Only goals score — saves give nothing
        if is_goal:
            self.score_shooter += 1

        self._choice_shooter    = None
        self._choice_goalkeeper = None
        self.voted    = set()
        self.round_num += 1
        return result

    def score_line(self) -> str:
        return (
            f"🎯  **{self.shooter.display_name}** (Shooter):    {self.score_shooter} ⚽\n"
            f"🧤  **{self.goalkeeper.display_name}** (Goalkeeper): {self.score_goalkeeper} ⚽"
        )
