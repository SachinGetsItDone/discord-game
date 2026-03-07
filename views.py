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
from discord.ui import View, Button, button as ui_button
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
        f"🎯  **{game.shooter.display_name}**  {game.score_shooter}  —  {game.score_goalkeeper}  **{game.goalkeeper.display_name}**  🧤\n"
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
    e.set_footer(text="Pick ⬅️ Left  ·  ⬆️ Centre  ·  ➡️ Right   •   45 s   •   Your pick is secret")
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
            f"🎯  **{game.shooter.display_name}**   {game.score_shooter}  —  {game.score_goalkeeper}   **{game.goalkeeper.display_name}**  🧤"
        )
        color = C_GOLD
    else:
        title = "🤝   I T ' S   A   D R A W"
        desc  = (
            f"```\n{_build_goal()}\n```\n"
            f"Both players finish level — what a match!\n\n"
            f"🎯  **{game.shooter.display_name}**   {game.score_shooter}  —  {game.score_goalkeeper}   **{game.goalkeeper.display_name}**  🧤"
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
        await interaction.response.defer()
        self.stop()
        embed = discord.Embed(
            title="🏆   T O U R N A M E N T   S E T U P",
            description="Select the **Shooter** from your server members:",
            color=C_BLUE,
        )
        view = TournamentSetupView(host=self.host, active_games=self.active_games, message=self.message)
        await self.message.edit(embed=embed, view=view)

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
            "• **5 rounds**, fixed roles throughout\n"
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
#  Tournament Setup  (both selects + Start button shown together)
# ═══════════════════════════════════════════════════════════════════

class TournamentSetupView(View):
    """
    Shows shooter select, goalkeeper select, and shot-count buttons all at once.
    Host fills both dropdowns then hits Start.
    """
    def __init__(self, host: discord.Member, active_games: dict, message: discord.Message):
        super().__init__(timeout=120)
        self.host         = host
        self.active_games = active_games
        self.message      = message
        self.shooter:    discord.Member | None = None
        self.goalkeeper: discord.Member | None = None
        self.total_shots: int = 5

        # Shooter select
        self.shooter_select = discord.ui.UserSelect(
            placeholder="🎯  Select Shooter…",
            min_values=1, max_values=1, row=0
        )
        self.shooter_select.callback = self._shooter_chosen
        self.add_item(self.shooter_select)

        # Goalkeeper select
        self.keeper_select = discord.ui.UserSelect(
            placeholder="🧤  Select Goalkeeper…",
            min_values=1, max_values=1, row=1
        )
        self.keeper_select.callback = self._keeper_chosen
        self.add_item(self.keeper_select)

        # Shot count buttons
        for i, n in enumerate([3, 5, 7, 10]):
            b = Button(
                label=f"{n} shots",
                style=discord.ButtonStyle.primary if n == 5 else discord.ButtonStyle.secondary,
                custom_id=f"shots_{n}",
                row=2,
            )
            b.callback = self._make_shots_cb(n)
            self.add_item(b)

        # Start button
        self.start_btn = Button(label="▶️  Start Match", style=discord.ButtonStyle.success, row=3, disabled=True, custom_id="start_match")
        self.start_btn.callback = self._start
        self.add_item(self.start_btn)

    def _make_shots_cb(self, n: int):
        async def cb(interaction: discord.Interaction):
            if interaction.user.id != self.host.id:
                await interaction.response.send_message("⛔ Only the host can set this up.", ephemeral=True)
                return
            self.total_shots = n
            # Highlight selected shot button
            for item in self.children:
                if isinstance(item, Button) and item.custom_id and item.custom_id.startswith("shots_"):
                    item.style = discord.ButtonStyle.primary if item.custom_id == f"shots_{n}" else discord.ButtonStyle.secondary
            await interaction.response.defer()
            await self._refresh()
        return cb

    async def _shooter_chosen(self, interaction: discord.Interaction):
        if interaction.user.id != self.host.id:
            await interaction.response.send_message("⛔ Only the host can set this up.", ephemeral=True)
            return
        uid = int(interaction.data["values"][0])
        self.shooter = interaction.guild.get_member(uid) or await interaction.guild.fetch_member(uid)
        if self.shooter and self.shooter.bot:
            self.shooter = None
            await interaction.response.send_message("⛔ Bots can't play.", ephemeral=True)
            return
        await interaction.response.defer()
        await self._refresh()

    async def _keeper_chosen(self, interaction: discord.Interaction):
        if interaction.user.id != self.host.id:
            await interaction.response.send_message("⛔ Only the host can set this up.", ephemeral=True)
            return
        uid = int(interaction.data["values"][0])
        self.goalkeeper = interaction.guild.get_member(uid) or await interaction.guild.fetch_member(uid)
        if self.goalkeeper and self.goalkeeper.bot:
            self.goalkeeper = None
            await interaction.response.send_message("⛔ Bots can't play.", ephemeral=True)
            return
        await interaction.response.defer()
        await self._refresh()

    async def _refresh(self):
        """Update embed status and enable Start when both are selected."""
        s_line = f"🎯  Shooter      →   {self.shooter.mention}" if self.shooter else "🎯  Shooter      →   *not selected*"
        k_line = f"🧤  Goalkeeper →   {self.goalkeeper.mention}" if self.goalkeeper else "🧤  Goalkeeper →   *not selected*"

        both_set = self.shooter is not None and self.goalkeeper is not None
        same     = both_set and self.shooter.id == self.goalkeeper.id
        either_bot = (self.shooter and self.shooter.bot) or (self.goalkeeper and self.goalkeeper.bot)

        # Enable/disable start
        for item in self.children:
            if isinstance(item, Button) and item.custom_id == "start_match":
                item.disabled = not both_set or same or either_bot

        warning = ""
        if same:           warning = "\n\n⛔  Shooter and goalkeeper must be different!"
        elif either_bot:   warning = "\n\n⛔  Bots can't play!"

        embed = discord.Embed(
            title="🏆   T O U R N A M E N T   S E T U P",
            description=(
                f"{s_line}\n"
                f"{k_line}\n\n"
                f"🔢  Shots each   →   **{self.total_shots}**"
                f"{warning}\n\n"
                f"*Select both players above, then hit  ▶️ Start Match*"
            ),
            color=C_BLUE,
        )
        await self.message.edit(embed=embed, view=self)

    async def _start(self, interaction: discord.Interaction):
        if interaction.user.id != self.host.id:
            await interaction.response.send_message("⛔ Only the host can start.", ephemeral=True)
            return
        if self.shooter is None or self.goalkeeper is None:
            await interaction.response.send_message("⛔ Select both players first.", ephemeral=True)
            return
        if self.shooter.id == self.goalkeeper.id:
            await interaction.response.send_message("⛔ Shooter and goalkeeper must be different.", ephemeral=True)
            return

        await interaction.response.defer()
        self.stop()

        game = Game.tournament(
            host=self.host,
            shooter=self.shooter,
            goalkeeper=self.goalkeeper,
            total_shots=self.total_shots,
        )

        embed = discord.Embed(
            title="🏆   T O U R N A M E N T   C H A L L E N G E",
            description=(
                f"🎙️  **Host:** {self.host.mention} has set up a match!\n\n"
                f"🎯  **Shooter:**      {self.shooter.mention}\n"
                f"🧤  **Goalkeeper:**   {self.goalkeeper.mention}\n"
                f"🔢  **Shots each:**   {self.total_shots}\n\n"
                f"**{self.shooter.display_name}** or **{self.goalkeeper.display_name}** — accept or decline!"
            ),
            color=C_BLUE,
        )
        embed.add_field(name="📋 Rules", value=(
            "• Both secretly pick ⬅️ Left, ⬆️ Centre or ➡️ Right\n"
            "• **Same direction** → 🧤 Save\n"
            "• **Different** → ⚽ Goal\n"
            f"• **{self.total_shots} shots** each — most goals wins!"
        ), inline=False)
        embed.set_footer(text="Challenge expires in 60 s")

        view = ChallengeView(game=game, active_games=self.active_games)
        await self.message.edit(embed=embed, view=view)
        view.message = self.message

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(embed=embed_cancelled("Tournament setup expired."), view=None)
            except Exception:
                pass


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
        game = Game.friendly(
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
        valid_ids = {self.game.shooter.id, self.game.goalkeeper.id}
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
                await self.message.edit(embed=embed_cancelled("Challenge expired — nobody accepted in time."), view=None)
            except Exception:
                pass


# ═══════════════════════════════════════════════════════════════════
#  Penalty View  (direction buttons — shared by both modes)
# ═══════════════════════════════════════════════════════════════════

class PenaltyView(View):
    def __init__(self, game: Game, active_games: dict, message: discord.Message):
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
