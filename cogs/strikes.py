import json
import discord
from discord.ext import commands
from datetime import timedelta

DATA_PATH = "data/guilds.json"

STRIKE_ROLE_NAMES = ["Strike 1", "Strike 2", "Strike 3"]
STRIKE_COLORS = [discord.Color.yellow(), discord.Color.orange(), discord.Color.red()]
ANTIPING_ROLE_NAME = "AntiPing"
DIVIDER_ROLE_NAME = "─────────────────"


def load_data():
    with open(DATA_PATH, "r") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_PATH, "w") as f:
        json.dump(data, f, indent=2)


def get_guild_config(data, guild_id: int) -> dict:
    gid = str(guild_id)
    if gid not in data:
        data[gid] = {
            "punishment": "timeout",
            "timeout_minutes": 60,
            "strike_roles": {},
            "antiping_role_id": None,
            "allowed_admin_roles": []
        }
    return data[gid]


async def ensure_divider_role(guild: discord.Guild):
    role = discord.utils.get(guild.roles, name=DIVIDER_ROLE_NAME)
    if not role:
        await guild.create_role(
            name=DIVIDER_ROLE_NAME,
            color=discord.Color.darker_gray(),
            reason="Anti Ping divider"
        )


async def ensure_bot_role(guild: discord.Guild, bot):
    role = discord.utils.get(guild.roles, name="Anti-Ping & Moderation")
    if not role:
        role = await guild.create_role(
            name="Anti-Ping & Moderation",
            color=discord.Color(0x555EEA),
            reason="Anti Ping bot setup"
        )
    me = guild.get_member(bot.user.id)
    if me and role not in me.roles:
        await me.add_roles(role)


async def ensure_antiping_role(guild: discord.Guild):
    data = load_data()
    cfg = get_guild_config(data, guild.id)

    role_id = cfg.get("antiping_role_id")
    role = guild.get_role(role_id) if role_id else None

    if not role:
        role = discord.utils.get(guild.roles, name=ANTIPING_ROLE_NAME)
    if not role:
        role = await guild.create_role(
            name=ANTIPING_ROLE_NAME,
            color=discord.Color(0x3498db),
            reason="Anti Ping bot setup"
        )

    cfg["antiping_role_id"] = role.id
    data[str(guild.id)] = cfg
    save_data(data)


async def ensure_strike_roles(guild: discord.Guild):
    data = load_data()
    cfg = get_guild_config(data, guild.id)

    for i, name in enumerate(STRIKE_ROLE_NAMES, start=1):
        key = str(i)
        existing_id = cfg["strike_roles"].get(key)
        role = guild.get_role(existing_id) if existing_id else None

        if not role:
            role = discord.utils.get(guild.roles, name=name)
        if not role:
            role = await guild.create_role(name=name, color=STRIKE_COLORS[i-1], reason="Anti Ping setup")

        cfg["strike_roles"][key] = role.id

    data[str(guild.id)] = cfg
    save_data(data)
    return cfg["strike_roles"]


async def apply_strike(member: discord.Member, guild: discord.Guild, moderator: discord.Member = None):
    data = load_data()
    cfg = get_guild_config(data, guild.id)
    strike_roles = cfg["strike_roles"]

    current = 0
    for i in range(3, 0, -1):
        role_id = strike_roles.get(str(i))
        if role_id and discord.utils.get(member.roles, id=role_id):
            current = i
            break

    new_strike = min(current + 1, 3)

    for i in range(1, 4):
        role_id = strike_roles.get(str(i))
        if role_id:
            role = guild.get_role(role_id)
            if role and role in member.roles:
                try:
                    await member.remove_roles(role)
                except discord.Forbidden:
                    pass

    new_role_id = strike_roles.get(str(new_strike))
    if new_role_id:
        new_role = guild.get_role(new_role_id)
        if new_role:
            try:
                await member.add_roles(new_role)
            except discord.Forbidden:
                pass

    save_data(data)

    if new_strike == 3:
        punishment = cfg.get("punishment", "timeout")
        try:
            if punishment == "timeout":
                mins = cfg.get("timeout_minutes", 60)
                await member.timeout(timedelta(minutes=mins), reason="Strike 3 — Anti Ping")
            elif punishment == "kick":
                await member.kick(reason="Strike 3 — Anti Ping")
            elif punishment == "ban":
                await member.ban(reason="Strike 3 — Anti Ping")
        except discord.Forbidden:
            pass

    return new_strike


class StrikesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            await ensure_divider_role(guild)
            await ensure_bot_role(guild, self.bot)
            await ensure_antiping_role(guild)
            await ensure_strike_roles(guild)

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        await ensure_divider_role(guild)
        await ensure_bot_role(guild, self.bot)
        await ensure_antiping_role(guild)
        await ensure_strike_roles(guild)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return

        data = load_data()
        cfg = get_guild_config(data, message.guild.id)
        antiping_role_id = cfg.get("antiping_role_id")

        if not antiping_role_id:
            return

        antiping_role = message.guild.get_role(antiping_role_id)
        if not antiping_role:
            return

        # Check if anyone mentioned has AntiPing role
        for user in message.mentions:
            member = message.guild.get_member(user.id)
            if member and antiping_role in member.roles:
                strike = await apply_strike(message.author, message.guild)
                try:
                    await message.delete()
                except:
                    pass
                await message.channel.send(
                    f"{message.author.mention} You are not allowed to ping that member. "
                    f"You have received **Strike {strike}**.",
                    delete_after=8
                )
                return

    @discord.app_commands.command(name="warn", description="Give a member a strike.")
    async def warn(self, interaction: discord.Interaction, member: discord.Member):
        data = load_data()
        cfg = get_guild_config(data, interaction.guild.id)
        allowed_roles = cfg.get("allowed_admin_roles", [])

        user_role_ids = [r.id for r in interaction.user.roles]
        has_permission = any(rid in user_role_ids for rid in allowed_roles) or interaction.user.guild_permissions.administrator

        if not has_permission and allowed_roles:
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return

        strike = await apply_strike(member, interaction.guild, moderator=interaction.user)
        await interaction.response.send_message(f"{member.mention} has been warned. They are now on **Strike {strike}**.")

    @discord.app_commands.command(name="strikes", description="Check a member's current strike level.")
    async def check_strikes(self, interaction: discord.Interaction, member: discord.Member):
        data = load_data()
        cfg = get_guild_config(data, interaction.guild.id)
        strike_roles = cfg["strike_roles"]

        current = 0
        for i in range(3, 0, -1):
            role_id = strike_roles.get(str(i))
            if role_id and discord.utils.get(member.roles, id=role_id):
                current = i
                break

        await interaction.response.send_message(
            f"{member.mention} is on **Strike {current}**." if current else f"{member.mention} has no strikes."
        )

    @discord.app_commands.command(name="clearstrikes", description="Clear all strikes from a member.")
    @discord.app_commands.default_permissions(manage_roles=True)
    async def clear_strikes(self, interaction: discord.Interaction, member: discord.Member):
        data = load_data()
        cfg = get_guild_config(data, interaction.guild.id)
        strike_roles = cfg["strike_roles"]

        removed = 0
        for i in range(1, 4):
            role_id = strike_roles.get(str(i))
            if role_id:
                role = interaction.guild.get_role(role_id)
                if role and role in member.roles:
                    try:
                        await member.remove_roles(role)
                        removed += 1
                    except discord.Forbidden:
                        await interaction.response.send_message(f"❌ I don't have permission to remove roles.", ephemeral=True)
                        return

        await interaction.response.send_message(f"✅ Removed {removed} strike(s) from {member.mention}.")


async def setup(bot):
    await bot.add_cog(StrikesCog(bot))
