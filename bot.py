import asyncio
import ssl
import aiohttp
import discord
from discord.ext import commands
import config

COGS = [
    "cogs.strikes",
    "cogs.dashboard",
]


async def main():
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    connector = aiohttp.TCPConnector(ssl=ssl_context)

    intents = discord.Intents.default()
    intents.guilds = True
    intents.members = True
    intents.message_content = True

    bot = commands.Bot(command_prefix="!", intents=intents, connector=connector)

    @bot.event
    async def on_ready():
        await bot.tree.sync()
        print(f"✅ Logged in as {bot.user}")

    for cog in COGS:
        await bot.load_extension(cog)

    await bot.start(config.TOKEN)


asyncio.run(main())
