import logging
import discord
from extensions.example import ExampleCog
from discord.ext import commands


class ItgBuddy(commands.Bot):
    logger: logging.Logger

    def __init__(self, *args, **kwargs):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guild_messages = True
        super().__init__(
            *args,
            **kwargs,
            intents=intents,
            command_prefix=commands.when_mentioned,
        )
        self.logger = logging.getLogger(self.__class__.__name__)

    async def setup_hook(self):
        # TODO: make this automatically pull all the files in extensions
        await self.add_cog(ExampleCog(self))
        self.logger.info("Loaded ExampleCog")

    async def on_ready(self) -> None:
        self.logger.info(f"Logged in as {self.user} ({self.user.id})")
