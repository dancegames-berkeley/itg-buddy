from pathlib import Path
from typing import Optional
import discord
import datetime
import time
from simfile import Simfile
from simfile.dir import SimfilePack

BERKELEY_BLUE = discord.Color.from_str("#002676")
CALIFORNIA_GOLD = discord.Color.from_str("#FDB515")


def progress_embed(progress_text: str) -> discord.Embed:
    return discord.Embed(
        title="Downloading...",
        description=f"```{progress_text}```",
        color=CALIFORNIA_GOLD,
        timestamp=datetime.datetime.fromtimestamp(time.time()),
    )


def overwrite_song_embed(
    _new_simfile: Simfile, _old_simfile: Simfile
) -> discord.Embed:
    embed = discord.Embed(
        title="Overwrite existing song?", color=CALIFORNIA_GOLD
    )
    return embed


def overwrite_pack_embed(_new_pack, _old_pack) -> discord.Embed:
    embed = discord.Embed(
        title="Overwrite existing pack?", color=CALIFORNIA_GOLD
    )
    return embed


def cancelled_embed() -> discord.Embed:
    return discord.Embed(
        title="Overwrite Cancelled",
        description="Keeping original item.",
        color=discord.Color.red(),
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
            simfile_list += f"And {len(simfile_strings) - i} more..."
            break
        else:
            simfile_list += f"{line}\n"
    embed.add_field(
        name=f"Contains {len(simfile_strings)} songs",
        value=simfile_list,
    )
    if pack.banner():
        banner_name = Path(pack.banner()).name
        embed.set_image(url=f"attachment://{banner_name}")
        return (embed, discord.File(pack.banner(), filename=banner_name))
    else:
        return (embed, None)
