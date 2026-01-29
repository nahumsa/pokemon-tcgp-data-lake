from enum import Enum
from pydantic import BaseModel


class GameEnum(str, Enum):
    POCKET = "POCKET"
    TCG = "PTCG"


class FormatEnum(str, Enum):
    STANDARD = "STANDARD"


class PlatformEnum(str, Enum):
    ALL = "all"


class TypeEnum(str, Enum):
    ONLINE = "online"


class TimeEnum(str, Enum):
    PAST_FOUR_WEEKS = "4weeks"
    PAST_SEVEN_DAYS = "7days"
    ALL = "all"


class TournamentPayload(BaseModel):
    game: GameEnum
    format: FormatEnum
    platform: PlatformEnum
    type: TypeEnum
    time: TimeEnum | str
    show: int = 100
    page: int = 1

    def increment_page(self) -> None:
        self.page += 1
