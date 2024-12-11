import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from io import TextIOBase
import sys
import time
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
from typing import Optional, Self, override


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
            Path(env_bindings["PACKS_PATH"]).joinpath(
                env_bindings["SINGLES_FOLDER_NAME"]
            ),
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
        # Start by deferring the interaction
        await inter.response.defer(thinking=True)

        # Run add_pack and handle exceptions accordingly
        try:
            pack, num_courses = await add_pack_async(
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
            return
        except Exception as e:
            await inter.edit_original_response(
                content=f"add_pack threw an exception: `{type(e)}`\n`{e.args}`"
            )
            return

        # Send result message on success
        await inter.edit_original_response(
            content=f"Added {pack.name} with {num_courses} course(s)."
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
        # Send "thinking" message
        if isinstance(inter_or_msg, discord.Interaction):
            await inter_or_msg.response.defer(thinking=True)
        elif isinstance(inter_or_msg, discord.Message):
            inter_or_msg = await inter_or_msg.reply("Processing command...")

        # Run add_song and handle exceptions accordingly
        try:
            sm, _ = await add_song_async(
                link,
                self.config.singles,
                inter_or_msg,
                cache=self.config.cache,
                overwrite=get_add_song_overwrite_handler(
                    inter_or_msg, asyncio.get_running_loop()
                ),
                delete_macos_files_flag=True,
            )
        except itg_cli.OverwriteException:
            return
        except Exception as e:
            await edit_response(
                inter_or_msg,
                f"add_song threw an exception: `{type(e)}`\n`{e.args}`",
            )
            return

        # Send result message on success
        await edit_response(
            inter_or_msg, f"Added {sm.title} to Berkeley Test Bench."
        )


async def edit_response(
    inter_or_msg: discord.Interaction | discord.Message,
    content: str,
):
    if isinstance(inter_or_msg, discord.Interaction):
        await inter_or_msg.edit_original_response(content=content)
    elif isinstance(inter_or_msg, discord.Message):
        await inter_or_msg.edit(content=content)
    else:
        raise ValueError("inter_or_msg is not Interaction or Message")


# Async Wrappers

# Thread pools for performing add-song and add-pack operations.
# itg-cli wasn't built with concurrency in mind, so max_workers=1 (for now)
ADD_SONG_EXECUTOR = ThreadPoolExecutor(max_workers=1)
ADD_PACK_EXECUTOR = ThreadPoolExecutor(max_workers=1)


def get_add_pack_overwrite_handler(
    inter: discord.Interaction, loop: asyncio.AbstractEventLoop
):
    def overwrite_handler(_new: SimfilePack, _old: SimfilePack) -> bool:
        asyncio.run_coroutine_threadsafe(
            inter.edit_original_response(
                content="Pack already exists. Aborting."
            ),
            loop,
        )
        return False

    return overwrite_handler


def get_add_song_overwrite_handler(
    inter_or_msg: discord.Interaction | discord.Message,
    loop: asyncio.AbstractEventLoop,
):
    def overwrite_handler(
        _new: tuple[Simfile, str], _old: tuple[Simfile, str]
    ) -> bool:
        asyncio.run_coroutine_threadsafe(
            edit_response(inter_or_msg, "Song already exists. Aborting."), loop
        )
        return False

    return overwrite_handler


# Async wrapper around itg_cli.add_song
# Takes an additional argument, bot_response, for posting updates from stderr
async def add_song_async(
    path_or_url: str,
    singles: Path,
    bot_response: discord.Message | discord.Interaction,
    cache: Path | None = None,
    downloads: Path | None = None,
    overwrite=lambda _new, _old: False,
    delete_macos_files_flag: bool = False,
):
    loop = asyncio.get_running_loop()
    with edit_response_with_stderr(bot_response, loop):
        return await loop.run_in_executor(
            ADD_SONG_EXECUTOR,
            lambda: itg_cli.add_song(
                path_or_url,
                singles,
                cache,
                downloads=downloads,
                overwrite=overwrite,
                delete_macos_files_flag=delete_macos_files_flag,
            ),
        )


# Async wrapper around itg_cli.add_pack
# Takes an additional argument, bot_response, for posting updates from stderr
async def add_pack_async(
    path_or_url: str,
    packs: Path,
    courses: Path,
    bot_response: discord.Message | discord.Interaction,
    downloads: Path | None = None,
    overwrite=lambda _new, _old: False,
    delete_macos_files_flag: bool = False,
):
    loop = asyncio.get_running_loop()
    with edit_response_with_stderr(bot_response, loop):
        return await loop.run_in_executor(
            ADD_PACK_EXECUTOR,
            lambda: itg_cli.add_pack(
                path_or_url,
                packs,
                courses,
                downloads=downloads,
                overwrite=overwrite,
                delete_macos_files_flag=delete_macos_files_flag,
            ),
        )


# Stderr redirection stuff
# Progress bars in itg_cli are written to stderr, so we can instead pipe stderr
# updates to a custom handler that regularly updates our bot's responses with
# the current progress.
class ItgCliStdOutHandler(TextIOBase):
    inter_or_msg: discord.Message | discord.Interaction
    last_updated: float
    buffer: str
    loop: asyncio.AbstractEventLoop

    def __init__(
        self,
        inter_or_msg: discord.Message | discord.Interaction,
        loop: asyncio.AbstractEventLoop,
    ):
        super().__init__()
        self.inter_or_msg = inter_or_msg
        self.loop = loop
        self.buffer = ""
        self.last_updated = 0

    @property
    def encoding(self):
        return sys.stdout.encoding

    @override
    def write(self, text: str):
        self.buffer += (
            text  # I think this is quite slow in Python, but I'm not sure
        )
        return len(text)

    @override
    def flush(self):
        now = time.time()
        if 1 + self.last_updated < now:
            self.last_updated = now
            asyncio.run_coroutine_threadsafe(
                edit_response(
                    self.inter_or_msg, f"```{self.buffer.strip()}```"
                ),
                self.loop,
            )
        self.buffer = ""


@contextmanager
def edit_response_with_stderr(
    inter_or_msg: discord.Message | discord.Interaction,
    loop: asyncio.AbstractEventLoop,
):
    original_stderr = sys.stderr
    custom_stderr = ItgCliStdOutHandler(inter_or_msg, loop)
    sys.stderr = custom_stderr
    try:
        yield
    finally:
        sys.stderr = original_stderr
