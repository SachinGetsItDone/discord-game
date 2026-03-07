"""
views.py  –  All Discord UI components for the Penalty Shootout bot.

Flow:
  /penalty
    └─ ModeSelectView  (Tournament | Friendly)
         ├─ Tournament → TournamentSetupView  (modal: @shooter @goalkeeper shots)
         │                └─ ChallengeView   (Accept / Decline by either player)
         │                     └─ PenaltyView (direction buttons, N rounds)
         └─ Friendly   → FriendlyChallengeView (anyone can Accept)
                          └─ PenaltyView
"""

import asyncio
import discord
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput, button as ui_button
from game import Game, MODE_TOURNAMENT, MODE_FRIENDLY, DIRECTIONS

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
#  Layout (13 wide):  POST [L L L] SEP [C C C] SEP [R R R] POST
#  Always 6 lines tall — same height every animation frame.

POST  = "🟫"
BAR   = "🟨"
NET   = "⬛"
SEP   = "🔲"
GRASS = "🟩"
BALL  = "⚽"
GLOVE = "🧤"


def _build_goal(ball_dir=None, keeper_dir=None, ball_in_net=False, keeper_visible=True):
    def zone(ball_here, keeper_here):
        if ball_in_net and ball_here and keeper_here:
            return [GLOVE, GLOVE, GLOVE]   # save — ball swallowed by glove
        if ball_in_net and ball_here:
            return [NET, BALL, NET]         # goal — ball in net
        if keeper_here:
            return [NET, GLOVE, NET]        # keeper standing/diving
        return [NET, NET, NET]             # empty zone

    # Default keeper to centre if visible but no direction yet
    kdir = keeper_dir if keeper_dir is not None else ("centre" if keeper_visible else None)

    lk = kdir == "left"
    ck = kdir == "centre"
    rk = kdir == "right"
    lb = ball_in_net and ball_dir == "left"
    cb = ball_in_net and ball_dir == "centre"
    rb = ball_in_net and ball_dir == "right"

    L = zone(lb, lk)
    C = zone(cb, ck)
    R = zone(rb, rk)

    def row(l, c, r):
        return POST + "".join(l) + SEP + "".join(c) + SEP + "".join(r) + POST

    empty = [NET, NET, NET]
    lines = [
        POST + BAR*3 + SEP + BAR*3 + SEP + BAR*3 + POST,   # crossbar
        row(empty, empty, empty),                            # top net (always empty)
        row(L, C, R),                                        # action row
        row(empty, empty, empty),                            # bottom net (always empty)
        GRASS * 13,
        GRASS * 13 if ball_in_net else GRASS * 6 + BALL + GRASS * 6,
    ]
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
#  Shared embed helpers
# ═══════════════════════════════════════════════════════════════════

def _mode_tag(game: Game) -> str:
    return "🏆 Tournament" if game.mode == MODE_TOURNAMENT else "🤝 Friendly"

def _role_line(game: Game) -> str:
    if game.mode == MODE_TOURNAMENT:
        return (
            f"🎯  Shooter  →  {game.shooter.mention}\n"
            f"🧤  Keeper   →  {game.goalkeeper.mention}"
        )
    return (
        f"🎯  Shooting  →  {game.shooter.mention}\n"
        f"🧤  In goal   →  {game.goalkeeper.mention}"
    )

def _score_bar(game: Game) -> str:
    return (
        f"**{game.player_a.display_name}**  {game.score_a}  —  {game.score_b}  **{game.player_b.display_name}**\n"
        f"🔢  Round  **{game.round_num}**  /  **{game.total_shots}**"
    )

def embed_match(game: Game, shooter_ready=False, keeper_ready=False) -> discord.Embed:
    s = "✅  Locked in!" if shooter_ready else "⏳  Choosing…"
    k = "✅  Locked in!" if keeper_ready  else "⏳  Choosing…"
    e = discord.Embed(
        title=f"⚽   P E N A L T Y   S H O O T O U T   ·   {_mode_tag(game)}",
        description=(
            f"```\n{_build_goal()}\n```\n"
            f"{_role_line(game)}\n\n"
            f"🎯  {game.shooter.display_name}   —   {s}\n"
            f"🧤  {game.goalkeeper.display_name}   —   {k}\n\n"
            f"{_score_bar(game)}"
        ),
        color=C_BLUE,
    )
    e.set_footer(text="Pick ⬅️ Left  ·  ⬆️ Centre  ·  ➡️ Right   •   30 s   •   Your pick is secret")
    return e

