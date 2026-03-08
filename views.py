import asyncio
import discord
from discord.ui import View, Button, button as ui_button

from game import (
    Game, DIRECTIONS, MODE_TOURNAMENT, MODE_FRIENDLY,
    grid_idle, grid_runup, grid_flying, grid_result,
)

C_BLUE   = 0x3B82F6
C_GREEN  = 0x22C55E
C_RED    = 0xEF4444
C_GOLD   = 0xF59E0B
C_GREY   = 0x6B7280
C_ORANGE = 0xF97316
C_PURPLE = 0x8B5CF6
C_DARK   = 0x1E1E2E


# ═══════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════

def _scorebar(game: Game) -> str:
    half_label = "1st Half" if game.half == 1 else "2nd Half"
    return (
        f"⚽  **{game.player_a.display_name}**  `{game.score_a} — {game.score_b}`  "
        f"**{game.player_b.display_name}**  ⚽\n"
        f"🔢  {half_label}  •  Shot **{game.shot_in_half}** / **{game.total_shots}**"
    )


def _roleline(game: Game) -> str:
    return (
        f"🎯  **Shooter** → {game.shooter.mention}\n"
        f"🧤  **Keeper**  → {game.goalkeeper.mention}"
    )


# ═══════════════════════════════════════════════════════════════════
#  Embed builders
# ═══════════════════════════════════════════════════════════════════

def embed_match(game: Game, waiting_for: str = "") -> discord.Embed:
    desc = f"{grid_idle()}\n{_roleline(game)}\n\n*Both pick secretly — same = 🧤 Save, different = ⚽ Goal*"
    if waiting_for:
        desc += f"\n\n⏳  Waiting for **{waiting_for}**…"
    e = discord.Embed(title="⚽   P E N A L T Y   S H O O T O U T", description=desc, color=C_BLUE)
    e.add_field(name="📊 Score", value=_scorebar(game), inline=False)
    e.set_footer(text="You have 45 seconds  •  Your pick is secret")
    return e


def embed_suspense(game: Game) -> discord.Embed:
    return discord.Embed(
        title="😤   S T E P P I N G   U P . . .",
        description=(
            f"{grid_idle()}"
            f"**{game.shooter.display_name}** places the ball on the spot…\n"
            f"**{game.goalkeeper.mention}** holds the line.\n\n"
            f"*The crowd goes silent* 🤫"
        ),
        color=C_ORANGE,
    )


def embed_runup(game: Game, keeper_dir: str) -> discord.Embed:
    return discord.Embed(
        title="🏃   R U N N I N G   U P !",
        description=(
            f"{grid_runup(keeper_dir)}"
            f"**{game.shooter.display_name}** charges forward!\n"
            f"🧤  The keeper commits — dives **{DIRECTIONS[keeper_dir]}**!\n\n"
            f"*Which way did the shooter go?* 👀"
        ),
        color=C_ORANGE,
    )


def embed_flying(game: Game, shot_dir: str, keeper_dir: str) -> discord.Embed:
    return discord.Embed(
        title="💨   B A L L   I N   T H E   A I R !",
        description=(
            f"{grid_flying(shot_dir, keeper_dir)}"
            f"**{game.shooter.display_name}** shoots **{DIRECTIONS[shot_dir]}**!\n\n"
            f"*It's going in… or is it?* 😱"
        ),
        color=C_ORANGE,
    )


def embed_goal(game: Game, shot_dir: str, keeper_dir: str, shooter: discord.Member, keeper: discord.Member) -> discord.Embed:
    e = discord.Embed(
        title="⚽   G  O  A  L  !   🔥",
        description=(
            f"{grid_result(shot_dir, keeper_dir, True)}"
            f"🎯  **{shooter.display_name}** kicked  {DIRECTIONS[shot_dir]}\n"
            f"🧤  **{keeper.display_name}** dived    {DIRECTIONS[keeper_dir]}\n\n"
            f"✅  **{shooter.display_name}** scores! The net bulges!"
        ),
        color=C_GREEN,
    )
    e.add_field(name="📊 Score", value=_scorebar(game), inline=False)
    return e


def embed_saved(game: Game, shot_dir: str, keeper_dir: str, shooter: discord.Member, keeper: discord.Member) -> discord.Embed:
    e = discord.Embed(
        title="🧤   S  A  V  E  D  !   💪",
        description=(
            f"{grid_result(shot_dir, keeper_dir, False)}"
            f"🎯  **{shooter.display_name}** kicked  {DIRECTIONS[shot_dir]}\n"
            f"🧤  **{keeper.display_name}** dived    {DIRECTIONS[keeper_dir]}\n\n"
            f"🛑  **{keeper.display_name}** read it perfectly!"
        ),
        color=C_RED,
    )
    e.add_field(name="📊 Score", value=_scorebar(game), inline=False)
    return e


