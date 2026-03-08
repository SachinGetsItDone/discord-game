"""
bot.py — Entry point for the Penalty Shootout Discord bot.

Commands:
  /penalty_tournament @shooter @goalkeeper [shots]
      Host assigns roles directly. Either player accepts to start.

  /penalty_friendly [@opponent] [shots]
      Challenge someone (or open to anyone). Roles assigned randomly at kick-off.
"""

import os
import discord
from discord import app_commands
from discord.ext import commands

from game import Game, MODE_TOURNAMENT, MODE_FRIENDLY
from views import ChallengeView, FriendlyChallengeView, C_BLUE

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.members = True

bot  = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

active_games: dict[int, Game] = {}


@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅  Online as {bot.user}  (ID: {bot.user.id})")


# ── /penalty_tournament ──────────────────────────────────────────

@tree.command(name="penalty_tournament", description="Host sets up a tournament penalty match.")
@app_commands.describe(
    shooter    = "The player who shoots first",
    goalkeeper = "The player who keeps goal",
    shots      = "Shots each player takes (default 5)",
)
async def penalty_tournament(
    interaction: discord.Interaction,
    shooter:     discord.Member,
    goalkeeper:  discord.Member,
    shots:       app_commands.Range[int, 1, 10] = 5,
):
    host = interaction.user

    if shooter.bot or goalkeeper.bot:
        await interaction.response.send_message("⛔ Bots can't play.", ephemeral=True); return
    if shooter.id == goalkeeper.id:
        await interaction.response.send_message("⛔ Shooter and goalkeeper must be different people.", ephemeral=True); return

    game = Game.tournament(host=host, player_a=shooter, player_b=goalkeeper, total_shots=shots)

    embed = discord.Embed(
        title="🏆   T O U R N A M E N T   C H A L L E N G E",
        description=(
            f"🎙️  **Host:** {host.mention} has set up a match!\n\n"
            f"🎯  **Shooter:**      {shooter.mention}\n"
            f"🧤  **Goalkeeper:**   {goalkeeper.mention}\n"
            f"🔢  **Shots each:**   {shots}\n\n"
            f"**{shooter.display_name}** or **{goalkeeper.display_name}** — accept or decline!"
        ),
        color=C_BLUE,
    )
    embed.add_field(name="📋 Rules", value=(
        "• Both secretly pick ⬅️ Left, ⬆️ Centre or ➡️ Right\n"
        "• **Same direction** → 🧤 Save\n"
        "• **Different** → ⚽ Goal\n"
        f"• **{shots} shots** each — most goals wins!"
    ), inline=False)
    embed.set_footer(text="Challenge expires in 60 s")

    view = ChallengeView(game=game, active_games=active_games)
    await interaction.response.send_message(embed=embed, view=view)
    view.message = await interaction.original_response()


# ── /penalty_friendly ────────────────────────────────────────────

@tree.command(name="penalty_friendly", description="Challenge someone to a friendly penalty shootout.")
@app_commands.describe(
    opponent = "Who to challenge (leave blank for open challenge)",
    shots    = "Shots each player takes (default 5)",
)
async def penalty_friendly(
    interaction: discord.Interaction,
    opponent:    discord.Member | None = None,
    shots:       app_commands.Range[int, 1, 10] = 5,
):
    host = interaction.user

    if opponent:
        if opponent.bot:
            await interaction.response.send_message("⛔ Bots can't play.", ephemeral=True); return
        if opponent.id == host.id:
            await interaction.response.send_message("⛔ You can't challenge yourself!", ephemeral=True); return

    target_line = f"{opponent.mention}" if opponent else "*Open challenge — anyone can accept!*"

    embed = discord.Embed(
        title="⚽   F R I E N D L Y   C H A L L E N G E",
        description=(
            f"🎙️  **{host.display_name}** wants a match!\n\n"
            f"🎯  **Challenging:** {target_line}\n"
            f"🔢  **Shots each:**  {shots}\n\n"
            f"Roles (shooter / goalkeeper) are assigned **randomly** at kick-off!"
        ),
        color=C_BLUE,
    )
    embed.add_field(name="📋 Rules", value=(
        "• Both secretly pick ⬅️ Left, ⬆️ Centre or ➡️ Right\n"
        "• **Same direction** → 🧤 Save\n"
        "• **Different** → ⚽ Goal\n"
        f"• **{shots} shots** each — most goals wins!"
    ), inline=False)
    embed.set_footer(text="Challenge expires in 60 s")

    view = FriendlyChallengeView(host=host, opponent=opponent, total_shots=shots, active_games=active_games)
    await interaction.response.send_message(embed=embed, view=view)
    view.message = await interaction.original_response()


# ── Run ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("❌  DISCORD_TOKEN not set")
    bot.run(TOKEN)
