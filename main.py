import os
import random
import discord
from discord.ext import commands

# Retrieve the token from environment variables
TOKEN = os.getenv("DISCORD_TOKEN")

# Setup intents for message content access
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# D&Z Downtime Activities (Matching the Web App)
DOWNTIME_ACTIVITIES = {
    "scavenge_safe": {"name": "Safe Scavenging", "icon": "🔦", "desc": "Loot a secured area for Food, Water, and basic Scrap."},
    "scavenge_urban": {"name": "Urban Scavenging", "icon": "🏙️", "desc": "High-risk search in city ruins for Firearms, Ammo, and Meds."},
    "fortify": {"name": "Fortifying Base", "icon": "🔨", "desc": "Construct Wood or Metal barricades. Requires Scrap."},
    "traps": {"name": "Setting Traps", "icon": "🕳️", "desc": "Dig Pitfalls or set Snares for defense and small game."},
    "farming": {"name": "Farming/Tending", "icon": "🌽", "desc": "Maintain crops for a major harvest. Yields 4d20 rations."},
    "taming": {"name": "Animal Taming", "icon": "🐕", "desc": "Befriend a stray dog, cat, or coyote."},
    "crafting": {"name": "Makeshift Crafting", "icon": "🛠️", "desc": "Create Spiked Bats, Molotovs, or Suppressors."},
    "vehicle": {"name": "Vehicle Repair", "icon": "🚗", "desc": "Fix Engines, Tires, or Bodywork using Scrap."},
    "recovery": {"name": "Medical Recovery", "icon": "🩹", "desc": "Heal from Infection, Blood Loss, or Amputation surgery."},
    "sanity": {"name": "Sanity Care", "icon": "🚬", "desc": "Lower Insanity Levels through rest or nice meals."}
}

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} - D&Z Survival Bot is Active!")

@bot.command()
async def ping(ctx):
    """Check if the bot is alive."""
    await ctx.send("Pong! 🐺 The wasteland is still standing.")

@bot.command()
async def activities(ctx):
    """List all available D&Z survival activities."""
    embed = discord.Embed(
        title="🧟 D&Z Survival Activities",
        description="Choose a task to spend your campaign downtime. Report results to your GM!",
        color=0xf39c12 # Amber color
    )
    for key, act in DOWNTIME_ACTIVITIES.items():
        embed.add_field(name=f"{act['icon']} {act['name']}", value=act['desc'], inline=False)
    
    await ctx.send(embed=embed)

@bot.command()
async def scavenge(ctx, zone="safe"):
    """Quickly roll for scavenging results (safe or urban)."""
    zone = zone.lower()
    if zone == "urban":
        items = ["Firearms", "Ammo", "Medical Supplies", "Rare Scrap", "Fuel"]
        found = random.choice(items)
        danger = random.randint(1, 20)
        msg = f"🏙️ **Urban Expedition Results**: You found **{found}**! "
        if danger > 15:
            msg += "\n⚠️ *Warning: You were spotted by a horde! GM roll for combat!*"
    else:
        items = ["1d4 Rations", "Clean Water", "Basic Scrap", "Cloth", "Duct Tape"]
        found = random.choice(items)
        msg = f"🔦 **Safe Scavenge Results**: You found **{found}**."
    
    await ctx.send(msg)

@bot.command()
async def rollout(ctx):
    """Roll a standard d20 for survival checks."""
    roll = random.randint(1, 20)
    msg = f"🎲 **Survival Check**: {roll}"
    if roll == 20: msg += " - **CRITICAL SUCCESS!** 🏆"
    elif roll == 1: msg += " - **CRITICAL FAILURE!** 💀"
    await ctx.send(msg)

@bot.command()
async def downtime(ctx):
    """Alias for activities."""
    await activities(ctx)

bot.run(TOKEN)
