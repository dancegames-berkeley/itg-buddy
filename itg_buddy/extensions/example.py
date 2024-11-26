import logging
import discord
from discord.ext import commands
from discord import app_commands


class ExampleCog(commands.Cog):
    logger: logging.Logger
    bot: commands.Bot

    def __init__(self, bot: commands.Bot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(
            f"{bot.__class__.__name__}.{self.__class__.__name__}"
        )
        self.bot = bot

    @commands.hybrid_command()
    async def register(
        self, ctx: commands.Context, global_flag: bool = False
    ) -> None:
        """
        Registers slash commands with Discord

        Parameters
        ----------
        ctx: commands.Context
            The context of the command invocation
        global_flag: bool
            Registers commands globally if True, or the current guild if False
        """
        if global_flag:
            await self.bot.tree.sync()
            await ctx.reply(
                "> Registered commands globally.\n"
                + "> Please allow some time for the changes to propgate."
            )
            self.logger.info(f"register: Registered commands globally")
        else:
            await self.bot.tree.sync(guild=ctx.guild)
            await ctx.reply(f"> Registered commands for {ctx.guild.name}.")
            self.logger.info(
                f"register: Registered commands for {ctx.guild.name}."
            )

    @app_commands.command()
    async def ping(self, inter: discord.Interaction) -> None:
        """
        Responds with pong and the latency of the bot.

        Parameters
        ----------
        inter: discord.Interaction
            The slash-command interaction
        """
        latency = round(inter.client.latency * 1000)
        await inter.response.send_message(f"> pong! `{latency}ms`")
        self.logger.info(f"ping: Sent pong ({latency}ms)")
