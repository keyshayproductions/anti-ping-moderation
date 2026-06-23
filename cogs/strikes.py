import json
import discord
from discord.ext import commands
from datetime import timedelta

DATA_PATH = "data/guilds.json"

STRIKE_ROLE_NAMES = ["Strike 1", "Strike 2", "Strike 3"]


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
            "protected_roles": [],
            "allowed_roles": [],
            "punishment": "timeout",
            "timeout_minutes": 60,
            "strike_roles": {}
        }
    return data[gid]


async def ensure_bot_role(guild: discord.Guild, bot):
    role = discord.utils.get(guild.roles, name="Anti-Ping & Moderation")
    if not role:
        role = await guild.create_role(
            name="Anti-Ping & Moderation",
            color=discord.Color(0x3498db),
            reason="Anti Ping bot setup"
        )
    me = guild.get_member(bot.user.id)
    if me and role not in me.roles:
        await me.add_roles(role)


async def ensure_strike_roles(guild: discord.Guild):
    data = load_data()
    cfg = get_guild_config(data, guild.id)
    changed = False

    for i, name in enumerate(STRIKE_ROLE_NAMES, start=1):
        key = str(i)
        existing_id = cfg["strike_roles"].get(key)
        role = guild.get_role(existing_id) if existing_id else None

        if not role:
            role = discord.utils.get(guild.roles, name=name)
        if not role:
            role = await guild.create_role(name=name, reason="Anti Ping setup")
            changed = True

        cfg["strike_roles"][key] = role.id

    if changed or str(guild.id) not in load_data():
        data[str(guild.id)] = cfg
        save_data(data)

    return cfg["strike_roles"]


async def apply_strike(member: discord.Member, guild: discord.Guild, moderator: discord.Member = None):
    data = load_data()
    cfg = get_guild_config(data, guild.id)
    strike_roles = cfg["strike_roles"]

    # Determine current strike count
    current = 0
    for i in range(3, 0, -1):
        role_id = strike_roles.get(str(i))
        if role_id and discord.utils.get(member.roles, id=role_id):
            current = i
            break

    new_strike = min(current + 1, 3)

    # Remove old strike roles, add new one
    for i in range(1, 4):
        role_id = strike_roles.get(str(i))
        if role_id:
            role = guild.get_role(role_id)
            if role and role in member.roles:
                await member.remove_roles(role)

    new_role_id = strike_roles.get(str(new_strike))
    if new_role_id:
        new_role = guild.get_role(new_role_id)
        if new_role:
            await member.add_roles(new_role)

    save_data(data)

    # Apply punishment on strike 3
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
            await ensure_strike_roles(guild)
            await ensure_bot_role(guild, self.bot)

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        await ensure_bot_role(guild, self.bot)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return

        data = load_data()
        cfg = get_guild_config(data, message.guild.id)

        protected = cfg.get("protected_roles", [])
        allowed = cfg.get("allowed_roles", [])

        if not protected:
            return

        # Check if author has an allowed role
        author_role_ids = [r.id for r in message.author.roles]
        if any(rid in author_role_ids for rid in allowed):
            return

        # Check if any mentioned role is protected
        mentioned_role_ids = [r.id for r in message.role_mentions]
        # Also check user pings — if the user has a protected role
        mentioned_user_role_ids = []
        for user in message.mentions:
            member = message.guild.get_member(user.id)
            if member:
                mentioned_user_role_ids.extend(r.id for r in member.roles)

        pinged_protected = any(rid in protected for rid in mentioned_role_ids + mentioned_user_role_ids)

        if pinged_protected:
            strike = await apply_strike(message.author, message.guild)
            try:
                await message.delete()
            except:
                pass
            await message.channel.send(
                f"{message.author.mention} You are not allowed to ping that role. "
                f"You have received **Strike {strike}**.",
                delete_after=8
            )

    @discord.app_commands.command(name="warn", description="Give a member a strike.")
    @discord.app_commands.default_permissions(manage_messages=True)
    async def warn(self, interaction: discord.Interaction, member: discord.Member):
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

        for i in range(1, 4):
            role_id = strike_roles.get(str(i))
            if role_id:
                role = interaction.guild.get_role(role_id)
                if role and role in member.roles:
                    await member.remove_roles(role)

        await interaction.response.send_message(f"Cleared all strikes for {member.mention}.")


async def setup(bot):
    await bot.add_cog(StrikesCog(bot))
