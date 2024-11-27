import discord
import itg_cli
import logging
import os
from dataclasses import dataclass
from simfile.dir import SimfilePack
from simfile.types import Simfile
from discord.ext import commands
from discord import app_commands
from pathlib import Path
from typing import Optional, Self


class ItgCliCogConfigError(Exception):
    pass


@dataclass
class ItgCliCogConfig:
    """Config Options for ItgCliCog"""

    packs: Path
    courses: Path
    singles: Path
    cache: Optional[Path]
    add_song_channel_id: Optional[int]

    def from_env() -> Optional[Self]:
        logger = logging.getLogger(__class__.__name__)
        env_bindings = {
            key: os.getenv(key)
            for key in [
                "PACKS_PATH",
                "COURSES_PATH",
                "SINGLES_FOLDER_NAME",
                "ITGMANIA_CACHE_PATH",
                "ADD_SONG_CHANNEL_ID",
            ]
        }
        missing = [key for key, val in env_bindings.items() if not val]
        for key in missing:
            logger.warning(
                f"Missing necessary environment variable for ItgCliCog: {key}"
            )
        if len(missing) > 0:
            raise ItgCliCogConfigError("Missing keys.")

        return ItgCliCogConfig(
            Path(env_bindings["PACKS_PATH"]),
            Path(env_bindings["COURSES_PATH"]),
            env_bindings["SINGLES_FOLDER_NAME"],
            Path(env_bindings["ITGMANIA_CACHE_PATH"]),
            env_bindings["ADD_SONG_CHANNEL_ID"],
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
        # Define overwrite handler for add_pack
        # TODO: make this more pretty with buttons and stuff
        # Maybe genericize it for both add_song and add_pack?
        # Will need to handle arg type differences
        def overwrite_handler(_new: SimfilePack, _old: SimfilePack) -> bool:
            inter.response.send_message("Pack already exists. Aborting.")
            return False

        # Run add_pack and handle exceptions accordingly
        try:
            pack, num_courses = itg_cli.add_pack(
                link,
                self.config.packs,
                self.config.courses,
                overwrite=overwrite_handler,
                delete_macos_files_flag=True,
            )
        except itg_cli.OverwriteException:
            return
        except Exception as e:
            # TODO: maybe convert this into an exception handler for the cog?
            inter.response.send_message(
                f"add_pack threw an exception: `{type(e)}`\n`{e.args}`"
            )
            return

        # Send result message on success
        inter.response.send_message(
            f"Added {pack.name} with {num_courses} course(s)."
        )

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
        # Define overwrite handler for add_song
        # TODO: make this more pretty with buttons and stuff
        # Maybe genericize it for both add_song and add_pack?
        # Will need to handle arg type differences
        async def overwrite_handler(
            _new: tuple[Simfile, str], _old: tuple[Simfile, str]
        ) -> bool:
            await self.inter_or_msg_reply(
                inter_or_msg, "Song already exists. Aborting."
            )
            return False

        # Run add_song and handle exceptions accordingly
        try:
            sm, _ = itg_cli.add_song(
                link,
                self.config.singles,
                self.config.cache,
                overwrite=overwrite_handler,
                delete_macos_files_flag=True,
            )
        except itg_cli.OverwriteException:
            return
        except Exception as e:
            # TODO: maybe convert this into an exception handler for the cog?
            await self.inter_or_msg_reply(
                inter_or_msg,
                f"add_song threw an exception: `{type(e)}`\n`{e.args}`",
            )
            return

        # Send result message on success
        await self.inter_or_msg_reply(
            inter_or_msg, f"Added {sm.title} to Berkeley Test Bench."
        )

    async def inter_or_msg_reply(
        self,
        inter_or_msg: discord.Interaction | discord.Message,
        content: str,
        inter_response_kwargs: dict = {},
        msg_reply_kwargs: dict = {},
    ):
        if isinstance(inter_or_msg, discord.Interaction):
            await inter_or_msg.response.send_message(
                content, **inter_response_kwargs
            )
        elif isinstance(inter_or_msg, discord.Message):
            await inter_or_msg.reply(content, **msg_reply_kwargs)
        else:
            raise ValueError("inter_or_msg is not Interaction or Message")
