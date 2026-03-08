"""
views.py  –  All Discord UI components for the penalty shootout bot.

Key fixes vs original:
- Every button callback does interaction.response.defer() FIRST to
  acknowledge within the 3-second window, then edits follow-up.
- Embed builders are standalone functions (no side-effects).
- asyncio.Lock used properly so only one coroutine resolves a round.
- ChallengeView stores message reference via on_send(), not externally.
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


# ═══════════════════════════════════════════════════════════════════
#  Embed builders
# ═══════════════════════════════════════════════════════════════════

def embed_match(game: Game, waiting_for: str = "") -> discord.Embed:
    desc = (
        f"🎯 **Shooter** → {game.shooter.mention}\n"
        f"🧤 **Goalkeeper** → {game.goalkeeper.mention}\n\n"
        f"{GOAL_FRAME}\n"
        f"*Shooter picks where to kick — Goalkeeper picks where to dive.*\n"
        f"*Same direction = 🧤 Save  |  Different = ⚽ Goal*"
    )
    if waiting_for:
        desc += f"\n\n⏳ Waiting for **{waiting_for}** to choose…"

    e = discord.Embed(title="⚽  PENALTY SHOOTOUT", description=desc, color=C_BLUE)
    e.add_field(name="📊 Score", value=game.score_line(), inline=False)
    e.add_field(
        name="🎯 Target",
        value=f"First to **{game.goal_target}** goals wins!  •  Round **{game.round_num}**",
        inline=False,
    )
    e.set_footer(text="Both players must choose within 30 s.")
    return e


def embed_animating(game: Game) -> discord.Embed:
    e = discord.Embed(
        title="🥅  Shooting…",
        description=(
            f"**{game.shooter.display_name}** is taking the shot!\n\n"
            "```\n   ⚽ ──────────────────► 🥅\n```"
        ),
        color=C_ORANGE,
    )
    e.set_footer(text="Calculating result…")
    return e


def embed_result(game: Game, result: dict) -> discord.Embed:
    if result["is_goal"]:
        color  = C_GREEN
        title  = "⚽  G O A L !"
        outcome = f"✅ **{game.shooter.display_name}** scores!"
    else:
        color  = C_RED
        title  = "🧤  S A V E D !"
        outcome = f"🛑 **{game.goalkeeper.display_name}** saves it!"

    e = discord.Embed(
        title=title,
        description=(
            f"🎯 **{game.shooter.display_name}** shoots  {result['shooter_dir']}\n"
            f"🧤 **{game.goalkeeper.display_name}** dives   {result['keeper_dir']}\n\n"
            f"{outcome}"
        ),
        color=color,
    )
    e.add_field(name="📊 Updated Score", value=game.score_line(), inline=False)
    return e


def embed_winner(game: Game, winner: discord.Member) -> discord.Embed:
    e = discord.Embed(
        title="🏆  M A T C H  W I N N E R",
        description=(
            f"🎉🎉  **{winner.display_name}** wins the penalty shootout!  🎉🎉\n\n"
            "⚽ 🥅 ⚽ 🥅 ⚽ 🥅 ⚽ 🥅 ⚽ 🥅"
        ),
        color=C_GOLD,
    )
    e.add_field(
        name="🏁 Final Score",
        value=(
            f"**{game.player_a.display_name}:** {game.score_a} ⚽\n"
            f"**{game.player_b.display_name}:** {game.score_b} ⚽"
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

    # ── Accept ──────────────────────────────────────────────────────
    @ui_button(label="✅  Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, btn: Button):
        # Only the shooter OR goalkeeper can accept (either of the two players)
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

        # Acknowledge immediately — prevents "Interaction Failed"
        await interaction.response.defer()

        self.stop()
        view = PenaltyView(self.game, self.active_games, self.message)
        self.active_games[self.message.id] = self.game
        await self.message.edit(embed=embed_match(self.game), view=view)

    # ── Decline ─────────────────────────────────────────────────────
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
            embed=embed_cancelled(
                f"**{interaction.user.display_name}** declined the challenge."
            ),
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
    Three buttons: ⬅️ Left | ⬆️ Centre | ➡️ Right
    Both the shooter and goalkeeper each press one button (ephemeral feedback).
    Once both have chosen the round is resolved automatically.
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

    # ── Build per-direction callback ─────────────────────────────────
    def _make_cb(self, direction: str):
        async def cb(interaction: discord.Interaction):
            await self._handle(interaction, direction)
        return cb

    # ── Core handler ─────────────────────────────────────────────────
    async def _handle(self, interaction: discord.Interaction, direction: str):
        game = self.game
        valid_ids = {game.shooter.id, game.goalkeeper.id}

        # Guard: not a player
        if interaction.user.id not in valid_ids:
            await interaction.response.send_message(
                "⛔ You're not playing in this match!", ephemeral=True
            )
            return

        # Guard: already voted this round
        if interaction.user.id in game.voted:
            await interaction.response.send_message(
                "✋ You've already chosen — waiting for your opponent!", ephemeral=True
            )
            return

        # Guard: round already resolved (race condition safety)
        if self._resolved:
            await interaction.response.send_message(
                "⚡ Round already resolved!", ephemeral=True
            )
            return

        # Acknowledge the interaction IMMEDIATELY — this is what prevents
        # "Interaction Failed".  We use ephemeral=True so only they see it.
        role = "🎯 Shooter" if interaction.user.id == game.shooter.id else "🧤 Goalkeeper"
        await interaction.response.send_message(
            f"{role}: You picked **{direction.upper()}** ✅  Waiting for opponent…",
            ephemeral=True,
        )

        # Now record the choice (thread-safe)
        async with self._lock:
            if self._resolved:          # double-check inside the lock
                return
            both_done = game.record_choice(interaction.user, direction)
            if not both_done:
                # Update public embed to show who we're waiting for
                waiting_name = (
                    game.goalkeeper.display_name
                    if interaction.user.id == game.shooter.id
                    else game.shooter.display_name
                )
                try:
                    await self.message.edit(embed=embed_match(game, waiting_for=waiting_name))
                except Exception:
                    pass
                return
            self._resolved = True       # mark before releasing lock

        # Both chosen — stop accepting more clicks, then animate + resolve
        self.stop()
        await self._animate_and_resolve()

    # ── Animation + resolution ───────────────────────────────────────
    async def _animate_and_resolve(self):
        game = self.game

        # Shooting animation
        await self.message.edit(embed=embed_animating(game), view=None)
        await asyncio.sleep(1.5)

        # Resolve
        result  = game.resolve_round()
        winner  = game.get_winner()

        if winner:
            self.active_games.pop(self.message.id, None)
            await self.message.edit(embed=embed_result(game, result), view=None)
            await asyncio.sleep(2.5)
            await self.message.edit(embed=embed_winner(game, winner), view=None)
        else:
            await self.message.edit(embed=embed_result(game, result), view=None)
            await asyncio.sleep(2.5)
            new_view = PenaltyView(game, self.active_games, self.message)
            self.active_games[self.message.id] = game
            await self.message.edit(embed=embed_match(game), view=new_view)

    # ── Timeout ──────────────────────────────────────────────────────
    async def on_timeout(self):
        if self._resolved:
            return
        self.active_games.pop(self.message.id, None)
        missing = []
        game = self.game
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
