"""
views.py  –  All Discord UI components for the penalty shootout bot.

Improvements:
- No ephemeral popups — the public embed updates to show ✅ who has locked in
- Animated step-by-step reveal: suspense → run-up → directions → result → score
- asyncio.Lock for thread-safe round resolution
"""

import asyncio
import discord
from discord.ui import View, Button, button as ui_button
from game import Game, GOAL_FRAME

# ── Colours ──────────────────────────────────────────────────────
C_BLUE   = 0x3B82F6
C_GREEN  = 0x22C55E
C_RED    = 0xEF4444
C_GOLD   = 0xF59E0B
C_GREY   = 0x6B7280
C_ORANGE = 0xF97316
C_PURPLE = 0x8B5CF6


# ═══════════════════════════════════════════════════════════════════
#  Embed builders
# ═══════════════════════════════════════════════════════════════════

def embed_match(game: Game, shooter_ready: bool = False, keeper_ready: bool = False) -> discord.Embed:
    shooter_status = "✅ **Locked in!**" if shooter_ready else "⏳ Choosing…"
    keeper_status  = "✅ **Locked in!**" if keeper_ready  else "⏳ Choosing…"

    desc = (
        f"{GOAL_FRAME}\n"
        f"*Shooter picks where to kick — Goalkeeper picks where to dive.*\n"
        f"*Same direction = 🧤 Save  |  Different = ⚽ Goal*\n\n"
        f"🎯 **{game.shooter.display_name}** (Shooter) — {shooter_status}\n"
        f"🧤 **{game.goalkeeper.display_name}** (Goalkeeper) — {keeper_status}"
    )

    e = discord.Embed(title=f"⚽  PENALTY SHOOTOUT  •  Round {game.round_num}", description=desc, color=C_BLUE)
    e.add_field(name="📊 Score", value=game.score_line(), inline=True)
    e.add_field(name="🏆 Target", value=f"First to **{game.goal_target}** goals", inline=True)
    e.set_footer(text="Both players must choose within 30 s  •  Only you can see your pick")
    return e


def embed_suspense(game: Game) -> discord.Embed:
    return discord.Embed(
        title="🎬  Both players have chosen!",
        description=(
            f"🎯 **{game.shooter.display_name}** steps up to the ball…\n"
            f"🧤 **{game.goalkeeper.display_name}** crouches on the line…\n\n"
            "```\n"
            "  👟  ⚽                          🥅\n"
            "```\n"
            "*The stadium holds its breath…*"
        ),
        color=C_PURPLE,
    )


def embed_run_up(game: Game) -> discord.Embed:
    return discord.Embed(
        title="💨  The run-up…",
        description=(
            "```\n"
            "      ⚽ ────────────────────► 🥅\n"
            "```\n"
            f"**{game.shooter.display_name}** strikes the ball!"
        ),
        color=C_ORANGE,
    )


def embed_reveal_directions(game: Game, result: dict) -> discord.Embed:
    return discord.Embed(
        title="👀  Directions Revealed!",
        description=(
            f"🎯 **{game.shooter.display_name}** kicked  →  **{result['shooter_dir']}**\n"
            f"🧤 **{game.goalkeeper.display_name}** dived   →  **{result['keeper_dir']}**\n\n"
            "*Calculating…*"
        ),
        color=C_ORANGE,
    )


def embed_result(game: Game, result: dict) -> discord.Embed:
    if result["is_goal"]:
        color   = C_GREEN
        title   = "⚽  G O A L !"
        outcome = f"✅  **{game.shooter.display_name}** scores!"
        visual  = "```\n  👟  ⚽ ──────────────────── 🎉\n```"
    else:
        color   = C_RED
        title   = "🧤  S A V E D !"
        outcome = f"🛑  **{game.goalkeeper.display_name}** keeps it out!"
        visual  = "```\n  👟  ⚽ ──────────► 🧤 BLOCKED\n```"

    e = discord.Embed(
        title=title,
        description=(
            f"🎯 **{game.shooter.display_name}** kicked  →  **{result['shooter_dir']}**\n"
            f"🧤 **{game.goalkeeper.display_name}** dived   →  **{result['keeper_dir']}**\n\n"
            f"{visual}\n"
            f"{outcome}"
        ),
        color=color,
    )
    e.add_field(name="📊 Updated Score", value=game.score_line(), inline=False)
    return e


def embed_winner(game: Game, winner: discord.Member) -> discord.Embed:
    e = discord.Embed(
        title="🏆  M A T C H  O V E R",
        description=(
            f"🎉🎉  **{winner.display_name}** wins the penalty shootout!  🎉🎉\n\n"
            "```\n"
            "  ⚽  ⚽  ⚽  ⚽  ⚽  🏆\n"
            "```"
        ),
        color=C_GOLD,
    )
    e.add_field(
        name="🏁 Final Score",
        value=(
            f"🎯 **{game.shooter.display_name}:** {game.score_shooter} ⚽\n"
            f"🧤 **{game.goalkeeper.display_name}:** {game.score_goalkeeper} ⚽"
        ),
        inline=False,
    )
    e.add_field(name="👑 Champion", value=f"{winner.mention} — absolute legend! 🔥", inline=False)
    e.set_footer(text="GG WP! Use /penalty @shooter @goalkeeper <goals> to play again.")
    return e


def embed_cancelled(reason: str) -> discord.Embed:
    return discord.Embed(title="❌  Match Cancelled", description=reason, color=C_GREY)


# ═══════════════════════════════════════════════════════════════════
#  Challenge view  (Accept / Decline)
# ═══════════════════════════════════════════════════════════════════

