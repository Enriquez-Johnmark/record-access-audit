"""Loading the made-up clinic into a FHIR server on this computer, for the
demo and the tests. Never a public or remote server: the data is made up, but
a test server elsewhere is not ours to fill (H3)."""

from typing import Any
from urllib.parse import urlparse

import httpx

from record_access_audit.core.records import Clinic
from record_access_audit.fhir.build import resources
from record_access_audit.fhir.client import FhirError

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
CHUNK = 400


def load(base_url: str, clinic: Clinic) -> int:
    """Writes every resource with PUT (so loading again changes nothing),
    in transaction bundles; returns how many were written."""
    host = urlparse(base_url).hostname
    if host not in LOCAL_HOSTS:
        raise FhirError(f"only loads made-up data into a FHIR server on this computer, not {base_url}")
    built = resources(clinic)
    with httpx.Client(timeout=300) as http:
        for start in range(0, len(built), CHUNK):
            bundle: dict[str, Any] = {
                "resourceType": "Bundle",
                "type": "transaction",
                "entry": [
                    {
                        "resource": resource,
                        "request": {"method": "PUT", "url": f"{resource['resourceType']}/{resource['id']}"},
                    }
                    for resource in built[start : start + CHUNK]
                ],
            }
            response = http.post(
                base_url.rstrip("/"), json=bundle, headers={"Content-Type": "application/fhir+json"}
            )
            if response.status_code >= 300:
                raise FhirError(f"loading failed: {response.status_code} {response.text[:300]}")
    return len(built)
