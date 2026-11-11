"""A summary as the model must write it: plain sentences, each citing the
numbered facts it rests on. Parsed strictly; anything else is refused."""

from pydantic import BaseModel, ConfigDict, Field


class Sentence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str = Field(min_length=1, max_length=400)
    facts: list[int] = Field(max_length=20)


class Summary(BaseModel):
    """Up to five sentences of summary, and up to three possible innocent
    explanations for the privacy officer to check."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    summary: list[Sentence] = Field(min_length=1, max_length=5)
    to_check: list[Sentence] = Field(default_factory=lambda: [], max_length=3)
