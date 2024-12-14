import asyncio
import discord
import itg_cli
import logging
from discord.ext import commands
from discord import app_commands

from itg_buddy.extensions.itg_cli.config import ItgCliCogConfig
from itg_buddy.extensions.itg_cli.embeds import (
    add_pack_success,
    add_song_success,
    cancelled_embed,
    error_embed,
)
from itg_buddy.extensions.itg_cli.overwrite import (
    get_add_pack_overwrite_handler,
    get_add_song_overwrite_handler,
)
from itg_buddy.extensions.itg_cli.utils import edit_response
from itg_buddy.extensions.itg_cli.wrappers import (
    add_pack_async,
    add_song_async,
)


class ItgCliCog(commands.Cog):
    bot: commands.Bot
    logger: logging.Logger
    config: ItgCliCogConfig

    def __init__(
        self,
        bot: commands.Bot,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.bot = bot
        self.config = ItgCliCogConfig.from_env()
        self.logger = self.logger = logging.getLogger(
            f"{bot.__class__.__name__}.{self.__class__.__name__}"
        )

    @app_commands.command(description="Add a pack to the machine.")
    @app_commands.describe(link="Link to the pack to add")
    async def add_pack(
        self,
        inter: discord.Interaction,
        link: str,
    ):
        # Start by deferring the interaction
        await inter.response.defer(thinking=True)

        # Run add_pack and handle exceptions accordingly
        try:
            pack, _num_courses = await add_pack_async(
                link,
                self.config.packs,
                self.config.courses,
                inter,
                overwrite=get_add_pack_overwrite_handler(
                    inter, asyncio.get_running_loop()
                ),
                delete_macos_files_flag=True,
            )
        except itg_cli.OverwriteException:
            await inter.edit_original_response(
                embed=cancelled_embed(), view=None
            )
            return
        except Exception as e:
            self.logger.exception(f"add_song threw an exception")
            await inter.edit_original_response(embed=error_embed(e), view=None)
            return

        # Send result message on success
        embed, file = add_pack_success(pack, inter.user)
        await inter.delete_original_response()
        await inter.channel.send(embed=embed, file=file)

    @app_commands.command(description="Add a song to Berkeley Test Bench.")
    @app_commands.describe(link="Link to the song to add")
    async def add_song(
        self,
        inter: discord.Interaction,
        link: str,
    ):
        await self._add_song_helper(inter, link)

    @commands.Cog.listener()
    async def on_message(self, msg: discord.Message) -> None:
        if msg.channel.id != self.config.add_song_channel_id:
            return
        zips = filter(
            lambda a: a.content_type == "application/zip", msg.attachments
        )
        for zip in zips:
            await self._add_song_helper(msg, zip.url)

    async def _add_song_helper(
        self, inter_or_msg: discord.Interaction | discord.Message, link: str
    ):
        # Store the user of the original message and send "thinking" message
        if isinstance(inter_or_msg, discord.Interaction):
            user = inter_or_msg.user
            await inter_or_msg.response.defer(thinking=True)
        elif isinstance(inter_or_msg, discord.Message):
            user = inter_or_msg.author
            inter_or_msg = await inter_or_msg.reply("Processing command...")

        # Run add_song and handle exceptions accordingly
        try:
            sf, path = await add_song_async(
                link,
                self.config.singles,
                inter_or_msg,
                cache=self.config.cache,
                overwrite=get_add_song_overwrite_handler(
                    inter_or_msg, user, asyncio.get_running_loop()
                ),
                delete_macos_files_flag=True,
            )
        except itg_cli.OverwriteException:
            await edit_response(
                inter_or_msg, embed=cancelled_embed(), view=None
            )
            return
        except Exception as e:
            self.logger.exception(f"add_song threw an exception")
            await edit_response(
                inter_or_msg,
                embed=error_embed(e),
            )
            return

        embed, file = add_song_success(sf, path, inter_or_msg.user)
        channel = inter_or_msg.channel
        # Delete progress message and send success message
        if isinstance(inter_or_msg, discord.Interaction):
            await inter_or_msg.delete_original_response()
            await inter_or_msg.channel.send(embed=embed, file=file)
        elif isinstance(inter_or_msg, discord.Message):
            await inter_or_msg.delete()
            await channel.send(embed=embed, file=file)