import discord
from discord.ext import commands
from discord import app_commands
import os
from dotenv import load_dotenv
import json
from datetime import datetime, timezone

load_dotenv()
from flask import Flask
from threading import Thread

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

Thread(target=run_flask, daemon=True).start()



TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))

CONFIG_FILE = "rep_config.json"
POINTS_FILE = "points_data.json"

# ── Config helpers ──────────────────────────────────────────────────────────

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ── Points data helpers ─────────────────────────────────────────────────────

def load_points():
    if os.path.exists(POINTS_FILE):
        with open(POINTS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_points(data):
    with open(POINTS_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_user_data(points_data: dict, user_id: int) -> dict:
    key = str(user_id)
    if key not in points_data:
        points_data[key] = {"messages": 0}
    return points_data[key]

config = load_config()
points_data = load_points()

# ── Rep keywords ────────────────────────────────────────────────────────────

REP_KEYWORDS = [
    "discord.gg/snoopys",
    ".gg/snoopys",
    "gg/snoopys",
    "/snoopys",
    "snoopys"
]

# ── Bot setup ───────────────────────────────────────────────────────────────

intents = discord.Intents.default()
intents.members = True
intents.presences = True
intents.guilds = True
intents.message_content = True
intents.messages = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

repped_members: set = set()

# ── Helpers ─────────────────────────────────────────────────────────────────

def get_custom_status(member: discord.Member) -> str:
    for activity in member.activities:
        if isinstance(activity, discord.CustomActivity):
            return activity.name or ""
    return ""

def has_rep_keyword(status: str) -> bool:
    if not status:
        return False
    return any(kw in status.lower() for kw in REP_KEYWORDS)

# ── Events ───────────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    guild = bot.get_guild(GUILD_ID)
    if guild is None:
        print(f"ERROR: Bot is not in guild {GUILD_ID}")
        return
    try:
        synced = await tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f"Synced {len(synced)} command(s) to guild {GUILD_ID}")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
    print(f"Bot ready as {bot.user} | Guild: {guild.name}")

    role_id = config.get("role_id")
    if role_id:
        role = guild.get_role(int(role_id))
        if role:
            for member in guild.members:
                if role in member.roles:
                    repped_members.add(member.id)


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if not message.guild or message.guild.id != GUILD_ID:
        return

    uid = str(message.author.id)
    if uid not in points_data:
        points_data[uid] = {"messages": 0}
    points_data[uid]["messages"] += 1
    save_points(points_data)

    await bot.process_commands(message)


@bot.event
async def on_presence_update(before: discord.Member, after: discord.Member):
    if after.guild.id != GUILD_ID:
        return

    channel_id = config.get("channel_id")
    role_id = config.get("role_id")
    if not channel_id or not role_id:
        return

    before_status = get_custom_status(before)
    after_status = get_custom_status(after)

    now_repping = has_rep_keyword(after_status)
    was_repping = has_rep_keyword(before_status)

    guild = after.guild
    role = guild.get_role(int(role_id))
    channel = guild.get_channel(int(channel_id))

    if role is None or channel is None:
        return

    if now_repping and not was_repping and after.id not in repped_members:
        repped_members.add(after.id)

        try:
            await after.add_roles(role, reason="Repping snoopys in status")
        except discord.Forbidden:
            print(f"Missing permissions to add role to {after}")
            return

        embed = discord.Embed(
            description=(
                "︶︶ . **thank** you so **mu**ch ! 𓂅  <a:snoopy_kiss:1514019676940664882>\n"
                "<a:snoopy_hearts:1514019575560278149> **>ᴗ<** **__for__** **_repping_** **___snoopy____**"
            ),
            color=0xFFFFFF
        )

        server_icon = guild.icon.url if guild.icon else None
        embed.set_author(name=guild.name, icon_url=server_icon)
        embed.set_footer(text=after.name, icon_url=after.display_avatar.url)
        embed.set_image(url="https://media.discordapp.net/attachments/1515746612503380192/1519036965968936970/image.png?ex=6a3f64ab&is=6a3e132b&hm=fa7b42afac15d4c670105817254e4edd35ef60a9aee00781c97b643586458237&=&format=webp&quality=lossless&width=1730&height=328")

        await channel.send(
            content=f"⠀⠀⠀⠀<:snoopy_heart:1514019425962033272>⠀⠀✎ ⠀{after.mention} ⠀⊹ ⠀<:snoopy_clap:1514019079151685632>",
            embed=embed
        )

    elif not now_repping and was_repping and after.id in repped_members:
        repped_members.discard(after.id)
        try:
            await after.remove_roles(role, reason="Removed snoopys from status")
        except discord.Forbidden:
            print(f"Missing permissions to remove role from {after}")


# ── Commands ─────────────────────────────────────────────────────────────────

@tree.command(
    name="rep",
    description="Set the rep notification channel and role",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(
    channel="Channel to send rep notifications to",
    role="Role to give to users who rep"
)
@app_commands.checks.has_permissions(administrator=True)
async def rep_command(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    role: discord.Role
):
    config["channel_id"] = channel.id
    config["role_id"] = role.id
    save_config(config)
    await interaction.response.send_message(
        f"✅ Rep channel set to {channel.mention} and role set to {role.mention}",
        ephemeral=True
    )


@tree.command(
    name="points",
    description="View points profile of a user",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(user="The user to check points for")
async def points_command(interaction: discord.Interaction, user: discord.Member):
    # Check if invoker has the rep role
    role_id = config.get("role_id")
    if not role_id:
        await interaction.response.send_message(
            "❌ Rep role hasn't been configured yet. Use `/rep` first.",
            ephemeral=True
        )
        return

    rep_role = interaction.guild.get_role(int(role_id))
    if rep_role is None or rep_role not in interaction.user.roles:
        await interaction.response.send_message(
            "❌ You don't have permission to use this command.",
            ephemeral=True
        )
        return

    await interaction.response.defer()

    guild = interaction.guild

    # ── Invite count (exclude invitees with account age < 7 days) ──
    valid_invites = 0
    try:
        invites = await guild.invites()
        now = datetime.now(timezone.utc)
        for inv in invites:
            if inv.inviter and inv.inviter.id == user.id:
                # We can't directly check invitee ages from invite objects,
                # so we count uses but flag new-account joins via on_member_join
                # Here we use stored valid invite count from points_data
                pass
        # Use stored valid_invites from points_data
        uid = str(user.id)
        stored = points_data.get(uid, {})
        valid_invites = stored.get("valid_invites", 0)
    except discord.Forbidden:
        valid_invites = 0

    uid = str(user.id)
    stored = points_data.get(uid, {"messages": 0, "valid_invites": 0})
    message_count = stored.get("messages", 0)

    # ── Build embed ──
    total_points = (message_count * 2) + (valid_invites * 5)

    embed = discord.Embed(
        description=(
            f"<a:snoopy_kiss:1514019676940664882> **__Points Profile__**\n"
            f"\u200b\n"
            f"<:snoopyline:1519660212288749568> Username : - {user.name}\n"
            f"<:snoopyline:1519660212288749568> User ID : - {user.id}\n"
            f"<:snoopyline:1519660212288749568> Invites : - {valid_invites} (+{valid_invites * 5} pts)\n"
            f"<:snoopyline:1519660212288749568> Message : - {message_count} (+{message_count * 2} pts)\n"
            f"<:snoopyline:1519660212288749568> Total Points : - {total_points}\n"
        ),
        color=0xFFFFFF
    )

    server_icon = guild.icon.url if guild.icon else None
    embed.set_author(name=guild.name, icon_url=server_icon)
    embed.set_footer(text=user.name, icon_url=user.display_avatar.url)

    await interaction.followup.send(embed=embed)


# ── Track valid invites on member join ────────────────────────────────────────

@bot.event
async def on_member_join(member: discord.Member):
    if member.guild.id != GUILD_ID:
        return

    # Check account age
    now = datetime.now(timezone.utc)
    account_age_days = (now - member.created_at).days
    if account_age_days < 7:
        return  # Exclude accounts younger than 7 days

    # Find which invite was used by comparing counts before and after
    try:
        invites_after = await member.guild.invites()
    except discord.Forbidden:
        return

    # Compare with cached invites
    cached = invite_cache.get(member.guild.id, [])
    for invite in invites_after:
        for cached_invite in cached:
            if invite.code == cached_invite.code and invite.uses > cached_invite.uses:
                if invite.inviter:
                    uid = str(invite.inviter.id)
                    if uid not in points_data:
                        points_data[uid] = {"messages": 0, "valid_invites": 0}
                    points_data[uid]["valid_invites"] = points_data[uid].get("valid_invites", 0) + 1
                    save_points(points_data)
                break

    # Update cache
    invite_cache[member.guild.id] = invites_after


# Cache invites on ready and when new invite is created
invite_cache: dict = {}

@bot.event
async def on_invite_create(invite: discord.Invite):
    if invite.guild and invite.guild.id == GUILD_ID:
        try:
            invite_cache[invite.guild.id] = await invite.guild.invites()
        except discord.Forbidden:
            pass

@bot.event
async def on_invite_delete(invite: discord.Invite):
    if invite.guild and invite.guild.id == GUILD_ID:
        try:
            invite_cache[invite.guild.id] = await invite.guild.invites()
        except discord.Forbidden:
            pass


# Override on_ready to also cache invites
original_on_ready = bot.event.__func__ if hasattr(bot.event, '__func__') else None

@bot.listen("on_ready")
async def cache_invites_on_ready():
    guild = bot.get_guild(GUILD_ID)
    if guild:
        try:
            invite_cache[guild.id] = await guild.invites()
            print(f"Cached {len(invite_cache[guild.id])} invites")
        except discord.Forbidden:
            print("Missing permission to fetch invites (needs Manage Guild)")



@tree.command(
    name="lb",
    description="Show the points leaderboard",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(type="Leaderboard type")
@app_commands.choices(type=[
    app_commands.Choice(name="points", value="points")
])
async def lb_command(interaction: discord.Interaction, type: str):
    role_id = config.get("role_id")
    if not role_id:
        await interaction.response.send_message(
            "\u274c Rep role hasn't been configured yet. Use `/rep` first.",
            ephemeral=True
        )
        return

    rep_role = interaction.guild.get_role(int(role_id))
    if rep_role is None or rep_role not in interaction.user.roles:
        await interaction.response.send_message(
            "\u274c You don't have permission to use this command.",
            ephemeral=True
        )
        return

    await interaction.response.defer()

    guild = interaction.guild

    leaderboard = []
    for uid, data in points_data.items():
        messages = data.get("messages", 0)
        invites = data.get("valid_invites", 0)
        total = (messages * 2) + (invites * 5)
        if total == 0:
            continue
        member = guild.get_member(int(uid))
        username = member.name if member else f"Unknown ({uid})"
        leaderboard.append((username, total))

    leaderboard.sort(key=lambda x: x[1], reverse=True)
    top = leaderboard[:10]

    if not top:
        lines = "No points data yet."
    else:
        lines = "\n".join(
            f"{i+1}. {name} - {pts}"
            for i, (name, pts) in enumerate(top)
        )

    embed = discord.Embed(
        description=(
            "<a:snoopy_kiss:1514019676940664882> **__Points Leaderboard__**\n"
            "\u200b\n"
            f"{lines}\n"
        ),
        color=0xFFFFFF
    )

    server_icon = guild.icon.url if guild.icon else None
    embed.set_author(name=guild.name, icon_url=server_icon)
    embed.set_footer(text=interaction.user.name, icon_url=interaction.user.display_avatar.url)

    await interaction.followup.send(embed=embed)


bot.run(TOKEN)
