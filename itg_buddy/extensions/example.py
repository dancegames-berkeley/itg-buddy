import logging
import discord
from discord.ext import commands
from discord import app_commands
from typing import Literal, Optional


class ExampleCog(commands.Cog):
    logger: logging.Logger
    bot: commands.Bot

    def __init__(self, bot: commands.Bot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(
            f"{bot.__class__.__name__}.{self.__class__.__name__}"
        )
        self.bot = bot

    @app_commands.command(
        name="ping",
        description="Responds with pong and the latency of the bot.",
    )
    async def ping(self, inter: discord.Interaction) -> None:
        latency = round(inter.client.latency * 1000)
        await inter.response.send_message(f"pong! `{latency}ms`")
        self.logger.info(f"ping: Sent pong ({latency}ms)")

    # Adapted from discord.py devpost
    # https://about.abstractumbra.dev/discord.py/2023/01/29/sync-command-example.html
    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def sync(
        self,
        ctx: commands.Context,
        guilds: commands.Greedy[discord.Object],
        spec: Optional[Literal["~", "*", "^"]] = None,
    ) -> None:
        if not guilds:
            if spec == "~":
                synced = await ctx.bot.tree.sync(guild=ctx.guild)
            elif spec == "*":
                ctx.bot.tree.copy_global_to(guild=ctx.guild)
                synced = await ctx.bot.tree.sync(guild=ctx.guild)
            elif spec == "^":
                ctx.bot.tree.clear_commands(guild=ctx.guild)
                await ctx.bot.tree.sync(guild=ctx.guild)
                synced = []
            else:
                synced = await ctx.bot.tree.sync()

            scope = "globally" if spec is None else "to the current guild."
            msg = f"Synced {len(synced)} commands {scope}"
            await ctx.send(msg)
            self.logger.info(msg)

            return

        ret = 0
        for guild in guilds:
            try:
                await ctx.bot.tree.sync(guild=guild)
            except discord.HTTPException:
                pass
            else:
                ret += 1

        await ctx.send(f"Synced the tree to {ret}/{len(guilds)}.")