def embed_suspense(game: Game) -> discord.Embed:
    e = discord.Embed(
        title="🎬   B O T H   C H O S E N !",
        description=(
            f"```\n{_build_goal()}\n```\n"
            f"🎯  **{game.shooter.display_name}**  steps up to the ball…\n"
            f"🧤  **{game.goalkeeper.display_name}**  crouches on the line…\n\n"
            f"*⚡ The stadium holds its breath… ⚡*\n\n"
            f"{_score_bar(game)}"
        ),
        color=C_PURPLE,
    )
    e.set_footer(text="Revealing in a moment…")
    return e

def embed_run_up(game: Game) -> discord.Embed:
    e = discord.Embed(
        title="💨   T H E   R U N - U P !",
        description=(
            f"```\n{_build_goal()}\n```\n"
            f"**{game.shooter.display_name}**  charges forward and  **S T R I K E S !**  🦵\n\n"
            f"{_score_bar(game)}"
        ),
        color=C_ORANGE,
    )
    e.set_footer(text="Where did it go…?")
    return e

def embed_ball_flying(game: Game, ball_dir: str, keeper_dir: str) -> discord.Embed:
    e = discord.Embed(
        title="⚽   B A L L   I N   T H E   A I R !",
        description=(
            f"```\n{_build_goal(ball_dir=ball_dir, keeper_dir=keeper_dir, ball_in_net=True)}\n```\n"
            f"🎯  **{game.shooter.display_name}**  kicked   →   **{ball_dir.upper()}**\n"
            f"🧤  **{game.goalkeeper.display_name}**  dived    →   **{keeper_dir.upper()}**\n\n"
            f"{_score_bar(game)}"
        ),
        color=C_ORANGE,
    )
    e.set_footer(text="Calculating result…")
    return e

def embed_result(game: Game, result: dict) -> discord.Embed:
    bd, kd = result["shooter_raw"], result["keeper_raw"]
    if result["is_goal"]:
        color, title, outcome = C_GREEN, "⚽   G  O  A  L  !", f"✅   **{game.shooter.display_name}**  scores!"
    else:
        color, title, outcome = C_RED,   "🧤   S  A  V  E  D  !", f"🛑   **{game.goalkeeper.display_name}**  saves it!"
    e = discord.Embed(
        title=title,
        description=(
            f"```\n{_build_goal(ball_dir=bd, keeper_dir=kd, ball_in_net=True)}\n```\n"
            f"🎯  **{game.shooter.display_name}**  kicked   →   **{result['shooter_dir']}**\n"
            f"🧤  **{game.goalkeeper.display_name}**  dived    →   **{result['keeper_dir']}**\n\n"
            f"{outcome}\n\n"
            f"{_score_bar(game)}"
        ),
        color=color,
    )
    return e

def embed_final(game: Game) -> discord.Embed:
    winner = game.get_winner()
    if winner:
        title = "🏆   M A T C H   O V E R"
        desc  = (
            f"```\n{_build_goal()}\n```\n"
            f"🎉   **{winner.display_name}**  wins the shootout!   🎉\n\n"
            f"**{game.player_a.display_name}**   {game.score_a}  —  {game.score_b}   **{game.player_b.display_name}**"
        )
        color = C_GOLD
    else:
        title = "🤝   I T ' S   A   D R A W"
        desc  = (
            f"```\n{_build_goal()}\n```\n"
            f"Both players finish level — what a match!\n\n"
            f"**{game.player_a.display_name}**   {game.score_a}  —  {game.score_b}   **{game.player_b.display_name}**"
        )
        color = C_GREY

    e = discord.Embed(title=title, description=desc, color=color)
    if winner:
        e.add_field(name="👑 Champion", value=f"{winner.mention} — absolute legend! 🔥", inline=False)
    e.set_footer(text="GG WP!  ·  Use /penalty to play again.")
    return e

def embed_cancelled(reason: str) -> discord.Embed:
    return discord.Embed(title="❌   Match Cancelled", description=reason, color=C_GREY)


# ═══════════════════════════════════════════════════════════════════
#  Mode Select View
# ═══════════════════════════════════════════════════════════════════

