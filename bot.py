"""
bot.py  –  Entry point for the Penalty Shootout Discord bot.

Command:
    /penalty @shooter @goalkeeper <goals>

    @shooter    – the player who takes all the shots
    @goalkeeper – the player who defends
    goals       – number of goals needed to win (must be 1–20, odd recommended)

The host who runs the command is NOT a player; they just set up the match.
Either of the two named players can click Accept/Decline on the challenge embed.
"""

import os
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from game import Game
from views import ChallengeView, C_BLUE

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# ── Bot ──────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.members = True

bot  = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# active_games: message_id → Game
active_games: dict[int, Game] = {}


# ── Ready ────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅  Online as {bot.user}  (ID: {bot.user.id})")
    print(
        f"🔗  Invite: https://discord.com/api/oauth2/authorize"
        f"?client_id={bot.user.id}&permissions=277025770560&scope=bot%20applications.commands"
    )
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.playing,
            name="⚽ Penalty Shootout | /penalty"
        )
    )


# ── /penalty command ─────────────────────────────────────────────
@tree.command(
    name="penalty",
    description="Set up a penalty shootout. Host assigns shooter, goalkeeper & goal target.",
)
@app_commands.describe(
    shooter    = "The player who will take all the shots",
    goalkeeper = "The player who will defend the goal",
    goals      = "Goals needed to win (1–20). Use an odd number to avoid draws.",
)
async def penalty(
    interaction: discord.Interaction,
    shooter:     discord.Member,
    goalkeeper:  discord.Member,
    goals:       app_commands.Range[int, 1, 20] = 5,
):
    host = interaction.user

    # ── Validation ───────────────────────────────────────────────
    if shooter.bot or goalkeeper.bot:
        await interaction.response.send_message(
            "⛔ Bots can't play.", ephemeral=True
        )
        return

    if shooter.id == goalkeeper.id:
        await interaction.response.send_message(
            "⛔ Shooter and goalkeeper must be different people.", ephemeral=True
        )
        return

    # ── Build embed ──────────────────────────────────────────────
    game = Game(host=host, shooter=shooter, goalkeeper=goalkeeper, goal_target=goals)

    embed = discord.Embed(
        title="⚽  PENALTY SHOOTOUT CHALLENGE",
        description=(
            f"🎙️ **Host:** {host.mention} has set up a match!\n\n"
            f"🎯 **Shooter:**    {shooter.mention}\n"
            f"🧤 **Goalkeeper:** {goalkeeper.mention}\n"
            f"🏆 **First to:**   {goals} goal{'s' if goals != 1 else ''}\n\n"
            f"**{shooter.display_name}** or **{goalkeeper.display_name}** — "
            f"accept or decline below!"
        ),
        color=C_BLUE,
    )
    embed.add_field(
        name="📋 Rules",
        value=(
            "• Both players secretly choose ⬅️ Left, ⬆️ Centre or ➡️ Right\n"
            "• **Same direction** → 🧤 Save\n"
            "• **Different directions** → ⚽ Goal\n"
            f"• First to **{goals}** wins!"
        ),
        inline=False,
    )
    embed.set_footer(text="Challenge expires in 60 seconds.")

    view = ChallengeView(game, active_games)

    # Respond to the interaction — this is the ONLY response.send_message
    # in the whole command; no follow-ups that could race each other.
    await interaction.response.send_message(embed=embed, view=view)

    # Grab the message object and hand it to the view so it can edit later
    message = await interaction.original_response()
    view.message = message


# ── Run ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("❌  DISCORD_TOKEN not set in .env")
    bot.run(TOKEN)
