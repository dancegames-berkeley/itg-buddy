import asyncio
from io import TextIOBase
import re
import time
from typing import override
import discord
import itg_cli
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from simfile.types import Simfile

from itg_buddy.extensions.itg_cli.itg_cli import edit_response_with_stderr
from itg_buddy.extensions.itg_cli.embeds import progress_embed
from itg_buddy.extensions.itg_cli.utils import edit_response


# Thread pools for performing add-song and add-pack operations.
# itg-cli wasn't built with concurrency in mind, so max_workers=1 (i.e. add_song
# and add_pack operations are handled in a queue)
ADD_SONG_EXECUTOR = ThreadPoolExecutor(max_workers=1)
ADD_PACK_EXECUTOR = ThreadPoolExecutor(max_workers=1)


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
        #   Our buffer contains a percent (1-3 digits followed by %)
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
