import discord
import random
from dataclasses import dataclass, field
from typing import Optional

MODE_TOURNAMENT = "tournament"
MODE_FRIENDLY   = "friendly"

DIRECTIONS = {
    "left":   "⬅️  LEFT",
    "centre": "⬆️  CENTRE",
    "right":  "➡️  RIGHT",
}

# Column indices for each direction in the 13-wide grid
_COL   = {"left": 1, "centre": 5, "right": 9}
_POST  = "🟫"
_BAR   = "🟨"
_INNER = "⬛"
_DIVID = "🔲"
_GRASS = "🟩"
_BALL  = "⚽"
_GLOVE = "🧤"


def build_grid(shot_dir: str, keeper_dir: str) -> str:
    """
    6-row × 13-col emoji grid:
      Row 0  = crossbar
      Rows 1-3 = net interior (keeper/ball placed in row 2)
      Rows 4-5 = grass
    """
    rows = []

    # Crossbar
    row0 = [_BAR] * 13
    for i in (0, 4, 8, 12):
        row0[i] = _POST if i in (0, 12) else _DIVID
    rows.append(row0)

    # Net interior
    for _ in range(3):
        row = [_INNER] * 13
        row[0] = _POST; row[4] = _DIVID; row[8] = _DIVID; row[12] = _POST
        rows.append(row)

    # Grass
    for _ in range(2):
        rows.append([_GRASS] * 13)

    # Place keeper (row 2)
    rows[2][_COL[keeper_dir]] = _GLOVE
    # Place ball (row 2) — overlaps keeper square if save
    rows[2][_COL[shot_dir]]   = _BALL

    return "```\n" + "\n".join("".join(r) for r in rows) + "\n```"


@dataclass
class Game:
    mode:        str
    host:        discord.Member
    player_a:    discord.Member   # shoots 1st half
    player_b:    discord.Member   # shoots 2nd half
    keeper_a:    discord.Member   # keeps while A shoots (= player_b)
    keeper_b:    discord.Member   # keeps while B shoots (= player_a)
    total_shots: int = 5

    score_a: int = 0   # goals by player_a
    score_b: int = 0   # goals by player_b
    round_num: int = 1

    voted: set = field(default_factory=set)
    _choice_shooter:    Optional[str] = field(default=None, repr=False)
    _choice_goalkeeper: Optional[str] = field(default=None, repr=False)

    # ── Factories ────────────────────────────────────────────────

    @classmethod
    def tournament(cls, host, player_a, player_b, total_shots=5):
        return cls(
            mode=MODE_TOURNAMENT, host=host,
            player_a=player_a, player_b=player_b,
            keeper_a=player_b, keeper_b=player_a,
            total_shots=total_shots,
        )

    @classmethod
    def friendly(cls, player_a, player_b, total_shots=5):
        if random.random() < 0.5:
            player_a, player_b = player_b, player_a
        return cls(
            mode=MODE_FRIENDLY, host=player_a,
            player_a=player_a, player_b=player_b,
            keeper_a=player_b, keeper_b=player_a,
            total_shots=total_shots,
        )

    # ── Properties ───────────────────────────────────────────────

    @property
    def half(self) -> int:
        return 1 if self.round_num <= self.total_shots else 2

    @property
    def shot_in_half(self) -> int:
        return self.round_num if self.round_num <= self.total_shots else self.round_num - self.total_shots

    @property
    def shooter(self) -> discord.Member:
        return self.player_a if self.round_num <= self.total_shots else self.player_b

    @property
    def goalkeeper(self) -> discord.Member:
        return self.keeper_a if self.round_num <= self.total_shots else self.keeper_b

    def total_rounds(self) -> int:
        return self.total_shots * 2

    def is_over(self) -> bool:
        return self.round_num > self.total_rounds()

    # ── Gameplay ─────────────────────────────────────────────────

    def record_choice(self, player: discord.Member, direction: str) -> bool:
        if player.id == self.shooter.id:
            self._choice_shooter = direction
        elif player.id == self.goalkeeper.id:
            self._choice_goalkeeper = direction
        self.voted.add(player.id)
        return self._choice_shooter is not None and self._choice_goalkeeper is not None

    def resolve_round(self) -> dict:
        shot_dir   = self._choice_shooter
        keeper_dir = self._choice_goalkeeper
        is_goal    = shot_dir != keeper_dir

        if is_goal:
            if self.round_num <= self.total_shots:
                self.score_a += 1
            else:
                self.score_b += 1

        grid = build_grid(shot_dir, keeper_dir)

        self._choice_shooter    = None
        self._choice_goalkeeper = None
        self.voted              = set()
        self.round_num         += 1

        return {
            "is_goal":    is_goal,
            "shot_dir":   shot_dir,
            "keeper_dir": keeper_dir,
            "grid":       grid,
        }

    def score_line(self) -> str:
        return (
            f"**{self.player_a.display_name}**  {self.score_a}  ⚽  —  ⚽  {self.score_b}  "
            f"**{self.player_b.display_name}**"
        )
