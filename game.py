"""
game.py  –  Game state for Penalty Shootout bot.

Two modes:
  TOURNAMENT  – host assigns shooter & goalkeeper, N shots each, highest score wins
  FRIENDLY    – 2 players, roles swap every round, N shots each, highest score wins

Scoring: all shots are played out. Winner = most goals. Draw is possible.
"""

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
    mode:        str             # MODE_TOURNAMENT or MODE_FRIENDLY
    host:        discord.Member  # who ran the command (may be a player in friendly)
    player_a:    discord.Member  # shooter in tournament | challenger in friendly
    player_b:    discord.Member  # goalkeeper in tournament | accepter in friendly
    total_shots: int = 5         # shots per player (tournament) / rounds (friendly)

    score_a: int = 0
    score_b: int = 0
    round_num: int = 1           # 1-indexed, goes up to total_shots

    choice_a: Optional[str] = None
    choice_b: Optional[str] = None
    voted: set = field(default_factory=set)

    # ── Role helpers ────────────────────────────────────────────────

    @property
    def shooter(self) -> discord.Member:
        """Current shooter this round."""
        if self.mode == MODE_TOURNAMENT:
            return self.player_a
        # Friendly: A shoots odd rounds, B shoots even rounds
        return self.player_a if self.round_num % 2 == 1 else self.player_b

    @property
    def goalkeeper(self) -> discord.Member:
        """Current goalkeeper this round."""
        if self.mode == MODE_TOURNAMENT:
            return self.player_b
        return self.player_b if self.round_num % 2 == 1 else self.player_a

    def is_over(self) -> bool:
        return self.round_num > self.total_shots

    def get_winner(self) -> Optional[discord.Member]:
        """Returns winner only after all shots played. None = still playing or draw."""
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
        """Record a direction choice. Returns True when both have chosen."""
        if player.id == self.shooter.id:
            self.choice_a = direction if self.mode == MODE_TOURNAMENT else (
                direction if player.id == self.player_a.id else self.choice_a
            )
            # Simpler: store by shooter/keeper slot
            self._choice_shooter = direction
        elif player.id == self.goalkeeper.id:
            self._choice_goalkeeper = direction
        self.voted.add(player.id)
        return (
            hasattr(self, "_choice_shooter") and self._choice_shooter is not None and
            hasattr(self, "_choice_goalkeeper") and self._choice_goalkeeper is not None
        )

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

        # Score goes to the shooter's player
        if is_goal:
            if self.shooter.id == self.player_a.id:
                self.score_a += 1
            else:
                self.score_b += 1
        else:
            # Save: point to the goalkeeper's player
            if self.goalkeeper.id == self.player_a.id:
                self.score_a += 1
            else:
                self.score_b += 1

        self._choice_shooter   = None
        self._choice_goalkeeper = None
        self.voted    = set()
        self.round_num += 1
        return result

    def score_line(self) -> str:
        return (
            f"**{self.player_a.display_name}:** {self.score_a} ⚽\n"
            f"**{self.player_b.display_name}:** {self.score_b} ⚽"
        )

    def shots_remaining(self) -> int:
        return max(0, self.total_shots - self.round_num + 1)
