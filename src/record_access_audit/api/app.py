"""The JSON API for the privacy officer's pages and the administrator's, and
the login links (H1). Every staff route checks the role; every change must
come from this site. The React app is served from `web/dist`."""

import logging
from collections.abc import AsyncGenerator, Awaitable, Callable, Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, cast
from urllib.parse import urlparse

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, ConfigDict

from record_access_audit.activity import activity, timeline
from record_access_audit.audit_run import fetch_and_run
from record_access_audit.auth import (
    SESSION_HOURS,
    Mail,
    Session,
    end_session,
    request_link,
    session_of,
    use_link,
)
from record_access_audit.case_view import view_case
from record_access_audit.clock import Clock, SystemClock
from record_access_audit.core.records import ClinicFacts, Department, Role
from record_access_audit.core.rules import DESCRIPTIONS, RuleCode
from record_access_audit.decisions import LABELS, DecisionError, NoSuchCaseError, decide
from record_access_audit.fhir.client import FhirError, FhirServer
from record_access_audit.mail import Mailer
from record_access_audit.model.client import Summariser
from record_access_audit.people import User, user_by_id
from record_access_audit.store.db import Db
from record_access_audit.store.queue import open_cases
from record_access_audit.store.rule_sets import (
    RuleSetError,
    change_rules,
    current,
    from_settings,
    settings_of,
)
from record_access_audit.summaries import summarise_open

COOKIE = "raa_session"
WEB = Path(__file__).resolve().parents[3] / "web" / "dist"


@dataclass(frozen=True)
class AppConfig:
    database_url: str
    base_url: str
    facts: ClinicFacts
    fhir_url: str


class LoginBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str


class DecisionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    outcome: str
    reason: str


@dataclass
class _State:
    config: AppConfig
    clock: Clock
    mailer: Mailer | None
    model: Summariser | None
    pool: "ConnectionPool[Any]"


def _state(request: Request) -> _State:
    return cast(_State, request.app.state.audit)


StateDep = Annotated[_State, Depends(_state)]


def _db(state: StateDep) -> Iterator[Db]:
    with state.pool.connection() as conn:
        yield cast(Db, conn)


DbDep = Annotated[Db, Depends(_db)]


def _session(request: Request, state: StateDep, db: DbDep) -> Session | None:
    return session_of(db, state.clock, request.cookies.get(COOKIE))


SessionDep = Annotated[Session | None, Depends(_session)]


def _user(session: SessionDep, db: DbDep) -> User:
    if session is None or session.who != "user":
        raise HTTPException(401, "log in first")
    user = user_by_id(db, int(session.person_id))
    if user is None:
        raise HTTPException(401, "log in first")
    return user


UserDep = Annotated[User, Depends(_user)]


def _officer(user: UserDep) -> User:
    if user.role != "privacy officer":
        raise HTTPException(403, "only the privacy officer can do this")
    return user


def _administrator(user: UserDep) -> User:
    if user.role != "administrator":
        raise HTTPException(403, "only the administrator can do this")
    return user


OfficerDep = Annotated[User, Depends(_officer)]
AdminDep = Annotated[User, Depends(_administrator)]

CSP = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'"


