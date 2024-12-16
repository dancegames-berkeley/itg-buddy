import logging
import os

from dataclasses import dataclass
from pathlib import Path
from typing import Self, Optional


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
            int(env_bindings["ADD_SONG_CHANNEL_ID"]),
        )
