from typing import Annotated, Any, Optional
from pydantic import BaseModel, Field, BeforeValidator, computed_field

from constants import BASE_URL

TextExtractorValidator = Annotated[Any, BeforeValidator(lambda x: x.text())]

class Participant(BaseModel):
    tournament_link: str
    place: Annotated[TextExtractorValidator, Field(alias="Place")]
    name: Annotated[TextExtractorValidator, Field(alias="Name")]
    record: Annotated[TextExtractorValidator, Field(alias="Record")]
    deck: Annotated[Optional[TextExtractorValidator], Field(alias="Deck")]= None
    raw_decklist: Annotated[Any, Field(alias="List", exclude=True)] = None
    points: Annotated[Optional[TextExtractorValidator], Field(alias="Points")] = None

    @computed_field
    def decklist_link(self) -> Optional[str]:
        if self.raw_decklist:
            return BASE_URL + self.raw_decklist.css_first("a").attributes.get("href")

class Tournament(BaseModel):
    date: Annotated[Optional[str], Field(alias="data-date")]
    name: Annotated[Optional[str], Field(alias="data-name")]
    organizer: Annotated[Optional[str], Field(alias="data-organizer")]
    format: Annotated[Optional[str], Field(alias="data-format")]
    players: Annotated[Optional[str], Field(alias="data-players")]
    winner: Annotated[Optional[str], Field(alias="data-winner")]
    tournament_page: Optional[str]
