"""
game.py  –  Game state for Penalty Shootout bot.

Real penalty shootout format:
  - Player A shoots all their shots first (rounds 1 to total_shots)
  - Then Player B shoots all their shots (rounds total_shots+1 to total_shots*2)
  - Most goals wins. Draw possible.

Both modes (tournament & friendly) use this same format.
In friendly, shooter/goalkeeper are assigned randomly.
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
    mode:       str
    host:       discord.Member
    player_a:   discord.Member  # shoots first half
    player_b:   discord.Member  # shoots second half
    keeper_a:   discord.Member  # keeps goal while B shoots (= player_b)
    keeper_b:   discord.Member  # keeps goal while A shoots (= player_a)
    total_shots: int = 5        # shots per player

    score_a:  int = 0  # goals scored by player_a
    score_b:  int = 0  # goals scored by player_b
    round_num: int = 1  # 1-indexed, goes up to total_shots * 2

    voted: set = field(default_factory=set)
    _choice_shooter:    Optional[str] = field(default=None, repr=False)
    _choice_goalkeeper: Optional[str] = field(default=None, repr=False)

    # ── Factories ────────────────────────────────────────────────────

    @classmethod
    def tournament(cls, host, player_a, player_b, total_shots=5):
        """player_a shoots first, player_b shoots second."""
        return cls(
            mode=MODE_TOURNAMENT,
            host=host,
            player_a=player_a,
            player_b=player_b,
            keeper_a=player_b,  # player_b keeps while A shoots
            keeper_b=player_a,  # player_a keeps while B shoots
            total_shots=total_shots,
        )

    @classmethod
    def friendly(cls, challenger, accepter, total_shots=5):
        """Randomly decide who shoots first."""
        if random.random() < 0.5:
            first, second = challenger, accepter
        else:
            first, second = accepter, challenger
        return cls(
            mode=MODE_FRIENDLY,
            host=challenger,
            player_a=first,
            player_b=second,
            keeper_a=second,
            keeper_b=first,
            total_shots=total_shots,
        )

    # ── Role helpers (who is shooting/keeping THIS round) ───────────

    @property
    def shooter(self) -> discord.Member:
        """Player A shoots rounds 1..total_shots, B shoots the rest."""
        return self.player_a if self.round_num <= self.total_shots else self.player_b

    @property
    def goalkeeper(self) -> discord.Member:
        return self.keeper_a if self.round_num <= self.total_shots else self.keeper_b

    @property
    def half(self) -> int:
        """1 = first half (A shooting), 2 = second half (B shooting)."""
        return 1 if self.round_num <= self.total_shots else 2

    @property
    def shot_in_half(self) -> int:
        """Shot number within current half (1-indexed)."""
        if self.half == 1:
            return self.round_num
        return self.round_num - self.total_shots

    # ── State helpers ────────────────────────────────────────────────

    def total_rounds(self) -> int:
        return self.total_shots * 2

    def is_over(self) -> bool:
        return self.round_num > self.total_rounds()

    def shots_remaining(self) -> int:
        return max(0, self.total_rounds() - self.round_num + 1)

    def get_winner(self) -> Optional[discord.Member]:
        if not self.is_over():
            return None
        if self.score_a > self.score_b:
            return self.player_a
        if self.score_b > self.score_a:
            return self.player_b
        return None  # draw

    def is_draw(self) -> bool:
        return self.is_over() and self.score_a == self.score_b

    # ── Choice recording ─────────────────────────────────────────────

    def record_choice(self, player: discord.Member, direction: str) -> bool:
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

        if is_goal:
            if self.shooter.id == self.player_a.id:
                self.score_a += 1
            else:
                self.score_b += 1

        self._choice_shooter    = None
        self._choice_goalkeeper = None
        self.voted    = set()
        self.round_num += 1
        return result

    def score_line(self) -> str:
        return (
            f"🎯  **{self.player_a.display_name}:** {self.score_a} ⚽\n"
            f"🎯  **{self.player_b.display_name}:** {self.score_b} ⚽"
        )
