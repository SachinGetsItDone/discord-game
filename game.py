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

_POST  = "🟫"
_BAR   = "🟨"
_INNER = "⬛"
_GRASS = "🟩"
_BALL  = "⚽"
_GLOVE = "🧤"
_SPOT  = "🔵"
_SCORE = "🟥"   # goal highlight
_BLOCK = "🟦"   # save highlight

W    = 9
_COL = {"left": 1, "centre": 4, "right": 7}


def _base():
    return [
        [_POST] + [_BAR]   * 7 + [_POST],
        [_POST] + [_INNER] * 7 + [_POST],
        [_POST] + [_INNER] * 7 + [_POST],
        [_POST] + [_INNER] * 7 + [_POST],
        [_GRASS] * W,
        [_GRASS] * W,
    ]


def _render(rows) -> str:
    return "```\n" + "".join("".join(r) + "\n" for r in rows) + "```"


def grid_idle() -> str:
    """Ball on the spot, keeper centred — pre-kick."""
    r = _base()
    r[1][_COL["centre"]] = _GLOVE
    r[5][_COL["centre"]] = _BALL
    return _render(r)


def grid_runup(keeper_dir: str) -> str:
    """Keeper has committed, ball still on spot."""
    r = _base()
    r[1][_COL[keeper_dir]] = _GLOVE
    r[5][_COL["centre"]]   = _BALL
    return _render(r)


def grid_flying(shot_dir: str, keeper_dir: str) -> str:
    """Ball entering the net area."""
    r = _base()
    r[1][_COL[keeper_dir]]  = _GLOVE
    r[3][_COL[shot_dir]]    = _BALL
    return _render(r)


def grid_result(shot_dir: str, keeper_dir: str, is_goal: bool) -> str:
    """Final frame — ball settled, column highlighted."""
    r = _base()
    kc = _COL[keeper_dir]
    bc = _COL[shot_dir]
    r[1][kc] = _GLOVE
    r[2][bc] = _BALL
    highlight = _SCORE if is_goal else _BLOCK
    for ri in (1, 3):
        if r[ri][bc] == _INNER:
            r[ri][bc] = highlight
    return _render(r)


@dataclass
class Game:
    mode:        str
    host:        discord.Member
    player_a:    discord.Member
    player_b:    discord.Member
    keeper_a:    discord.Member
    keeper_b:    discord.Member
    total_shots: int = 5

    score_a:   int = 0
    score_b:   int = 0
    round_num: int = 1

    voted: set = field(default_factory=set)
    _choice_shooter:    Optional[str] = field(default=None, repr=False)
    _choice_goalkeeper: Optional[str] = field(default=None, repr=False)

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

        self._choice_shooter    = None
        self._choice_goalkeeper = None
        self.voted              = set()
        self.round_num         += 1

        return {
            "is_goal":    is_goal,
            "shot_dir":   shot_dir,
            "keeper_dir": keeper_dir,
        }

    def score_line(self) -> str:
        return (
            f"**{self.player_a.display_name}**  {self.score_a}  —  {self.score_b}  "
            f"**{self.player_b.display_name}**"
        )
