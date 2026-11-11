"""The model clients: live Claude through the owner's API key, recorded
answers for tests, CI and the demo (no key, no cost), and a recorder that asks
Claude only for what isn't recorded yet. Every answer is untrusted until
`parse_summary` accepts it."""

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from pydantic import ValidationError

from record_access_audit.core.summary import Summary
from record_access_audit.model.request import SummaryRequest

if TYPE_CHECKING:
    import anthropic

RECORDINGS = Path(__file__).resolve().parents[3] / "evalset" / "recorded" / "summaries.json"
# In a cloud session the owner's key is kept under this name: Claude Code
# itself reads ANTHROPIC_API_KEY, and the owner's key must pay for this app only.
OWNER_KEY = "OWNER_ANTHROPIC_API_KEY"


class Summariser(Protocol):
    @property
    def model(self) -> str: ...

    def answer(self, request: SummaryRequest) -> str:
        """The model's raw answer; `parse_summary` checks it before anything trusts it."""
        ...


def parse_summary(raw: str) -> Summary | None:
    """The summary in `raw`, or None if it isn't exactly the agreed shape (C2)."""
    try:
        return Summary.model_validate_json(raw)
    except ValidationError:
        return None


def recording_key(request: SummaryRequest) -> str:
    """A hash of the exact request, so a changed prompt, model or fact can't reuse an old answer."""
    return hashlib.sha256(request.to_json().encode()).hexdigest()


class ClaudeSummariser:
    """Claude through the owner's API key, never a subscription, answering as a `Summary`."""

    def __init__(self, api_key: str, model: str, client: "anthropic.Anthropic | None" = None) -> None:
        import anthropic  # loaded only when Claude is used live

        self.model = model
        self._client = client or anthropic.Anthropic(api_key=api_key)

    def answer(self, request: SummaryRequest) -> str:
        try:
            response = self._client.messages.parse(
                model=request.model,
                max_tokens=1024,
                system=request.system,
                messages=[{"role": "user", "content": request.user_message()}],
                output_format=Summary,
            )
        except ValidationError:
            # An answer that doesn't fit the type is no summary, not a crash (C2).
            return ""
        if response.stop_reason != "end_turn" or response.parsed_output is None:
            return ""
        return response.parsed_output.model_dump_json()


class NotRecordedError(KeyError):
    """No recorded answer for this exact request: record again with the owner's key."""


def load_recordings(file: Path) -> dict[str, str]:
    if not file.exists():
        return {}
    loaded: dict[str, str] = json.loads(file.read_text(encoding="utf-8"))["answers"]
    return loaded


def save_recordings(file: Path, recordings: dict[str, str]) -> None:
    file.parent.mkdir(parents=True, exist_ok=True)
    body = {
        "made_up": "Claude's answers about made-up cases at a made-up clinic, keyed by the request's hash.",
        "answers": dict(sorted(recordings.items())),
    }
    file.write_text(json.dumps(body, indent=1) + "\n", encoding="utf-8")


class RecordedSummariser:
    """Replays recorded answers, keyed by the exact request."""

    def __init__(self, recordings: dict[str, str], model: str) -> None:
        self._recordings = recordings
        self.model = model

    @classmethod
    def from_file(cls, file: Path = RECORDINGS, model: str = "claude-sonnet-5-5") -> "RecordedSummariser":
        return cls(load_recordings(file), model)

    def answer(self, request: SummaryRequest) -> str:
        try:
            return self._recordings[recording_key(request)]
        except KeyError:
            raise NotRecordedError(recording_key(request)) from None


class RecordingSummariser:
    """Asks the live model only for what isn't recorded yet, saving each answer as it comes."""

    def __init__(self, live: Summariser, file: Path = RECORDINGS) -> None:
        self._live = live
        self._file = file
        self._recordings = load_recordings(file)
        self.used: set[str] = set()
        self.model = live.model

    def answer(self, request: SummaryRequest) -> str:
        key = recording_key(request)
        self.used.add(key)
        if key not in self._recordings:
            self._recordings[key] = self._live.answer(request)
            save_recordings(self._file, self._recordings)
        return self._recordings[key]