class ModeSelectView(View):
    def __init__(self, host: discord.Member, active_games: dict):
        super().__init__(timeout=60)
        self.host         = host
        self.active_games = active_games
        self.message: discord.Message | None = None

    @ui_button(label="🏆  Tournament", style=discord.ButtonStyle.primary)
    async def tournament(self, interaction: discord.Interaction, btn: Button):
        if interaction.user.id != self.host.id:
            await interaction.response.send_message("⛔ Only the host can set up the match.", ephemeral=True)
            return
        await interaction.response.send_modal(
            TournamentSetupModal(host=self.host, active_games=self.active_games, message=self.message)
        )
        self.stop()

    @ui_button(label="🤝  Friendly", style=discord.ButtonStyle.secondary)
    async def friendly(self, interaction: discord.Interaction, btn: Button):
        if interaction.user.id != self.host.id:
            await interaction.response.send_message("⛔ Only the person who ran /penalty can start.", ephemeral=True)
            return
        await interaction.response.defer()
        self.stop()
        embed = discord.Embed(
            title="🤝  FRIENDLY MATCH CHALLENGE",
            description=(
                f"**{self.host.display_name}** wants a friendly penalty shootout!\n\n"
                f"You'll take turns shooting and saving.\n"
                f"**{self.host.display_name}** shoots first.\n\n"
                f"Anyone can accept below!"
            ),
            color=C_BLUE,
        )
        embed.add_field(name="📋 Rules", value=(
            "• Both secretly pick ⬅️ Left, ⬆️ Centre or ➡️ Right\n"
            "• **Same direction** → 🧤 Save\n"
            "• **Different** → ⚽ Goal\n"
            "• **5 rounds**, roles swap each round\n"
            "• Most goals wins!"
        ), inline=False)
        embed.set_footer(text="Challenge expires in 60 s")
        view = FriendlyChallengeView(host=self.host, active_games=self.active_games)
        await self.message.edit(embed=embed, view=view)
        view.message = self.message

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(embed=embed_cancelled("Mode selection expired."), view=None)
            except Exception:
                pass


# ═══════════════════════════════════════════════════════════════════
#  Tournament Setup Modal
# ═══════════════════════════════════════════════════════════════════

class TournamentSetupModal(Modal, title="🏆 Tournament Setup"):
    shooter_input    = TextInput(label="Shooter's username or @mention",    placeholder="e.g. john or @john",  max_length=50)
    goalkeeper_input = TextInput(label="Goalkeeper's username or @mention", placeholder="e.g. jane or @jane", max_length=50)
    shots_input      = TextInput(label="Shots each (1–10)", placeholder="5", default="5", max_length=2)

    def __init__(self, host: discord.Member, active_games: dict, message: discord.Message):
        super().__init__()
        self.host         = host
        self.active_games = active_games
        self.message      = message

    async def on_submit(self, interaction: discord.Interaction):
        # Parse shots
        try:
            shots = int(self.shots_input.value.strip())
            if not 1 <= shots <= 10:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("⛔ Shots must be a number between 1 and 10.", ephemeral=True)
            return

        # Resolve shooter
        shooter = await _resolve_member(interaction, self.shooter_input.value.strip())
        if shooter is None:
            await interaction.response.send_message(
                f"⛔ Could not find member: `{self.shooter_input.value}`", ephemeral=True
            )
            return

        # Resolve goalkeeper
        goalkeeper = await _resolve_member(interaction, self.goalkeeper_input.value.strip())
        if goalkeeper is None:
            await interaction.response.send_message(
                f"⛔ Could not find member: `{self.goalkeeper_input.value}`", ephemeral=True
            )
            return

        if shooter.bot or goalkeeper.bot:
            await interaction.response.send_message("⛔ Bots can't play.", ephemeral=True)
            return
        if shooter.id == goalkeeper.id:
            await interaction.response.send_message("⛔ Shooter and goalkeeper must be different people.", ephemeral=True)
            return

        game = Game(
            mode=MODE_TOURNAMENT,
            host=self.host,
            player_a=shooter,
            player_b=goalkeeper,
            total_shots=shots,
        )

        embed = discord.Embed(
            title="🏆  TOURNAMENT CHALLENGE",
            description=(
                f"🎙️ **Host:** {self.host.mention} has set up a match!\n\n"
                f"🎯 **Shooter:**    {shooter.mention}\n"
                f"🧤 **Goalkeeper:** {goalkeeper.mention}\n"
                f"🔢 **Shots each:** {shots}\n\n"
                f"**{shooter.display_name}** or **{goalkeeper.display_name}** — accept or decline!"
            ),
            color=C_BLUE,
        )
        embed.add_field(name="📋 Rules", value=(
            "• Both secretly pick ⬅️ Left, ⬆️ Centre or ➡️ Right\n"
            "• **Same direction** → 🧤 Save\n"
            "• **Different** → ⚽ Goal\n"
            f"• **{shots} shots** — most goals wins!"
        ), inline=False)
        embed.set_footer(text="Challenge expires in 60 s")

        view = ChallengeView(game=game, active_games=self.active_games)
        await interaction.response.defer()
        await self.message.edit(embed=embed, view=view)
        view.message = self.message


