import os
import random
import time
import json
import discord
from discord.ext import commands
from datetime import datetime

# Allow configuring a data directory via environment variables (vital for Railway volumes)
DATA_DIR = os.getenv("DATA_DIR", ".")

COOLDOWN_FILE = os.path.join(DATA_DIR, "cooldowns.json")
ASSIGNMENTS_FILE = os.path.join(DATA_DIR, "character_assignments.json")
PLAYER_CHARS_DIR = os.path.join(DATA_DIR, "player-characters")
DISABLED_ACTIVITIES_FILE = os.path.join(DATA_DIR, "disabled_activities.json")

def load_json(filepath, default):
    try:
        with open(filepath, "r", encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return default

def save_json(filepath, data):
    with open(filepath, "w", encoding='utf-8') as f:
        json.dump(data, f, indent=2)

user_cooldowns = load_json(COOLDOWN_FILE, {})
user_assignments = load_json(ASSIGNMENTS_FILE, {})
disabled_activities = load_json(DISABLED_ACTIVITIES_FILE, [])

def get_latest_folder():
    if not os.path.exists(PLAYER_CHARS_DIR):
        os.makedirs(PLAYER_CHARS_DIR)
        return None
    folders = [f for f in os.listdir(PLAYER_CHARS_DIR) if os.path.isdir(os.path.join(PLAYER_CHARS_DIR, f))]
    valid_folders = []
    for f in folders:
        try:
            dt = datetime.strptime(f, "%m-%d-%Y.%I-%M%p")
            valid_folders.append((dt, f))
        except ValueError:
            pass
    if not valid_folders:
        return None
    valid_folders.sort(key=lambda x: x[0], reverse=True)
    return os.path.join(PLAYER_CHARS_DIR, valid_folders[0][1])

def get_character_file(char_name):
    latest_folder = get_latest_folder()
    if not latest_folder: return None, None
    for file in os.listdir(latest_folder):
        if file.endswith('.json'):
            path = os.path.join(latest_folder, file)
            data = load_json(path, None)
            if data and "character" in data and "name" in data["character"]:
                if data["character"]["name"].strip().lower() == char_name.strip().lower():
                    return path, data
    return None, None

def get_assigned_character(user_id):
    char_name = user_assignments.get(str(user_id))
    if not char_name: return None, None
    return get_character_file(char_name)

async def is_activity_disabled(key, ctx):
    if key in disabled_activities:
        await ctx.send(f"❌ **{DOWNTIME_ACTIVITIES[key]['name']}** is currently locked/disabled by the GM.")
        return True
    return False

async def check_and_consume_cooldown(ctx):
    """
    Checks if the user has an available downtime action.
    Returns True if they can proceed, False if they are on cooldown.
    """
    user_id = str(ctx.author.id)
    now = time.time()
    
    # Load history and clean up timestamps older than 24h (86400s)
    history = user_cooldowns.get(user_id, [])
    history = [ts for ts in history if now - ts < 86400]
    
    # 1. Check max 2 per 24 hours
    if len(history) >= 2:
        oldest_ts = history[0]
        time_until_reset = (oldest_ts + 86400) - now
        hours = int(time_until_reset // 3600)
        minutes = int((time_until_reset % 3600) // 60)
        await ctx.send(f"⏳ **Cooldown**: {ctx.author.mention}, you've hit your limit of 2 downtime actions per 24 hours. Next action available in **{hours}h {minutes}m**.")
        return False

    # 2. Check 8-hour cooldown between individual runs (28800s)
    if len(history) > 0:
        most_recent_ts = history[-1]
        time_since_last = now - most_recent_ts
        if time_since_last < 28800:
            time_until_next = 28800 - time_since_last
            hours = int(time_until_next // 3600)
            minutes = int((time_until_next % 3600) // 60)
            await ctx.send(f"⏳ **Cooldown**: {ctx.author.mention}, you must rest for **{hours}h {minutes}m** before doing another downtime activity.")
            return False

    # Consume the action
    history.append(now)
    user_cooldowns[user_id] = history
    save_json(COOLDOWN_FILE, user_cooldowns)
    return True

# Retrieve the token from environment variables
TOKEN = os.getenv("DISCORD_TOKEN")

# Setup intents for message content access
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True

bot = commands.Bot(command_prefix="!", intents=intents)

DOWNTIME_ACTIVITIES = {
    "scavenge_safe": {"name": "Safe Scavenging", "icon": "🔦", "cmd": "`!scavenge`", "desc": "Loot a secured area for Food, Water, and basic Scrap."},
    "scavenge_urban": {"name": "Urban Scavenging", "icon": "🏙️", "cmd": "`!scavenge urban`", "desc": "High-risk search in city ruins for Firearms, Ammo, and Meds."},
    "fortify": {"name": "Fortifying Base", "icon": "🔨", "cmd": "`!fortify`", "desc": "Construct Wood or Metal barricades. Requires Scrap."},
    "traps": {"name": "Setting Traps", "icon": "🕳️", "cmd": "`!activity traps`", "desc": "Dig Pitfalls or set Snares for defense and small game."},
    "farming": {"name": "Farming/Tending", "icon": "🌽", "cmd": "`!activity farming`", "desc": "Maintain crops for a major harvest. Yields 4d20 rations."},
    "taming": {"name": "Animal Taming", "icon": "🐕", "cmd": "`!activity taming`", "desc": "Befriend a stray dog, cat, or coyote."},
    "crafting": {"name": "Makeshift Crafting", "icon": "🛠️", "cmd": "`!activity crafting`", "desc": "Create Spiked Bats, Molotovs, or Suppressors."},
    "vehicle": {"name": "Vehicle Repair", "icon": "🚗", "cmd": "`!activity vehicle`", "desc": "Fix Engines, Tires, or Bodywork using Scrap."},
    "recovery": {"name": "Medical Recovery", "icon": "🩹", "cmd": "`!recovery`", "desc": "Heal from Infection, Blood Loss, or Amputation surgery."},
    "sanity": {"name": "Sanity Care", "icon": "🚬", "cmd": "`!sanity`", "desc": "Lower Insanity Levels through rest or nice meals."}
}

def find_activity_key(search_term):
    search_term = search_term.lower().strip()
    # Handle replacing spaces with underscores for direct key match
    alt_search = search_term.replace(" ", "_")
    for k, v in DOWNTIME_ACTIVITIES.items():
        if k == alt_search or v['name'].lower() == search_term:
            return k
    return None

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} - D&Z Survival Bot is Active!")

@bot.command()
async def assign(ctx, *, char_name: str):
    """Assign a character to yourself."""
    path, data = get_character_file(char_name)
    if not data:
        await ctx.send(f"❌ Could not find a character named '{char_name}' in the latest directory.")
        return
    
    user_assignments[str(ctx.author.id)] = data["character"]["name"]
    save_json(ASSIGNMENTS_FILE, user_assignments)
    await ctx.send(f"✅ Successfully assigned **{data['character']['name']}** to {ctx.author.mention}!")

@bot.command()
async def unassign(ctx):
    """Unassign your current character."""
    user_id = str(ctx.author.id)
    if user_id in user_assignments:
        char_name = user_assignments.pop(user_id)
        save_json(ASSIGNMENTS_FILE, user_assignments)
        await ctx.send(f"✅ Successfully unassigned **{char_name}**. You are no longer tracking a character.")
    else:
        await ctx.send("❌ You don't currently have a character assigned.")

@bot.command()
async def force_assign(ctx, member: discord.Member, *, char_name: str):
    """(GM only) Assign a character to a specific user."""
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ You must be an Administrator to use this command.")
        return

    path, data = get_character_file(char_name)
    if not data:
        await ctx.send(f"❌ Could not find a character named '{char_name}' in the latest directory.")
        return
    
    user_assignments[str(member.id)] = data["character"]["name"]
    save_json(ASSIGNMENTS_FILE, user_assignments)
    await ctx.send(f"✅ Successfully assigned **{data['character']['name']}** to {member.mention}!")

@bot.command()
async def disable(ctx, *, activity_name: str):
    """(GM only) Disable a specific activity."""
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ You must be an Administrator to use this command.")
        return

    found_key = find_activity_key(activity_name)
    if not found_key:
        await ctx.send(f"❌ Could not find activity '{activity_name}'. Type `!activities` to see valid names.")
        return
        
    if found_key in disabled_activities:
        await ctx.send(f"⚠️ **{DOWNTIME_ACTIVITIES[found_key]['name']}** is already disabled.")
    else:
        disabled_activities.append(found_key)
        save_json(DISABLED_ACTIVITIES_FILE, disabled_activities)
        await ctx.send(f"🔒 **{DOWNTIME_ACTIVITIES[found_key]['name']}** has been DISABLED.")

@bot.command()
async def enable(ctx, *, activity_name: str):
    """(GM only) Enable a specific activity."""
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ You must be an Administrator to use this command.")
        return

    found_key = find_activity_key(activity_name)
    if not found_key:
        await ctx.send(f"❌ Could not find activity '{activity_name}'. Type `!activities` to see valid names.")
        return
        
    if found_key in disabled_activities:
        disabled_activities.remove(found_key)
        save_json(DISABLED_ACTIVITIES_FILE, disabled_activities)
        await ctx.send(f"🔓 **{DOWNTIME_ACTIVITIES[found_key]['name']}** has been ENABLED!")
    else:
        await ctx.send(f"⚠️ **{DOWNTIME_ACTIVITIES[found_key]['name']}** is already enabled.")

@bot.command()
async def mystats(ctx):
    """View your assigned character's stats."""
    path, data = get_assigned_character(ctx.author.id)
    if not data:
        await ctx.send("❌ You don't have an assigned character or it could not be found. Use `!assign <name>`.")
        return
    await send_character_embed(ctx, data)

@bot.command()
async def show_char(ctx, *, char_name: str):
    """View a specific character's stats."""
    path, data = get_character_file(char_name)
    if not data:
        await ctx.send(f"❌ Could not find a character named '{char_name}'.")
        return
    await send_character_embed(ctx, data)

async def send_character_embed(ctx, data):
    c = data["character"]
    embed = discord.Embed(title=f"👤 {c['name']} (Level {c['level']} {c['background']})", color=0x2ecc71)
    
    stats_str = f"STR {c['stats']['str']} | DEX {c['stats']['dex']} | CON {c['stats']['con']} | INT {c['stats']['int']} | WIS {c['stats']['wis']} | CHA {c['stats']['cha']}"
    embed.add_field(name="Attributes", value=stats_str, inline=False)
    
    vitals = f"❤️ HP: {c['hp']}/{c['maxHp']}\n🩸 Blood: {c['blood']}/{c['maxBlood']}\n🧠 Insanity: {c['insanity']}"
    embed.add_field(name="Vitals", value=vitals, inline=True)
    
    supplies = f"🥫 Rations: {c['rations']}/{c.get('maxRations', 7)}\n💧 Water: {c['water']}/{c.get('maxWater', 14)}"
    embed.add_field(name="Supplies", value=supplies, inline=True)
    
    weapons = []
    for w in c.get('weapons', []):
        weapons.append(f"{w.get('icon', '⚔️')} {w.get('name')} ({w.get('damage')} {w.get('damageType')})")
    
    if weapons:
        embed.add_field(name="Active Weapons", value="\n".join(weapons), inline=False)
    
    await ctx.send(embed=embed)

@bot.command()
async def all_chars(ctx):
    """List all available characters in the latest folder."""
    latest_folder = get_latest_folder()
    if not latest_folder:
        await ctx.send("❌ No character folders found.")
        return
    
    chars = []
    for file in os.listdir(latest_folder):
        if file.endswith('.json'):
            data = load_json(os.path.join(latest_folder, file), None)
            if data and "character" in data:
                chars.append(data["character"]["name"])
    
    if not chars:
        await ctx.send("❌ No characters found in the latest folder.")
        return
    
    embed = discord.Embed(title=f"📋 Available Characters ({os.path.basename(latest_folder)})", description="\n".join(chars), color=0x3498db)
    await ctx.send(embed=embed)

@bot.command()
async def upload_char(ctx):
    """Upload a character JSON file to update or add them to the latest folder."""
    if not ctx.message.attachments:
        await ctx.send("❌ You must attach a JSON file to this command.")
        return
    
    latest_folder = get_latest_folder()
    if not latest_folder:
        latest_folder = os.path.join(PLAYER_CHARS_DIR, datetime.now().strftime("%m-%d-%Y.%I-%M%p").lower())
        os.makedirs(latest_folder, exist_ok=True)
        
    for attachment in ctx.message.attachments:
        if attachment.filename.endswith(".json"):
            path = os.path.join(latest_folder, attachment.filename)
            await attachment.save(path)
            await ctx.send(f"✅ Successfully uploaded `{attachment.filename}` to `{os.path.basename(latest_folder)}`.")
        else:
            await ctx.send(f"⚠️ Ignored `{attachment.filename}` (not a JSON file).")

@bot.command()
async def download_char(ctx, *, char_name: str = None):
    """Download a character JSON file (defaults to your assigned character)."""
    if char_name:
        path, data = get_character_file(char_name)
        if not path:
            await ctx.send(f"❌ Could not find a character named '{char_name}'.")
            return
    else:
        path, data = get_assigned_character(ctx.author.id)
        if not path:
            await ctx.send("❌ You don't have an assigned character. Use `!download_char <name>` or `!assign <name>` first.")
            return

    try:
        file = discord.File(path)
        await ctx.send(f"📁 Here is the latest JSON file for **{data['character']['name']}**:", file=file)
    except Exception as e:
        await ctx.send(f"❌ Error uploading file: {e}")

@bot.command()
async def activities(ctx):
    """List all available D&Z survival activities."""
    embed = discord.Embed(
        title="🧟 D&Z Survival Activities",
        description="Choose a task to spend your campaign downtime. Report results to your GM!",
        color=0xf39c12 # Amber color
    )
    for key, act in DOWNTIME_ACTIVITIES.items():
        status = " 🔒 `[DISABLED]`" if key in disabled_activities else ""
        embed.add_field(name=f"{act['icon']} {act['name']}{status} - {act.get('cmd', '')}", value=act['desc'], inline=False)
    await ctx.send(embed=embed)

@bot.command()
async def downtime(ctx):
    """Alias for activities."""
    await activities(ctx)

@bot.command()
async def ping(ctx):
    """Check if the bot is alive."""
    await ctx.send("Pong! 🐺 The wasteland is still standing.")

@bot.command()
async def rollout(ctx):
    """Roll a standard d20 for survival checks."""
    roll = random.randint(1, 20)
    msg = f"🎲 **Survival Check**: {roll}"
    if roll == 20: msg += " - **CRITICAL SUCCESS!** 🏆"
    elif roll == 1: msg += " - **CRITICAL FAILURE!** 💀"
    await ctx.send(msg)

@bot.command()
async def scavenge(ctx, zone="safe"):
    """Quickly roll for scavenging results (safe or urban) and apply to your character."""
    zone = zone.lower()
    if zone == "urban":
        if await is_activity_disabled("scavenge_urban", ctx): return
    else:
        if await is_activity_disabled("scavenge_safe", ctx): return

    if not await check_and_consume_cooldown(ctx):
        return

    items = []
    danger_roll = 0
    if zone == "urban":
        pool = ["Firearms", "Ammo", "Medical Supplies", "Rare Scrap", "Fuel"]
        found = random.choice(pool)
        danger_roll = random.randint(1, 20)
    else:
        pool = ["1d4 Rations", "Clean Water", "Basic Scrap", "Cloth", "Duct Tape"]
        found = random.choice(pool)

    char_path, char_data = get_assigned_character(ctx.author.id)
    char_update_msg = ""
    
    if char_data:
        c = char_data["character"]
        if found == "1d4 Rations":
            amount = random.randint(1, 4)
            c["rations"] = min(c.get("rations", 0) + amount, c.get("maxRations", 7))
            char_update_msg = f"\n✅ Added **{amount} Rations** to {c['name']}! (Total: {c['rations']}/{c.get('maxRations', 7)})"
            found_display = f"{amount} Rations"
        elif found == "Clean Water":
            c["water"] = min(c.get("water", 0) + 1, c.get("maxWater", 14))
            char_update_msg = f"\n✅ Added **1 Water** to {c['name']}! (Total: {c['water']}/{c.get('maxWater', 14)})"
            found_display = "Clean Water"
        else:
            found_display = found
            inv = c.get("inventory", [])
            empty_idx = next((i for i, slot in enumerate(inv) if slot is None), -1)
            
            if empty_idx != -1:
                inv[empty_idx] = {"name": found, "qty": 1, "icon": "📦", "tp": 0, "category": "loot"}
                char_update_msg = f"\n🎒 Added **{found}** to {c['name']}'s inventory."
            else:
                char_update_msg = f"\n🎒 **{c['name']}'s inventory is FULL!** Had to leave the **{found}** behind."
        save_json(char_path, char_data)
    else:
        found_display = f"{random.randint(1, 4)} Rations" if found == "1d4 Rations" else found
        char_update_msg = "\n*(Use `!assign <character>` to automatically add loot to your inventory!)*"

    if zone == "urban":
        msg = f"🏙️ **Urban Expedition Results**: {ctx.author.mention} found **{found_display}**! "
        if danger_roll > 15:
            msg += "\n⚠️ *Warning: You were spotted by a horde! GM roll for combat!*"
    else:
        msg = f"🔦 **Safe Scavenge Results**: {ctx.author.mention} found **{found_display}**."
        
    await ctx.send(msg + char_update_msg)

@bot.command()
async def recovery(ctx):
    """Use Medical Supplies to restore your HP and Blood."""
    if await is_activity_disabled("recovery", ctx): return

    char_path, char_data = get_assigned_character(ctx.author.id)
    if not char_data:
        await ctx.send("❌ You need an assigned character to perform recovery. Use `!assign <name>`.")
        return

    c = char_data["character"]
    inv = c.get("inventory", [])
    med_idx = next((i for i, item in enumerate(inv) if item and item.get("name") == "Medical Supplies"), -1)

    if med_idx == -1:
        await ctx.send(f"❌ {ctx.author.mention}, you don't have any **Medical Supplies** in your inventory to perform a recovery!")
        return

    if not await check_and_consume_cooldown(ctx):
        return

    # Consume the medical supplies
    inv[med_idx] = None
    c["inventory"] = inv
    
    # Restore vitals
    c["hp"] = c.get("maxHp", c["hp"])
    c["blood"] = c.get("maxBlood", c["blood"])
    
    save_json(char_path, char_data)
    await ctx.send(f"🩹 **Medical Recovery**: {ctx.author.mention} used **Medical Supplies**. {c['name']} has fully restored their HP ({c['hp']}) and Blood ({c['blood']})!")

@bot.command()
async def sanity(ctx):
    """Eat a Ration to lower your Insanity by 1."""
    if await is_activity_disabled("sanity", ctx): return

    char_path, char_data = get_assigned_character(ctx.author.id)
    if not char_data:
        await ctx.send("❌ You need an assigned character to care for your sanity. Use `!assign <name>`.")
        return

    c = char_data["character"]
    if c.get("rations", 0) < 1:
        await ctx.send(f"❌ {ctx.author.mention}, you don't have any **Rations** to eat to care for your sanity!")
        return

    if not await check_and_consume_cooldown(ctx):
        return

    # Consume a ration and lower insanity
    c["rations"] -= 1
    old_insanity = c.get("insanity", 0)
    c["insanity"] = max(0, old_insanity - 1)
    
    save_json(char_path, char_data)
    await ctx.send(f"🚬 **Sanity Care**: {ctx.author.mention} ate a nice meal (1 Ration). {c['name']}'s Insanity dropped from **{old_insanity}** to **{c['insanity']}**!")

@bot.command()
async def fortify(ctx):
    """Use Basic Scrap to fortify your base."""
    if await is_activity_disabled("fortify", ctx): return

    char_path, char_data = get_assigned_character(ctx.author.id)
    if not char_data:
        await ctx.send("❌ You need an assigned character to fortify the base. Use `!assign <name>`.")
        return

    c = char_data["character"]
    inv = c.get("inventory", [])
    scrap_idx = next((i for i, item in enumerate(inv) if item and item.get("name") in ["Basic Scrap", "Rare Scrap"]), -1)

    if scrap_idx == -1:
        await ctx.send(f"❌ {ctx.author.mention}, you don't have any **Scrap** in your inventory to fortify the base!")
        return

    if not await check_and_consume_cooldown(ctx):
        return

    # Consume the scrap
    scrap_name = inv[scrap_idx]["name"]
    inv[scrap_idx] = None
    c["inventory"] = inv
    
    save_json(char_path, char_data)
    await ctx.send(f"🔨 **Fortifying Base**: {ctx.author.mention} spent **{scrap_name}** to upgrade the base defenses! Report to your GM.")

@bot.command()
async def activity(ctx, *, activity_name: str):
    """Generic command for other downtime activities (e.g. !activity taming)."""
    found_key = find_activity_key(activity_name)
    if not found_key:
        await ctx.send(f"❌ Unknown activity '{activity_name}'. Use `!activities` to see valid options.")
        return

    if await is_activity_disabled(found_key, ctx): return

    if not await check_and_consume_cooldown(ctx):
        return

    roll = random.randint(1, 20)
    msg = f"🛠️ **Downtime Activity**: {ctx.author.mention} spent their downtime action working on **{DOWNTIME_ACTIVITIES[found_key]['name']}**.\n"
    msg += f"🎲 **Survival Check**: {roll}"
    if roll == 20: msg += " - **CRITICAL SUCCESS!** 🏆"
    elif roll == 1: msg += " - **CRITICAL FAILURE!** 💀"
    
    await ctx.send(msg + "\n*(GM, please resolve the results of this check!)*")

@bot.command()
async def instructions(ctx):
    """Show instructions for players on how to use the bot."""
    embed = discord.Embed(
        title="📚 D&Z Player Instructions",
        description="Welcome to the wasteland! Here is how to use the survival bot to track your character and downtime.",
        color=0x3498db
    )
    
    embed.add_field(name="1. Claim Your Character", value="Type `!assign <Character Name>` to link your Discord account to your character sheet.", inline=False)
    embed.add_field(name="2. View Your Stats", value="Type `!mystats` at any time to check your HP, Blood, Insanity, Rations, Water, and Weapons.", inline=False)
    embed.add_field(name="3. Go Scavenging", value="Type `!scavenge` (safe) or `!scavenge urban` (dangerous). The bot will roll for loot and automatically add it to your inventory!", inline=False)
    embed.add_field(name="4. Health & Sanity", value="Type `!recovery` to consume Medical Supplies and fully heal. Type `!sanity` to consume a Ration and lower your Insanity by 1.", inline=False)
    embed.add_field(name="5. Base Building", value="Type `!fortify` to consume Scrap and upgrade your base.", inline=False)
    embed.add_field(name="6. Other Activities", value="For anything else (like Traps or Taming), type `!activity <name>` (e.g. `!activity taming`). The bot will roll your check for the GM!", inline=False)

    embed.set_footer(text="Survival isn't a right, it's a privilege. Good luck out there.")
    await ctx.send(embed=embed)

bot.run(TOKEN)
