import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import datetime
from io import TextIOBase
import sys
import time
import discord
import itg_cli
import logging
import os
import re
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
            return
        except Exception as e:
            self.logger.exception(f"add_song threw an exception")
            await inter.edit_original_response(embed=error_embed(e))
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
        # Send "thinking" message
        if isinstance(inter_or_msg, discord.Interaction):
            await inter_or_msg.response.defer(thinking=True)
        elif isinstance(inter_or_msg, discord.Message):
            inter_or_msg = await inter_or_msg.reply("Processing command...")

        # Run add_song and handle exceptions accordingly
        try:
            sf, path = await add_song_async(
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


async def edit_response(
    inter_or_msg: discord.Interaction | discord.Message, **kwargs
):
    if isinstance(inter_or_msg, discord.Interaction):
        await inter_or_msg.edit_original_response(**kwargs)
    elif isinstance(inter_or_msg, discord.Message):
        await inter_or_msg.edit(**kwargs)
    else:
        raise ValueError("inter_or_msg is not Interaction or Message")


# Async Wrappers

# Thread pools for performing add-song and add-pack operations.
# itg-cli wasn't built with concurrency in mind, so max_workers=1 (i.e. add_song
# and add_pack operations are handled in a queue)
ADD_SONG_EXECUTOR = ThreadPoolExecutor(max_workers=1)
ADD_PACK_EXECUTOR = ThreadPoolExecutor(max_workers=1)


def get_add_pack_overwrite_handler(
    inter: discord.Interaction, loop: asyncio.AbstractEventLoop
):
    def overwrite_handler(_new: SimfilePack, _old: SimfilePack) -> bool:
        asyncio.run_coroutine_threadsafe(
            inter.edit_original_response(
                content="Pack already exists. Aborting.", embed=None
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
            edit_response(
                inter_or_msg,
                content="Song already exists. Aborting.",
                embed=None,
            ),
            loop,
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
) -> tuple[Simfile, str]:
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
        self.buffer += text
        return len(text)

    @override
    def flush(self):
        now = time.time()
        # Post an update only if
        #   It's been at least 1 second since our last update
        #   Our string contains 1-3 digits followed by %
        if 1 + self.last_updated < now and re.search(
            r"[0-9]{1,3}%", self.buffer
        ):
            self.last_updated = now
            asyncio.run_coroutine_threadsafe(
                edit_response(
                    self.inter_or_msg, embed=progress_embed(self.buffer)
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


# Embed Templates
BERKELEY_BLUE = discord.Color.from_str("#002676")
CALIFORNIA_GOLD = discord.Color.from_str("#FDB515")


def progress_embed(progress_text: str) -> discord.Embed:
    return discord.Embed(
        title="Downloading...",
        description=f"```{progress_text}```",
        color=CALIFORNIA_GOLD,
        timestamp=datetime.datetime.fromtimestamp(time.time()),
    )


def error_embed(e: Exception) -> discord.Embed:
    return discord.Embed(
        title="An Error Occurred",
        description=f"```{e}```",
        color=discord.Color.red(),
    )


def add_song_success(
    sf: Simfile, path: str, user: discord.User
) -> tuple[discord.Embed, Optional[discord.File]]:
    banner_path = None
    singles_pack = SimfilePack(Path(path).parents[1])
    if sf.banner:
        banner_path = Path(path).parent.joinpath(sf.banner)
    elif singles_pack.banner():
        banner_path = singles_pack.banner()
    embed = discord.Embed(
        title=f"Added {sf.title} to {singles_pack.name}",
        description=f"added by <@{user.id}>",
        color=BERKELEY_BLUE,
        timestamp=datetime.datetime.fromtimestamp(time.time()),
    )
    embed.add_field(name="Title", value=sf.title)
    embed.add_field(name="Artist", value=sf.artist)
    embed.add_field(
        name="Charts",
        value="\n".join(
            [f"**[{c.meter}]** {c.description}" for c in sf.charts]
        ),
        inline=False,
    )
    if banner_path:
        embed.set_image(url=f"attachment://{sf.banner}")
        return (embed, discord.File(banner_path, filename=sf.banner))
    else:
        return (embed, None)


def add_pack_success(
    pack: SimfilePack, user: discord.User
) -> tuple[discord.Embed, Optional[discord.File]]:
    embed = discord.Embed(
        title=f"Added {pack.name}",
        description=f"added by <@{user.id}>",
        color=BERKELEY_BLUE,
        timestamp=datetime.datetime.fromtimestamp(time.time()),
    )
    simfile_strings = [
        f"**{[int(c.meter) for c in sf.charts]}** {sf.title}"
        for sf in sorted(
            list(pack.simfiles(strict=False)),
            key=lambda sf: sf.titletranslit or sf.title,
        )
    ]
    simfile_list = ""
    for i, line in enumerate(simfile_strings):
        if len(simfile_list) + len(line) > 1000:  # Real limit is 1024
            simfile_list = (
                simfile_list + f"And {len(simfile_strings) - i} more..."
            )
            break
        else:
            simfile_list += f"{line}\n"

    embed.add_field(
        name=f"Contains {len(simfile_strings)} songs", value=simfile_list
    )

    if pack.banner():
        banner_name = Path(pack.banner()).name
        embed.set_image(url=f"attachment://{banner_name}")
        return (embed, discord.File(pack.banner(), filename=banner_name))
    else:
        return (embed, None)
