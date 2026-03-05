"""
views.py  –  All Discord UI components for the penalty shootout bot.

Visual: emoji front-view goal (posts, net, pitch, ball on spot).
        Keeper and ball animate into position during the reveal.
Fixed embed size — goal frame present on every state, no resize.
"""

import asyncio
import discord
from discord.ui import View, Button, button as ui_button
from game import Game

# ── Colours ──────────────────────────────────────────────────────
C_BLUE   = 0x3B82F6
C_GREEN  = 0x22C55E
C_RED    = 0xEF4444
C_GOLD   = 0xF59E0B
C_GREY   = 0x6B7280
C_ORANGE = 0xF97316
C_PURPLE = 0x8B5CF6


# ═══════════════════════════════════════════════════════════════════
#  Goal renderer
# ═══════════════════════════════════════════════════════════════════
#
#  The goal is a 9-wide emoji grid (cols 0-8).
#  Three zones:  LEFT = cols 1-2 | CENTRE = cols 3-5 | RIGHT = cols 6-7
#  Posts = col 0 & 8  (🟫)  Crossbar row = top row
#
#  ball_dir / keeper_dir: "left" | "centre" | "right" | None

# Centre column for each zone (where the emoji appears)
ZONE_COL = {"left": 1, "centre": 4, "right": 7}

POST  = "🟫"
NET   = "⬛"
GRASS = "🟩"
SPOT  = "⚽"   # ball on penalty spot (always shown on pitch row)


def _build_goal(ball_dir=None, keeper_dir=None, ball_in_net=False, keeper_visible=True) -> str:
    """
    Returns a 6-line emoji goal string.
    - keeper_visible: always show keeper (centre if no dir given)
    - ball_dir      : zone ball went (shown in net when ball_in_net=True)
    - keeper_dir    : zone keeper dived (replaces centre standing position)
    - ball_in_net   : show ball inside net
    """
    WIDTH = 9

    net = [[NET] * WIDTH for _ in range(3)]

    for row in net:
        row[0] = POST
        row[8] = POST

    # Keeper always visible — centre by default, dives to dir when revealed
    if keeper_visible:
        col = ZONE_COL[keeper_dir] if keeper_dir is not None else ZONE_COL["centre"]
        net[1][col] = "🧤"

    # Ball in net
    if ball_in_net and ball_dir is not None:
        bcol = ZONE_COL[ball_dir]
        if keeper_dir is not None and ZONE_COL[keeper_dir] == bcol:
            # Save: glove catches ball — show glove in both rows, no ball
            net[1][bcol] = "🧤"
            net[2][bcol] = "🧤"
        else:
            net[2][bcol] = "⚽"

    # Crossbar row (top)
    crossbar = POST + "🟨" * 7 + POST

    # Assemble rows
    rows = [crossbar]
    for row in net:
        rows.append("".join(row))

    # Pitch rows
    rows.append(GRASS * WIDTH)
    rows.append(GRASS * WIDTH if ball_in_net else GRASS * 4 + SPOT + GRASS * 4)

    return "\n".join(rows)


# ═══════════════════════════════════════════════════════════════════
#  Embed builders  (fixed layout — goal frame always present)
# ═══════════════════════════════════════════════════════════════════

def _score_field(game):
    return game.score_line()

def _target_field(game):
    return f"First to **{game.goal_target}** goals"


def embed_match(game: Game, shooter_ready=False, keeper_ready=False) -> discord.Embed:
    s = "✅ **Locked in!**" if shooter_ready else "⏳ Choosing…"
    k = "✅ **Locked in!**" if keeper_ready  else "⏳ Choosing…"
    e = discord.Embed(
        title=f"⚽  PENALTY SHOOTOUT  •  Round {game.round_num}",
        description=(
            f"```\n{_build_goal()}\n```"
            f"🎯 **{game.shooter.display_name}** — {s}\n"
            f"🧤 **{game.goalkeeper.display_name}** — {k}"
        ),
        color=C_BLUE,
    )
    e.add_field(name="📊 Score",    value=_score_field(game),  inline=True)
    e.add_field(name="🏆 Target",   value=_target_field(game), inline=True)
    e.set_footer(text="Pick a direction  •  Your choice is secret  •  30 s")
    return e


def embed_suspense(game: Game) -> discord.Embed:
    e = discord.Embed(
        title="🎬  Both players have chosen!",
        description=(
            f"```\n{_build_goal()}\n```"
            f"🎯 **{game.shooter.display_name}** steps up…\n"
            f"🧤 **{game.goalkeeper.display_name}** crouches on the line…\n"
            f"*The stadium holds its breath…*"
        ),
        color=C_PURPLE,
    )
    e.add_field(name="📊 Score",  value=_score_field(game),  inline=True)
    e.add_field(name="🏆 Target", value=_target_field(game), inline=True)
    e.set_footer(text="Revealing…")
    return e


