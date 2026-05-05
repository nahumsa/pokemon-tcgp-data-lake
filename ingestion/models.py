from typing import Annotated, Any, Optional
from pydantic import BaseModel, Field, BeforeValidator, computed_field

from .constants import BASE_URL


def extract_node_text(value: Any) -> str:
    if not hasattr(value, "text"):
        return str(value)

    text = value.text(strip=True)
    if text:
        return text

    tooltip_node = value.css_first("[data-tooltip]")
    if tooltip_node:
        return tooltip_node.attributes.get("data-tooltip", "")

    return ""


TextExtractorValidator = Annotated[
    Any, BeforeValidator(extract_node_text)
]


class Participant(BaseModel):
    tournament_link: str
    place: Annotated[TextExtractorValidator, Field(alias="Place")]
    name: Annotated[TextExtractorValidator, Field(alias="Name")]
    record: Annotated[TextExtractorValidator, Field(alias="Record")]
    deck: Annotated[Optional[TextExtractorValidator], Field(alias="Deck")] = None
    raw_decklist: Annotated[Any, Field(alias="List", exclude=True)] = None
    points: Annotated[Optional[TextExtractorValidator], Field(alias="Points")] = None

    @computed_field
    @property
    def decklist_link(self) -> Optional[str]:
        if self.raw_decklist and (link := self.raw_decklist.css_first("a")):
            if href := link.attributes.get("href"):
                return BASE_URL + href

    @computed_field
    @property
    def matches(self) -> Optional[str]:
        if self.raw_decklist and (link := self.raw_decklist.css_first("a")):
            if href := link.attributes.get("href"):
                return BASE_URL + href.replace("/decklist", "")


class Tournament(BaseModel):
    data_date: Annotated[Optional[str], Field(alias="data-date")] = None
    data_time: Annotated[Optional[str], Field(alias="data-time")] = None
    data_name: Annotated[Optional[str], Field(alias="data-name")] = None
    data_organizer: Annotated[Optional[str], Field(alias="data-organizer")] = None
    data_format: Annotated[Optional[str], Field(alias="data-format")] = None
    data_players: Annotated[Optional[str], Field(alias="data-players")] = None
    data_winner: Annotated[Optional[str], Field(alias="data-winner")] = None
    tournament_page: Optional[str] = None

    @computed_field
    @property
    def date(self) -> Optional[str]:
        return self.data_date


class Card(BaseModel):
    name: str
    code: Optional[str]
    quantity: int
    kind: str


class Deck(BaseModel):
    player: str
    tournament: str
    decklist: list[Card]
    decklist_link: Optional[str]


class Match(BaseModel):
    round: Annotated[TextExtractorValidator, Field(alias="Round")]
    player1: Annotated[TextExtractorValidator, Field(alias="P1")]
    player2: Annotated[TextExtractorValidator, Field(alias="P2")]
    result: Annotated[TextExtractorValidator, Field(alias="Result")]
    tournament: str