async def _resolve_member(interaction: discord.Interaction, text: str) -> discord.Member | None:
    """Try to resolve a member from a mention or username string."""
    # Strip <@123> mention format
    if text.startswith("<@") and text.endswith(">"):
        uid = text.strip("<@!>")
        try:
            return interaction.guild.get_member(int(uid)) or await interaction.guild.fetch_member(int(uid))
        except Exception:
            return None
    # Try by display name / username
    text_lower = text.lstrip("@").lower()
    for m in interaction.guild.members:
        if m.name.lower() == text_lower or m.display_name.lower() == text_lower:
            return m
    return None


# ═══════════════════════════════════════════════════════════════════
#  Friendly Challenge View
# ═══════════════════════════════════════════════════════════════════

class FriendlyChallengeView(View):
    def __init__(self, host: discord.Member, active_games: dict):
        super().__init__(timeout=60)
        self.host         = host
        self.active_games = active_games
        self.message: discord.Message | None = None

    @ui_button(label="✅  Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, btn: Button):
        if interaction.user.id == self.host.id:
            await interaction.response.send_message("⛔ You can't accept your own challenge!", ephemeral=True)
            return
        if interaction.user.bot:
            return
        await interaction.response.defer()
        self.stop()
        game = Game(
            mode=MODE_FRIENDLY,
            host=self.host,
            player_a=self.host,
            player_b=interaction.user,
            total_shots=5,
        )
        self.active_games[self.message.id] = game
        view = PenaltyView(game=game, active_games=self.active_games, message=self.message)
        await self.message.edit(embed=embed_match(game), view=view)

    @ui_button(label="❌  Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, btn: Button):
        if interaction.user.id == self.host.id:
            await interaction.response.defer()
            self.stop()
            await self.message.edit(embed=embed_cancelled("Challenge cancelled by host."), view=None)
            return
        await interaction.response.send_message("⛔ Only the host can cancel, or someone else can accept!", ephemeral=True)

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(embed=embed_cancelled("Friendly challenge expired — nobody accepted."), view=None)
            except Exception:
                pass


# ═══════════════════════════════════════════════════════════════════
#  Tournament Challenge View  (Accept / Decline by either player)
# ═══════════════════════════════════════════════════════════════════

class ChallengeView(View):
    def __init__(self, game: Game, active_games: dict):
        super().__init__(timeout=60)
        self.game         = game
        self.active_games = active_games
        self.message: discord.Message | None = None

    @ui_button(label="✅  Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, btn: Button):
        valid_ids = {self.game.player_a.id, self.game.player_b.id}
        if interaction.user.id not in valid_ids:
            await interaction.response.send_message("⛔ You're not part of this challenge.", ephemeral=True)
            return
        await interaction.response.defer()
        self.stop()
        self.active_games[self.message.id] = self.game
        view = PenaltyView(game=self.game, active_games=self.active_games, message=self.message)
        await self.message.edit(embed=embed_match(self.game), view=view)

    @ui_button(label="❌  Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, btn: Button):
        valid_ids = {self.game.player_a.id, self.game.player_b.id}
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
                await self.message.edit(embed=embed_cancelled("Challenge expired — nobody accepted in time."), view=None)
            except Exception:
                pass


# ═══════════════════════════════════════════════════════════════════
#  Penalty View  (direction buttons — shared by both modes)
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
            shooter_ready = game._choice_shooter is not None
            keeper_ready  = game._choice_goalkeeper is not None
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
        shooter_dir_raw = game._choice_shooter
        keeper_dir_raw  = game._choice_goalkeeper

        await self.message.edit(embed=embed_suspense(game), view=None)
        await asyncio.sleep(0.6)

        await self.message.edit(embed=embed_run_up(game), view=None)
        await asyncio.sleep(0.5)

        result = game.resolve_round()
        result["shooter_raw"] = shooter_dir_raw
        result["keeper_raw"]  = keeper_dir_raw

        await self.message.edit(embed=embed_ball_flying(game, shooter_dir_raw, keeper_dir_raw), view=None)
        await asyncio.sleep(0.8)

        await self.message.edit(embed=embed_result(game, result), view=None)
        await asyncio.sleep(1.2)

        if game.is_over():
            self.active_games.pop(self.message.id, None)
            await self.message.edit(embed=embed_final(game), view=None)
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
        if not hasattr(game, "_choice_shooter") or game._choice_shooter is None:
            missing.append(game.shooter.display_name)
        if not hasattr(game, "_choice_goalkeeper") or game._choice_goalkeeper is None:
            missing.append(game.goalkeeper.display_name)
        who = " & ".join(missing) if missing else "someone"
        try:
            await self.message.edit(
                embed=embed_cancelled(f"⏰ Round timed out — **{who}** didn't choose in time.\n\n{game.score_line()}"),
                view=None,
            )
        except Exception:
            pass