def embed_run_up(game: Game) -> discord.Embed:
    e = discord.Embed(
        title="💨  The run-up!",
        description=(
            f"```\n{_build_goal()}\n```"
            f"**{game.shooter.display_name}** charges and STRIKES! 🦵"
        ),
        color=C_ORANGE,
    )
    e.add_field(name="📊 Score",  value=_score_field(game),  inline=True)
    e.add_field(name="🏆 Target", value=_target_field(game), inline=True)
    e.set_footer(text="Where did it go…?")
    return e


def embed_ball_flying(game: Game, ball_dir: str, keeper_dir: str) -> discord.Embed:
    """Ball and keeper both shown in their chosen zones. Save = glove only."""
    e = discord.Embed(
        title="⚽  Ball in the air!",
        description=(
            f"```\n{_build_goal(ball_dir=ball_dir, keeper_dir=keeper_dir, ball_in_net=True)}\n```"
            f"🎯 **{game.shooter.display_name}** kicked **{ball_dir.upper()}**\n"
            f"🧤 **{game.goalkeeper.display_name}** dived **{keeper_dir.upper()}**"
        ),
        color=C_ORANGE,
    )
    e.add_field(name="📊 Score",  value=_score_field(game),  inline=True)
    e.add_field(name="🏆 Target", value=_target_field(game), inline=True)
    e.set_footer(text="Revealing keeper…")
    return e


def embed_result(game: Game, result: dict) -> discord.Embed:
    bd = result["shooter_raw"]
    kd = result["keeper_raw"]

    if result["is_goal"]:
        color  = C_GREEN
        title  = "⚽  G O A L !"
        outcome = f"✅  **{game.shooter.display_name}** scores!"
    else:
        color  = C_RED
        title  = "🧤  S A V E D !"
        outcome = f"🛑  **{game.goalkeeper.display_name}** keeps it out!"

    e = discord.Embed(
        title=title,
        description=(
            f"```\n{_build_goal(ball_dir=bd, keeper_dir=kd, ball_in_net=True)}\n```"
            f"🎯 **{game.shooter.display_name}** kicked  **{result['shooter_dir']}**\n"
            f"🧤 **{game.goalkeeper.display_name}** dived   **{result['keeper_dir']}**\n\n"
            f"{outcome}"
        ),
        color=color,
    )
    e.add_field(name="📊 Updated Score", value=_score_field(game),  inline=True)
    e.add_field(name="🏆 Target",        value=_target_field(game), inline=True)
    return e


def embed_winner(game: Game, winner: discord.Member) -> discord.Embed:
    e = discord.Embed(
        title="🏆  M A T C H  O V E R",
        description=(
            f"```\n{_build_goal()}\n```"
            f"🎉  **{winner.display_name}** wins the penalty shootout!  🎉"
        ),
        color=C_GOLD,
    )
    e.add_field(
        name="🏁 Final Score",
        value=(
            f"🎯 **{game.shooter.display_name}:** {game.score_shooter} ⚽\n"
            f"🧤 **{game.goalkeeper.display_name}:** {game.score_goalkeeper} ⚽"
        ),
        inline=True,
    )
    e.add_field(name="👑 Champion", value=f"{winner.mention} — absolute legend! 🔥", inline=True)
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
            await interaction.response.send_message("⛔ You're not part of this challenge.", ephemeral=True)
            return
        if interaction.user.id == self.game.host.id:
            await interaction.response.send_message("⛔ The host can't accept their own challenge.", ephemeral=True)
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
            await interaction.response.send_message("⛔ You're not part of this challenge.", ephemeral=True)
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
            await interaction.response.send_message("⛔ You're not playing in this match!", ephemeral=True)
            return
        if interaction.user.id in game.voted:
            await interaction.response.send_message("✋ Already locked in — waiting for opponent!", ephemeral=True)
            return
        if self._resolved:
            await interaction.response.send_message("⚡ Round already resolved!", ephemeral=True)
            return

        await interaction.response.defer()

        async with self._lock:
            if self._resolved:
                return
            both_done = game.record_choice(interaction.user, direction)
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

        # Capture directions before resolve wipes them
        shooter_dir_raw = game.choice_shooter
        keeper_dir_raw  = game.choice_goalkeeper

        # Step 1 — suspense (empty goal)
        await self.message.edit(embed=embed_suspense(game), view=None)
        await asyncio.sleep(0.6)

        # Step 2 — run-up (empty goal)
        await self.message.edit(embed=embed_run_up(game), view=None)
        await asyncio.sleep(0.5)

        # Resolve
        result = game.resolve_round()
        result["shooter_raw"] = shooter_dir_raw
        result["keeper_raw"]  = keeper_dir_raw
        winner = game.get_winner()

        # Step 3 — ball AND keeper both revealed in their zones simultaneously
        await self.message.edit(embed=embed_ball_flying(game, shooter_dir_raw, keeper_dir_raw), view=None)
        await asyncio.sleep(0.8)

        # Step 4 — result verdict with score update
        await self.message.edit(embed=embed_result(game, result), view=None)
        await asyncio.sleep(1.2)

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
                    f"⏰ Round timed out — **{who}** didn't choose in time.\n\n{game.score_line()}"
                ),
                view=None,
            )
        except Exception:
            pass
