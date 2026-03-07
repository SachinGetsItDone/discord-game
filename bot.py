"""
bot.py  –  Entry point for the Penalty Shootout Discord bot.

Commands:
    /penalty tournament @shooter @goalkeeper [shots]
    /penalty friendly [@opponent] [shots]
"""

import os
import discord
from discord import app_commands
from discord.ext import commands

from views import ChallengeView, FriendlyChallengeView, C_BLUE
from game import Game

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.members = True

bot  = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

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


# ── /penalty tournament ──────────────────────────────────────────
@tree.command(name="penalty_tournament", description="🏆 Tournament — host picks shooter, goalkeeper & shot count.")
@app_commands.describe(
    shooter    = "The player who will take all the shots",
    goalkeeper = "The player who will defend the goal",
    shots      = "Number of shots each (1–10, default 5)",
)
async def penalty_tournament(
    interaction: discord.Interaction,
    shooter:    discord.Member,
    goalkeeper: discord.Member,
    shots:      app_commands.Range[int, 1, 10] = 5,
):
    host = interaction.user

    if shooter.bot or goalkeeper.bot:
        await interaction.response.send_message("⛔ Bots can't play.", ephemeral=True)
        return
    if shooter.id == goalkeeper.id:
        await interaction.response.send_message("⛔ Shooter and goalkeeper must be different people.", ephemeral=True)
        return

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
        f"• **{shots} shots** — most goals wins!"
    ), inline=False)
    embed.set_footer(text="Challenge expires in 60 s")

    view = ChallengeView(game=game, active_games=active_games)
    await interaction.response.send_message(embed=embed, view=view)
    message = await interaction.original_response()
    view.message = message


# ── /penalty friendly ────────────────────────────────────────────
@tree.command(name="penalty_friendly", description="🤝 Friendly — challenge someone (or leave open for anyone).")
@app_commands.describe(
    opponent = "Who you want to challenge (leave empty for open challenge)",
    shots    = "Number of shots (1–10, default 5)",
)
async def penalty_friendly(
    interaction: discord.Interaction,
    opponent: discord.Member = None,
    shots:    app_commands.Range[int, 1, 10] = 5,
):
    host = interaction.user

    if opponent:
        if opponent.bot:
            await interaction.response.send_message("⛔ Bots can't play.", ephemeral=True)
            return
        if opponent.id == host.id:
            await interaction.response.send_message("⛔ You can't challenge yourself.", ephemeral=True)
            return
        target_str = f"{opponent.mention} has been challenged"
        mention    = opponent.mention
    else:
        target_str = "Open challenge — anyone can accept!"
        mention    = "anyone"

    embed = discord.Embed(
        title="🤝   F R I E N D L Y   C H A L L E N G E",
        description=(
            f"**{host.display_name}** wants a friendly penalty shootout!\n\n"
            f"{target_str}\n\n"
            f"🔢  **Shots:** {shots}\n"
            f"🎲  Roles (Shooter / Goalkeeper) assigned **randomly** at kick-off!\n\n"
            f"Hit ✅ Accept to play!"
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

    view = FriendlyChallengeView(host=host, opponent=opponent, active_games=active_games, total_shots=shots)
    await interaction.response.send_message(embed=embed, view=view)
    message = await interaction.original_response()
    view.message = message


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("❌  DISCORD_TOKEN not set")
    bot.run(TOKEN)
