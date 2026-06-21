import asyncio
import discord
from discord.ext import commands
import config

COGS = [
    "cogs.strikes",
    "cogs.dashboard",
]


async def main():
    intents = discord.Intents.default()
    intents.guilds = True
    intents.members = True
    intents.message_content = True

    bot = commands.Bot(command_prefix="!", intents=intents)

    @bot.event
    async def on_ready():
        await bot.tree.sync()
        print(f"✅ Logged in as {bot.user}")

    for cog in COGS:
        await bot.load_extension(cog)

    await bot.start(config.TOKEN)


asyncio.run(main())
