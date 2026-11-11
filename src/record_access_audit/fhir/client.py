"""The tool's client for the clinic's FHIR server. It only reads (H3): every
request is a GET, and it has no method that writes. Loading made-up data is
`made_up.load`, a separate command for a server on this computer."""

import json
from typing import Any, cast
from urllib.parse import urlparse

import httpx

from record_access_audit.fhir.build import CLINIC_TAG

Resource = dict[str, Any]

# Every resource type the tool reads, in the order it reads them.
TYPES = ["Practitioner", "PractitionerRole", "Patient", "CareTeam", "Encounter", "Appointment", "AuditEvent"]
PAGE = 200
# A page bigger than this, or more pages than this, is refused rather than read.
MAX_PAGE_BYTES = 20_000_000
MAX_PAGES = 1_000


class FhirError(Exception):
    pass


class FhirServer:
    def __init__(self, base_url: str, *, transport: httpx.BaseTransport | None = None) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise FhirError(f"not a FHIR server address: {base_url}")
        self.base_url = base_url.rstrip("/")
        self._http = httpx.Client(
            transport=transport, timeout=60, headers={"Accept": "application/fhir+json"}
        )

    def fetch(self, kind: str) -> list[Resource]:
        """Every resource of `kind` tagged with the clinic, page by page."""
        tag = f"{CLINIC_TAG['system']}|{CLINIC_TAG['code']}"
        url: str | None = f"{self.base_url}/{kind}"
        params: dict[str, str] | None = {"_tag": tag, "_count": str(PAGE)}
        found: list[Resource] = []
        seen: set[str] = set()
        while url is not None:
            if url in seen:
                raise FhirError(f"the server's pages repeat: {url}")
            if len(seen) >= MAX_PAGES:
                raise FhirError(f"more than {MAX_PAGES} pages of {kind}")
            seen.add(url)
            bundle = self._get(url, params)
            params = None
            for entry in cast(list[dict[str, Any]], bundle.get("entry", [])):
                resource = entry.get("resource")
                if isinstance(resource, dict) and cast(Resource, resource).get("resourceType") == kind:
                    found.append(cast(Resource, resource))
            links = cast(list[dict[str, str]], bundle.get("link", []))
            url = next((link.get("url") for link in links if link.get("relation") == "next"), None)
            if url is not None and not self._ours(url):
                raise FhirError(f"the server's next page points elsewhere: {url}")
        return found

    def fetch_clinic(self) -> dict[str, list[Resource]]:
        return {kind: self.fetch(kind) for kind in TYPES}

    def _ours(self, url: str) -> bool:
        """Whether `url` is on this server: same scheme, host and base path."""
        page, base = urlparse(url), urlparse(self.base_url)
        return (page.scheme, page.netloc) == (base.scheme, base.netloc) and page.path.startswith(base.path)

    def _get(self, url: str, params: dict[str, str] | None) -> dict[str, Any]:
        try:
            with self._http.stream("GET", url, params=params) as response:
                if response.status_code != 200:
                    raise FhirError(f"GET {url}: {response.status_code}")
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_PAGE_BYTES:
                        raise FhirError(f"GET {url}: a page over {MAX_PAGE_BYTES} bytes")
        except httpx.HTTPError as error:
            raise FhirError(f"GET {url}: {error}") from error
        try:
            value = json.loads(body)
        except ValueError as error:
            raise FhirError(f"GET {url}: not JSON") from error
        if not isinstance(value, dict) or cast(dict[str, Any], value).get("resourceType") != "Bundle":
            raise FhirError(f"GET {url}: not a Bundle")
        return cast(dict[str, Any], value)