def embed_halftime(game: Game) -> discord.Embed:
    e = discord.Embed(
        title="🔄   H A L F   T I M E",
        description=(
            f"**{game.player_a.display_name}** has taken all {game.total_shots} shots!\n\n"
            f"🔁  Now **{game.player_b.display_name}** steps up to shoot\n"
            f"🧤  **{game.player_a.display_name}** takes the gloves\n\n"
            f"───────────────────\n"
            f"📊  **{game.score_line()}**\n"
            f"───────────────────"
        ),
        color=C_PURPLE,
    )
    e.set_footer(text="2nd half kicks off shortly…")
    return e


def embed_final(game: Game) -> discord.Embed:
    if game.score_a > game.score_b:
        winner = game.player_a
        title  = f"🏆   {winner.display_name.upper()}   W I N S !"
        color  = C_GOLD
        banner = "🎉🎊🎉🎊🎉🎊🎉🎊🎉🎊"
    elif game.score_b > game.score_a:
        winner = game.player_b
        title  = f"🏆   {winner.display_name.upper()}   W I N S !"
        color  = C_GOLD
        banner = "🎉🎊🎉🎊🎉🎊🎉🎊🎉🎊"
    else:
        winner = None
        title  = "🤝   I  T ' S   A   D  R  A  W  !"
        color  = C_BLUE
        banner = "🏳️🏳️  What a battle — honours even!  🏳️🏳️"

    e = discord.Embed(title=title, description=banner, color=color)
    e.add_field(
        name="🏁 Full Time Score",
        value=(
            f"```\n"
            f"  {game.player_a.display_name:<20} {game.score_a}\n"
            f"  {game.player_b.display_name:<20} {game.score_b}\n"
            f"```"
        ),
        inline=False,
    )
    if winner:
        e.add_field(name="👑 Champion", value=f"{winner.mention}  —  absolute legend! 🔥", inline=False)
    e.set_footer(text="GG WP!  Use /penalty_tournament or /penalty_friendly to play again")
    return e


def embed_cancelled(reason: str) -> discord.Embed:
    return discord.Embed(title="❌   Match Cancelled", description=reason, color=C_GREY)


# ═══════════════════════════════════════════════════════════════════
#  Friendly Challenge View
# ═══════════════════════════════════════════════════════════════════

