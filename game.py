import discord
from dataclasses import dataclass, field
from typing import Optional

DIRECTIONS = {
    "left":   "⬅️ LEFT",
    "centre": "⬆️ CENTRE",
    "right":  "➡️ RIGHT",
}

GOAL_FRAME = (
    "```\n"
    "  ┌──────────────────────┐\n"
    "  │  🥅   G O A L   🥅  │\n"
    "  └──────────────────────┘\n"
    "```"
)


@dataclass
class Game:
    host:        discord.Member
    shooter:     discord.Member
    goalkeeper:  discord.Member
    goal_target: int = 5

    score_shooter:    int = 0
    score_goalkeeper: int = 0
    round_num:        int = 1

    choice_shooter:    Optional[str] = None
    choice_goalkeeper: Optional[str] = None
    voted: set = field(default_factory=set)

    def record_choice(self, player: discord.Member, direction: str) -> bool:
        """Returns True when both players have chosen."""
        if player.id == self.shooter.id:
            self.choice_shooter = direction
        elif player.id == self.goalkeeper.id:
            self.choice_goalkeeper = direction
        self.voted.add(player.id)
        return (self.choice_shooter is not None
                and self.choice_goalkeeper is not None)

    def resolve_round(self) -> dict:
        is_goal = self.choice_shooter != self.choice_goalkeeper
        result = {
            "is_goal":     is_goal,
            "shooter_dir": DIRECTIONS[self.choice_shooter],
            "keeper_dir":  DIRECTIONS[self.choice_goalkeeper],
        }
        if is_goal:
            self.score_shooter += 1
        else:
            self.score_goalkeeper += 1

        self.choice_shooter    = None
        self.choice_goalkeeper = None
        self.voted             = set()
        self.round_num        += 1
        return result

    def get_winner(self) -> Optional[discord.Member]:
        if self.score_shooter >= self.goal_target:
            return self.shooter
        if self.score_goalkeeper >= self.goal_target:
            return self.goalkeeper
        return None

    def score_line(self) -> str:
        return (
            f"🎯 **{self.shooter.display_name}** (Shooter): {self.score_shooter} ⚽\n"
            f"🧤 **{self.goalkeeper.display_name}** (Goalkeeper): {self.score_goalkeeper} ⚽"
        )
