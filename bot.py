"""
bot.py  –  Entry point for the Penalty Shootout Discord bot.

Command:
    /penalty

Bot replies with mode selector buttons (Tournament / Friendly).

Tournament mode: bot asks for @shooter, @goalkeeper, and shots count.
Friendly mode:   the person who runs /penalty is player A; bot posts a
                 challenge embed that anyone can accept as player B.
"""

import os
import discord
from discord import app_commands
from discord.ext import commands

from views import ModeSelectView, C_BLUE

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.members = True

bot  = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# active_games: message_id → Game
active_games: dict = {}


@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅  Online as {bot.user}  (ID: {bot.user.id})")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.playing,
            name="⚽ Penalty Shootout | /penalty"
        )
    )


@tree.command(
    name="penalty",
    description="Start a penalty shootout — choose Tournament or Friendly mode.",
)
async def penalty(interaction: discord.Interaction):
    embed = discord.Embed(
        title="⚽  PENALTY SHOOTOUT",
        description=(
            "Choose a game mode:\n\n"
            "🏆 **Tournament** — Host assigns a Shooter & Goalkeeper. Fixed shots, best score wins.\n\n"
            "🤝 **Friendly** — Challenge anyone! You both take turns shooting & saving."
        ),
        color=C_BLUE,
    )
    embed.set_footer(text="Select a mode below • Expires in 60 s")
    view = ModeSelectView(host=interaction.user, active_games=active_games)
    await interaction.response.send_message(embed=embed, view=view)
    message = await interaction.original_response()
    view.message = message


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("❌  DISCORD_TOKEN not set")
    bot.run(TOKEN)
