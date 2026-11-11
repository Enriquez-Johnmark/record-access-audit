import httpx
import pytest

from record_access_audit.fhir.client import FhirError, FhirServer
from record_access_audit.made_up.generate import generate
from record_access_audit.made_up.load import load


def test_h3_the_tools_fhir_client_only_ever_reads() -> None:
    methods: list[str] = []

    def answer(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        return httpx.Response(200, json={"resourceType": "Bundle", "type": "searchset", "entry": []})

    server = FhirServer("http://127.0.0.1:8090/fhir", transport=httpx.MockTransport(answer))
    server.fetch_clinic()
    assert methods
    assert set(methods) == {"GET"}
    public = {name for name in dir(server) if not name.startswith("_")}
    assert public == {"base_url", "fetch", "fetch_clinic"}


def test_h3_the_loader_accepts_only_a_server_on_this_computer() -> None:
    clinic = generate().clinic
    for url in ["https://fhir.example.test/fhir", "http://10.0.0.5:8080/fhir", "http://hapi.fhir.org/baseR4"]:
        with pytest.raises(FhirError, match="only loads made-up data into a FHIR server on this computer"):
            load(url, clinic)


def bundle_with_next(url: str) -> httpx.Response:
    return httpx.Response(
        200, json={"resourceType": "Bundle", "entry": [], "link": [{"relation": "next", "url": url}]}
    )


def test_h2_pages_that_repeat_or_point_elsewhere_are_refused() -> None:
    base = "https://fhir.clinic.example.test/fhir"
    for next_url, problem in [
        (f"{base}/Practitioner?page=2", "the server's pages repeat"),
        ("http://fhir.clinic.example.test/fhir/Practitioner?page=2", "points elsewhere"),
        ("https://other.example.test/fhir/Practitioner?page=2", "points elsewhere"),
    ]:

        def answer(_: httpx.Request, next_url: str = next_url) -> httpx.Response:
            return bundle_with_next(next_url)

        server = FhirServer(base, transport=httpx.MockTransport(answer))
        with pytest.raises(FhirError, match=problem):
            server.fetch("Practitioner")