class ChallengeView(View):
    def __init__(self, game: Game, active_games: dict):
        super().__init__(timeout=60)
        self.game         = game
        self.active_games = active_games
        self.message: discord.Message | None = None

    @ui_button(label="✅  Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, btn: Button):
        valid_ids = {self.game.shooter.id, self.game.goalkeeper.id}
        if interaction.user.id not in valid_ids:
            await interaction.response.send_message(
                "⛔ You're not part of this challenge.", ephemeral=True
            )
            return
        if interaction.user.id == self.game.host.id:
            await interaction.response.send_message(
                "⛔ The host can't accept their own challenge.", ephemeral=True
            )
            return

        await interaction.response.defer()
        self.stop()
        view = PenaltyView(self.game, self.active_games, self.message)
        self.active_games[self.message.id] = self.game
        await self.message.edit(embed=embed_match(self.game), view=view)

    @ui_button(label="❌  Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, btn: Button):
        valid_ids = {self.game.shooter.id, self.game.goalkeeper.id}
        if interaction.user.id not in valid_ids:
            await interaction.response.send_message(
                "⛔ You're not part of this challenge.", ephemeral=True
            )
            return

        await interaction.response.defer()
        self.stop()
        await self.message.edit(
            embed=embed_cancelled(f"**{interaction.user.display_name}** declined the challenge."),
            view=None,
        )

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(
                    embed=embed_cancelled("Challenge expired — nobody accepted in time."),
                    view=None,
                )
            except Exception:
                pass


# ═══════════════════════════════════════════════════════════════════
#  Penalty view  (direction buttons)
# ═══════════════════════════════════════════════════════════════════

class PenaltyView(View):
    """
    Three direction buttons. No ephemeral popups — the embed itself
    updates to show who has locked in (without revealing direction).
    Once both choose, a multi-step animated reveal plays out.
    """

    def __init__(self, game: Game, active_games: dict, message: discord.Message):
        super().__init__(timeout=30)
        self.game         = game
        self.active_games = active_games
        self.message      = message
        self._lock        = asyncio.Lock()
        self._resolved    = False

        for label, value, style in (
            ("⬅️  Left",   "left",   discord.ButtonStyle.primary),
            ("⬆️  Centre", "centre", discord.ButtonStyle.secondary),
            ("➡️  Right",  "right",  discord.ButtonStyle.primary),
        ):
            b = Button(label=label, style=style, custom_id=f"dir_{value}")
            b.callback = self._make_cb(value)
            self.add_item(b)

    def _make_cb(self, direction: str):
        async def cb(interaction: discord.Interaction):
            await self._handle(interaction, direction)
        return cb

    async def _handle(self, interaction: discord.Interaction, direction: str):
        game = self.game
        valid_ids = {game.shooter.id, game.goalkeeper.id}

        if interaction.user.id not in valid_ids:
            await interaction.response.send_message(
                "⛔ You're not playing in this match!", ephemeral=True
            )
            return

        if interaction.user.id in game.voted:
            await interaction.response.send_message(
                "✋ You've already locked in — waiting for your opponent!", ephemeral=True
            )
            return

        if self._resolved:
            await interaction.response.send_message(
                "⚡ Round already resolved!", ephemeral=True
            )
            return

        # Acknowledge silently — no popup
        await interaction.response.defer()

        async with self._lock:
            if self._resolved:
                return

            both_done = game.record_choice(interaction.user, direction)

            # Update embed to show who has locked in (direction stays secret)
            shooter_ready = game.choice_shooter is not None
            keeper_ready  = game.choice_goalkeeper is not None
            try:
                await self.message.edit(
                    embed=embed_match(game, shooter_ready=shooter_ready, keeper_ready=keeper_ready)
                )
            except Exception:
                pass

            if not both_done:
                return

            self._resolved = True

        self.stop()
        await self._animate_and_resolve()

    async def _animate_and_resolve(self):
        game = self.game

        # Step 1 — suspense
        await self.message.edit(embed=embed_suspense(game), view=None)
        await asyncio.sleep(1.5)

        # Step 2 — run-up
        await self.message.edit(embed=embed_run_up(game), view=None)
        await asyncio.sleep(1.2)

        # Resolve the round
        result = game.resolve_round()
        winner = game.get_winner()

        # Step 3 — reveal directions
        await self.message.edit(embed=embed_reveal_directions(game, result), view=None)
        await asyncio.sleep(1.5)

        # Step 4 — goal / save + score
        await self.message.edit(embed=embed_result(game, result), view=None)
        await asyncio.sleep(2.5)

        # Step 5 — winner or next round
        if winner:
            self.active_games.pop(self.message.id, None)
            await self.message.edit(embed=embed_winner(game, winner), view=None)
        else:
            new_view = PenaltyView(game, self.active_games, self.message)
            self.active_games[self.message.id] = game
            await self.message.edit(embed=embed_match(game), view=new_view)

    async def on_timeout(self):
        if self._resolved:
            return
        self.active_games.pop(self.message.id, None)
        game = self.game
        missing = []
        if game.choice_shooter is None:
            missing.append(game.shooter.display_name)
        if game.choice_goalkeeper is None:
            missing.append(game.goalkeeper.display_name)
        who = " & ".join(missing) if missing else "someone"
        try:
            await self.message.edit(
                embed=embed_cancelled(
                    f"⏰ Round timed out — **{who}** didn't choose in time.\n\n"
                    f"{game.score_line()}"
                ),
                view=None,
            )
        except Exception:
            pass