class FriendlyChallengeView(View):
    def __init__(self, host, opponent, total_shots, active_games):
        super().__init__(timeout=60)
        self.host         = host
        self.opponent     = opponent
        self.total_shots  = total_shots
        self.active_games = active_games
        self.message      = None

    @ui_button(label="✅  Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, btn: Button):
        if interaction.user.bot:
            await interaction.response.send_message("⛔ Bots can't play.", ephemeral=True); return
        if interaction.user.id == self.host.id:
            await interaction.response.send_message("⛔ You can't accept your own challenge!", ephemeral=True); return
        if self.opponent and interaction.user.id != self.opponent.id:
            await interaction.response.send_message(f"⛔ This challenge is for {self.opponent.mention} only.", ephemeral=True); return

        await interaction.response.defer()
        self.stop()
        try:
            game = Game.friendly(player_a=self.host, player_b=interaction.user, total_shots=self.total_shots)
            self.active_games[self.message.id] = game
            view = PenaltyView(game=game, active_games=self.active_games, message=self.message)
            await self.message.edit(embed=embed_match(game), view=view)
        except Exception as e:
            await self.message.edit(embed=embed_cancelled(f"❌ Error: {e}"), view=None)

    @ui_button(label="❌  Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, btn: Button):
        valid = {self.host.id}
        if self.opponent:
            valid.add(self.opponent.id)
        if interaction.user.id not in valid:
            await interaction.response.send_message("⛔ You're not part of this challenge.", ephemeral=True); return
        await interaction.response.defer()
        self.stop()
        await self.message.edit(embed=embed_cancelled(f"**{interaction.user.display_name}** declined."), view=None)

    async def on_timeout(self):
        if self.message:
            try: await self.message.edit(embed=embed_cancelled("Challenge expired — nobody accepted in time."), view=None)
            except Exception: pass


# ═══════════════════════════════════════════════════════════════════
#  Tournament Challenge View
# ═══════════════════════════════════════════════════════════════════

class ChallengeView(View):
    def __init__(self, game: Game, active_games: dict):
        super().__init__(timeout=60)
        self.game         = game
        self.active_games = active_games
        self.message      = None

    @ui_button(label="✅  Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, btn: Button):
        if interaction.user.bot:
            await interaction.response.send_message("⛔ Bots can't play.", ephemeral=True); return
        valid_ids = {self.game.player_a.id, self.game.player_b.id}
        if interaction.user.id not in valid_ids:
            await interaction.response.send_message("⛔ You're not part of this challenge.", ephemeral=True); return
        if interaction.user.id == self.game.host.id:
            await interaction.response.send_message("⛔ The host can't accept their own challenge.", ephemeral=True); return

        await interaction.response.defer()
        self.stop()
        self.active_games[self.message.id] = self.game
        view = PenaltyView(game=self.game, active_games=self.active_games, message=self.message)
        await self.message.edit(embed=embed_match(self.game), view=view)

    @ui_button(label="❌  Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, btn: Button):
        valid_ids = {self.game.player_a.id, self.game.player_b.id}
        if interaction.user.id not in valid_ids:
            await interaction.response.send_message("⛔ You're not part of this challenge.", ephemeral=True); return
        await interaction.response.defer()
        self.stop()
        await self.message.edit(embed=embed_cancelled(f"**{interaction.user.display_name}** declined."), view=None)

    async def on_timeout(self):
        if self.message:
            try: await self.message.edit(embed=embed_cancelled("Challenge expired — nobody accepted in time."), view=None)
            except Exception: pass


# ═══════════════════════════════════════════════════════════════════
#  Penalty View  (direction buttons)
# ═══════════════════════════════════════════════════════════════════

class PenaltyView(View):
    def __init__(self, game: Game, active_games: dict, message):
        super().__init__(timeout=45)
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
            await interaction.response.send_message("⛔ You're not playing in this match!", ephemeral=True); return
        if interaction.user.id in game.voted:
            await interaction.response.send_message("✋ Already locked in — waiting for your opponent!", ephemeral=True); return
        if self._resolved:
            await interaction.response.send_message("⚡ Round already resolved!", ephemeral=True); return

        role = "🎯" if interaction.user.id == game.shooter.id else "🧤"
        dir_label = {"left": "⬅️ LEFT", "centre": "⬆️ CENTRE", "right": "➡️ RIGHT"}[direction]
        await interaction.response.send_message(
            f"{role}  Locked in: **{dir_label}** ✅\n*Waiting for your opponent…*",
            ephemeral=True,
        )

        async with self._lock:
            if self._resolved:
                return
            both_done = game.record_choice(interaction.user, direction)
            if not both_done:
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
            self._resolved = True

        self.stop()
        await self._animate_and_resolve()

    async def _animate_and_resolve(self):
        game = self.game

        # Capture who shot/kept BEFORE resolve increments round_num
        shooter    = game.shooter
        goalkeeper = game.goalkeeper

        # Step 1 — suspense
        await self.message.edit(embed=embed_suspense(game), view=None)
        await asyncio.sleep(0.7)

        # Resolve to get directions
        result     = game.resolve_round()
        shot_dir   = result["shot_dir"]
        keeper_dir = result["keeper_dir"]
        is_goal    = result["is_goal"]

        # Step 2 — keeper commits (run-up)
        await self.message.edit(embed=embed_runup(game, keeper_dir), view=None)
        await asyncio.sleep(0.6)

        # Step 3 — ball flying
        await self.message.edit(embed=embed_flying(game, shot_dir, keeper_dir), view=None)
        await asyncio.sleep(0.7)

        # Step 4 — result
        if is_goal:
            await self.message.edit(embed=embed_goal(game, shot_dir, keeper_dir, shooter, goalkeeper), view=None)
        else:
            await self.message.edit(embed=embed_saved(game, shot_dir, keeper_dir, shooter, goalkeeper), view=None)
        await asyncio.sleep(1.5)

        # Next state
        if game.is_over():
            self.active_games.pop(self.message.id, None)
            await self.message.edit(embed=embed_final(game), view=None)
        elif game.round_num == game.total_shots + 1:
            await self.message.edit(embed=embed_halftime(game), view=None)
            await asyncio.sleep(3.0)
            new_view = PenaltyView(game=game, active_games=self.active_games, message=self.message)
            self.active_games[self.message.id] = game
            await self.message.edit(embed=embed_match(game), view=new_view)
        else:
            new_view = PenaltyView(game=game, active_games=self.active_games, message=self.message)
            self.active_games[self.message.id] = game
            await self.message.edit(embed=embed_match(game), view=new_view)

    async def on_timeout(self):
        if self._resolved:
            return
        self.active_games.pop(self.message.id, None)
        game = self.game
        missing = []
        if game._choice_shooter is None:
            missing.append(game.shooter.display_name)
        if game._choice_goalkeeper is None:
            missing.append(game.goalkeeper.display_name)
        who = " & ".join(missing) if missing else "someone"
        try:
            await self.message.edit(
                embed=embed_cancelled(
                    f"⏰  **{who}** didn't choose in time.\n\n{game.score_line()}"
                ),
                view=None,
            )
        except Exception:
            pass