def create_app(
    config: AppConfig,
    clock: Clock | None = None,
    mailer: Mailer | None = None,
    model: Summariser | None = None,
) -> FastAPI:
    clock = clock or SystemClock()
    pool: ConnectionPool[Any] = ConnectionPool(
        config.database_url,
        kwargs={"autocommit": True, "row_factory": dict_row},
        min_size=1,
        max_size=8,
        open=True,
    )
    origin = urlparse(config.base_url)
    secure = origin.scheme == "https"

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
        yield
        pool.close()

    app = FastAPI(
        title="Record Access Audit", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan
    )
    app.state.audit = _State(config, clock, mailer, model, pool)

    @app.middleware("http")
    async def guard(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        # A change must come from this site (no cross-site form or script can make one).
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            sent = request.headers.get("origin")
            if sent is not None and urlparse(sent)[:2] != origin[:2]:
                return Response(status_code=403, content="changes must come from this site")
            if request.headers.get("sec-fetch-site") == "cross-site":
                return Response(status_code=403, content="changes must come from this site")
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = CSP
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        return response

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/login", status_code=204)
    def login(body: LoginBody, db: DbDep, background: BackgroundTasks) -> Response:
        mail = request_link(db, clock, body.email, config.base_url)
        if mail is not None:
            # Sent after answering, so a known address answers as quickly as an
            # unknown one, and a mail failure changes nothing anyone can see.
            background.add_task(_send, mailer or _no_mail, mail)
        return Response(status_code=204)

    @app.post("/api/login/{token}")
    def use_login_link(token: str, db: DbDep) -> Response:
        # Only this POST, from the page the link opens, uses the link: an email
        # scanner that opens the link can't use it up.
        used = use_link(db, clock, token)
        if used is None:
            raise HTTPException(400, "This login link has expired or has already been used. Get a new one.")
        secret, session = used
        response = JSONResponse({"who": session.who})
        response.set_cookie(
            COOKIE,
            secret,
            max_age=SESSION_HOURS * 3600,
            httponly=True,
            samesite="lax",
            secure=secure,
            path="/",
        )
        return response

    @app.post("/api/logout", status_code=204)
    def logout(request: Request, db: DbDep) -> Response:
        end_session(db, request.cookies.get(COOKIE))
        response = Response(status_code=204)
        response.delete_cookie(COOKIE, path="/")
        return response

    @app.get("/api/me")
    def me(user: UserDep) -> dict[str, Any]:
        return {"who": "user", "email": user.email, "name": user.name, "role": user.role}

    @app.get("/api/queue")
    def queue(_: OfficerDep, db: DbDep) -> list[dict[str, Any]]:
        names = _names(db)
        return [
            {
                "id": row.id,
                "staff": names["staff"][row.staff],
                "patient": names["patients"].get(row.patient) if row.patient else None,
                "day": row.day,
                "rules": sorted(row.codes, key=lambda code: list(RuleCode).index(RuleCode(code))),
                "score": row.score,
                "age_days": row.age_days,
                "first_look": row.first_access_at,
            }
            for row in open_cases(db, clock)
        ]

    @app.get("/api/decided")
    def decided(_: OfficerDep, db: DbDep) -> list[dict[str, Any]]:
        names = _names(db)
        rows = db.execute(
            "select distinct on (c.id) c.id, c.staff, c.patient, c.day, d.outcome, d.decided_at, d.decided_by"
            " from cases c join decisions d on d.case_id = c.id order by c.id, d.id desc"
        ).fetchall()
        return [
            {
                "id": r["id"],
                "staff": names["staff"][str(r["staff"])],
                "patient": names["patients"].get(str(r["patient"])) if r["patient"] else None,
                "day": r["day"],
                "outcome": r["outcome"],
                "outcome_label": LABELS[str(r["outcome"])],
                "decided_at": r["decided_at"],
                "decided_by": r["decided_by"],
            }
            for r in sorted(rows, key=lambda r: r["decided_at"], reverse=True)
        ]

    @app.get("/api/cases/{case_id}")
    def case(case_id: int, user: OfficerDep, db: DbDep) -> dict[str, Any]:
        try:
            view = view_case(db, clock, user, config.facts, case_id)
        except KeyError:
            raise HTTPException(404, "no such case") from None
        body = cast(dict[str, Any], jsonable_encoder(view))
        body["timeline"] = jsonable_encoder(timeline(db, case_id))
        body["outcomes"] = [{"value": value, "label": label} for value, label in LABELS.items()]
        return body

    @app.post("/api/cases/{case_id}/decisions", status_code=201)
    def record_decision(case_id: int, body: DecisionBody, user: OfficerDep, db: DbDep) -> dict[str, Any]:
        try:
            made = decide(db, clock, user, case_id, body.outcome, body.reason)
        except NoSuchCaseError:
            raise HTTPException(404, "no such case") from None
        except DecisionError as error:
            raise HTTPException(400, str(error)) from None
        return cast(dict[str, Any], jsonable_encoder(made))

    @app.get("/api/rules")
    def rules(_: UserDep, db: DbDep) -> dict[str, Any]:
        rule_set = current(db, clock)
        versions = db.execute(
            "select version, created_at, created_by from rule_set_versions order by version desc"
        ).fetchall()
        return {
            "version": rule_set.version,
            "settings": settings_of(rule_set),
            "rules": [{"code": code.value, "description": DESCRIPTIONS[code]} for code in RuleCode],
            "roles": [{"value": role.name, "label": role.value} for role in Role],
            "versions": jsonable_encoder(versions),
        }

    @app.post("/api/rules", status_code=201)
    def change(body: dict[str, Any], user: OfficerDep, db: DbDep) -> dict[str, Any]:
        try:
            changed = change_rules(db, clock, user, from_settings(body))
        except (RuleSetError, KeyError, ValueError, TypeError) as error:
            raise HTTPException(400, f"those rules can't be used: {error}") from None
        return {"version": changed.version, "settings": settings_of(changed)}

    @app.get("/api/activity")
    def log(
        _: UserDep, db: DbDep, actor: str | None = None, action: str | None = None
    ) -> list[dict[str, Any]]:
        return cast(
            list[dict[str, Any]], jsonable_encoder(activity(db, actor=actor or None, action=action or None))
        )

    @app.post("/api/run")
    def run(user: AdminDep, db: DbDep) -> dict[str, Any]:
        try:
            result = fetch_and_run(db, clock, FhirServer(config.fhir_url), config.facts, actor=user.email)
        except FhirError as error:
            raise HTTPException(502, f"The record system's FHIR server couldn't be read: {error}") from None
        summaries = summarise_open(db, clock, model, config.facts, actor=user.email)
        return {
            "new_accesses": result.new_accesses,
            "refused": [f"{r.resource}: {r.reason}" for r in result.refused],
            "new_flags": result.run.flags,
            "new_cases": result.run.cases,
            "summaries": summaries,
        }

    @app.get("/api/{rest:path}")
    def unknown(rest: str) -> None:
        raise HTTPException(404, "no such API")

    if (WEB / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=WEB / "assets"), name="assets")

        @app.get("/{rest:path}")
        def page(rest: str) -> FileResponse:
            # A built file if there is one (icons), else the app, which routes itself.
            candidate = (WEB / rest).resolve()
            if rest and candidate.is_file() and WEB.resolve() in candidate.parents:
                return FileResponse(candidate)
            return FileResponse(WEB / "index.html")

    return app


def _send(mailer: Mailer, mail: Mail) -> None:
    try:
        mailer.send(mail.to, mail.subject, mail.body)
    except Exception as error:  # logged, never shown: it would reveal the address is known
        logging.getLogger(__name__).warning("sending a login link failed: %s", type(error).__name__)


class _NoMail:
    def send(self, to: str, subject: str, body: str) -> None:
        raise RuntimeError("no mailer configured")


_no_mail = _NoMail()


def _names(db: Db) -> dict[str, dict[str, Any]]:
    staff = {
        str(r["id"]): {
            "id": r["id"],
            "name": f"{r['given']} {r['family']}",
            "role": Role[str(r["role"])].value,
            "department": Department[str(r["department"])].value,
        }
        for r in db.execute("select id, given, family, role, department from staff").fetchall()
    }
    patients = {
        str(r["id"]): {"id": r["id"], "name": f"{r['given']} {r['family']}"}
        for r in db.execute("select id, given, family from patients").fetchall()
    }
    return {"staff": staff, "patients": patients}
