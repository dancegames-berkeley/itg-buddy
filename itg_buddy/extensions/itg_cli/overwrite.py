# Overwrite Button View
import asyncio

import discord

from simfile.types import Simfile
from simfile.dir import SimfilePack
from itg_buddy.extensions.itg_cli.embeds import (
    overwrite_pack_embed,
    overwrite_song_embed,
)
from itg_buddy.extensions.itg_cli.utils import edit_response


class OverwriteView(discord.ui.View):
    choice: asyncio.Future[bool]
    parent: discord.Interaction | discord.Message
    user: discord.User

    def __init__(
        self,
        user: discord.User,
        parent: discord.Interaction | discord.Message,
        *args,
        **kwargs,
    ):
        super().__init__(*args, timeout=60, **kwargs)
        self.choice = asyncio.get_running_loop().create_future()
        self.parent = parent
        self.user = user

    async def interaction_check(
        self, interaction: discord.Interaction
    ) -> bool:
        if interaction.user == self.user:
            return True
        await interaction.response.send_message(
            f"The command was initiated by {self.user.mention}", ephemeral=True
        )
        return False

    async def on_timeout(self):
        self.choice.set_result(False)
        self.stop()
        await edit_response(self.parent, view=None)

    @discord.ui.button(
        label="Overwrite",
        style=discord.ButtonStyle.green,
    )
    async def overwrite(
        self, interaction: discord.Interaction, _button: discord.ui.Button
    ):
        self.choice.set_result(True)
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(
        label="Cancel",
        style=discord.ButtonStyle.red,
    )
    async def cancel(
        self, interaction: discord.Interaction, _button: discord.ui.Button
    ):
        self.choice.set_result(False)
        self.stop()
        await interaction.response.defer()


def get_add_pack_overwrite_handler(
    command_interaction: discord.Interaction,
    loop: asyncio.AbstractEventLoop,
):
    async def async_helper(
        new: SimfilePack, old: SimfilePack, interaction: discord.Interaction
    ):
        view = OverwriteView(interaction.user, parent=command_interaction)
        await interaction.edit_original_response(
            embed=overwrite_pack_embed(new, old),
            view=view,
        )
        return await view.choice

    def pack_overwrite_handler(new: SimfilePack, old: SimfilePack) -> bool:
        return asyncio.run_coroutine_threadsafe(
            async_helper(new, old, command_interaction), loop
        ).result()

    return pack_overwrite_handler


def get_add_song_overwrite_handler(
    inter_or_msg: discord.Interaction | discord.Message,
    user: discord.User,
    loop: asyncio.AbstractEventLoop,
):
    async def async_helper(
        new: Simfile,
        old: Simfile,
        inter_or_msg: discord.Interaction | discord.Message,
    ):
        view = OverwriteView(user, parent=inter_or_msg)
        await edit_response(
            inter_or_msg,
            embed=overwrite_song_embed(new, old),
            view=view,
        )
        return await view.choice

    def song_overwrite_handler(
        new: tuple[Simfile, str], old: tuple[Simfile, str]
    ) -> bool:
        return asyncio.run_coroutine_threadsafe(
            async_helper(new[0], old[0], inter_or_msg), loop
        ).result()

    return song_overwrite_handler
