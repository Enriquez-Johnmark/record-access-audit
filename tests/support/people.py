"""The tool's made-up users in a test database."""

from record_access_audit.people import User, add_user
from record_access_audit.store.db import Db

OFFICER_EMAIL = "privacy@clinic.example.test"
ADMIN_EMAIL = "admin@clinic.example.test"


def officer_and_admin(db: Db) -> tuple[User, User]:
    return (
        add_user(db, OFFICER_EMAIL, "Alex Example", "privacy officer"),
        add_user(db, ADMIN_EMAIL, "Example Administrator", "administrator"),
    )
