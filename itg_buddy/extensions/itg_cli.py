from operator import add
import discord
import itg_cli
import logging
from simfile.dir import SimfilePack
from simfile.types import Simfile
from discord.ext import commands
from discord import app_commands
from pathlib import Path
from typing import Optional


class ItgCliCommands(commands.Cog):
    bot: commands.Bot
    packs: Path
    courses: Path
    singles: Path
    cache: Optional[Path]
    add_song_channel_id: Optional[int]
    logger: logging.Logger

    def __init__(
        self,
        bot: commands.Bot,
        packs: Path,
        courses: Path,
        singles: str,
        cache: Optional[Path] = None,
        add_song_channel_id: Optional[int] = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.bot = bot
        self.packs = packs
        self.courses = courses
        self.singles = packs.join(singles)
        self.cache = cache
        self.add_song_channel_id = add_song_channel_id
        self.logger = self.logger = logging.getLogger(
            f"{bot.__class__.__name__}.{self.__class__.__name__}"
        )

    @app_commands.command(
        name="add_pack", description="Add a pack to the machine."
    )
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
                self.packs,
                self.courses,
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

    @app_commands.command(
        name="add_song", description="Add a song to the Berkeley Test Bench."
    )
    @app_commands.describe(link="Link to the song to add")
    async def add_pack(
        self,
        inter: discord.Interaction,
        link: str,
    ):
        # Define overwrite handler for add_song
        # TODO: make this more pretty with buttons and stuff
        # Maybe genericize it for both add_song and add_pack?
        # Will need to handle arg type differences
        def overwrite_handler(
            _new: tuple[Simfile, str], _old: tuple[Simfile, str]
        ) -> bool:
            inter.response.send_message("Song already exists. Aborting.")
            return False

        # Run add_song and handle exceptions accordingly
        try:
            sm, _ = itg_cli.add_song(
                link,
                self.singles,
                self.cache,
                overwrite=overwrite_handler,
                delete_macos_files_flag=True,
            )
        except itg_cli.OverwriteException:
            return
        except Exception as e:
            # TODO: maybe convert this into an exception handler for the cog?
            inter.response.send_message(
                f"add_song threw an exception: `{type(e)}`\n`{e.args}`"
            )
            return

        # Send result message on success
        inter.response.send_message(
            f"Added {sm.title} to Berkeley Test Bench."
        )
