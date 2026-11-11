import os

import pytest

from record_access_audit.fhir.client import FhirServer
from record_access_audit.made_up.generate import generate
from record_access_audit.made_up.load import load

FHIR_URL = os.environ.get("FHIR_URL", "http://127.0.0.1:8090/fhir")


@pytest.fixture(scope="session")
def loaded_fhir() -> FhirServer:
    """The local FHIR server with the made-up clinic on it, loaded once per run."""
    load(FHIR_URL, generate().clinic)
    return FhirServer(FHIR_URL)
