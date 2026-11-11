"""The made-up Example Valley Clinic: 30 staff, 300 patients, their care, and
14 days of access log with planted cases and innocent look-alikes, each
labelled. Seeded, so it is the same every time (A1). Every person in it is
made up."""

import random
from dataclasses import dataclass, field, replace
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from record_access_audit.core.records import (
    CLINIC_TIME_ZONE,
    Access,
    AccessKind,
    Address,
    Appointment,
    CareTeamMember,
    Clinic,
    ClinicFacts,
    Department,
    Encounter,
    Patient,
    Role,
    Section,
    Shift,
    Staff,
)
from record_access_audit.made_up.names import (
    GIVEN_NAMES,
    PATIENT_FAMILY_NAMES,
    PATIENT_STREETS,
    STAFF,
    STAFF_STREETS,
)

TZ = ZoneInfo(CLINIC_TIME_ZONE)
SEED = 2026
DAYS = 14
# Monday 19 October 2026, midnight in the clinic's time zone.
START = datetime(2026, 10, 19, tzinfo=TZ)
CITY = "Example City"

OFFICE = Shift(time(8), time(17))
LONG_DAY = Shift(time(7), time(19))
NIGHT = Shift(time(19), time(7))


@dataclass(frozen=True)
class Label:
    """One planted case or innocent look-alike in the log."""

    id: str
    planted: bool
    kind: str
    staff: str
    patient: str | None
    day: date
    rules: tuple[str, ...]  # the rules expected to fire; empty when it should not be flagged
    note: str

    @property
    def flagged(self) -> bool:
        return bool(self.rules)


@dataclass(frozen=True)
class MadeUp:
    clinic: Clinic
    labels: tuple[Label, ...]


def generate() -> MadeUp:
    # A seeded generator for made-up data, not for anything secret.
    return _Builder(random.Random(SEED)).build()  # noqa: S311


def labels_json(labels: tuple[Label, ...]) -> list[dict[str, Any]]:
    return [
        {
            "id": label.id,
            "planted": label.planted,
            "kind": label.kind,
            "staff": label.staff,
            "patient": label.patient,
            "day": label.day.isoformat(),
            "rules": list(label.rules),
            "flagged": label.flagged,
            "note": label.note,
        }
        for label in labels
    ]


def facts_json(facts: ClinicFacts) -> dict[str, Any]:
    """The clinic facts with no FHIR home, as saved in `demo/clinic.json`."""
    return {
        "made_up": "Example Valley Clinic and everyone in it are made up.",
        "shifts": {
            staff: {"start": shift.start.isoformat("minutes"), "end": shift.end.isoformat("minutes")}
            for staff, shift in sorted(facts.shifts.items())
        },
        "staff_records": dict(sorted(facts.staff_records.items())),
        "vips": sorted(facts.vips),
    }


def _day(index: int) -> date:
    return (START + timedelta(days=index)).date()


def _at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=TZ)


@dataclass
class _Builder:
    rng: random.Random
    staff: list[Staff] = field(default_factory=lambda: [])
    shifts: dict[str, Shift] = field(default_factory=lambda: {})
    patients: list[Patient] = field(default_factory=lambda: [])
    care_teams: list[CareTeamMember] = field(default_factory=lambda: [])
    encounters: list[Encounter] = field(default_factory=lambda: [])
    appointments: list[Appointment] = field(default_factory=lambda: [])
    raw: list[tuple[str, datetime, AccessKind, tuple[str, ...], Section | None, int]] = field(
        default_factory=lambda: []
    )
    labels: list[Label] = field(default_factory=lambda: [])
    staff_records: dict[str, str] = field(default_factory=lambda: {})
    vips: set[str] = field(default_factory=lambda: set())
    team: dict[str, list[str]] = field(default_factory=lambda: {})  # patient -> current team

    # ---- people ----

    def build(self) -> MadeUp:
        self._make_staff()
        self._make_patients()
        self._make_care()
        self._make_normal_accesses()
        self._plant()
        self._look_alikes()
        accesses = self._number_accesses()
        clinic = Clinic(
            staff=tuple(self.staff),
            patients=tuple(sorted(self.patients, key=lambda p: p.id)),
            care_teams=tuple(sorted(self.care_teams, key=lambda m: (m.patient, m.staff, m.start))),
            encounters=tuple(sorted(self.encounters, key=lambda e: e.id)),
            appointments=tuple(sorted(self.appointments, key=lambda a: a.id)),
            accesses=accesses,
            facts=ClinicFacts(
                shifts=dict(self.shifts),
                staff_records=dict(self.staff_records),
                vips=frozenset(self.vips),
            ),
        )
        return MadeUp(clinic=clinic, labels=tuple(self.labels))

    def _make_staff(self) -> None:
        for number, (given, family, role, department) in enumerate(STAFF, start=1):
            staff_id = f"S-{number:03d}"
            street = STAFF_STREETS[number - 1]
            address = Address(f"{10 + number * 7} {street}", CITY, "00010")
            self.staff.append(Staff(staff_id, given, family, role, department, address))
            if department is Department.URGENT_CARE:
                shift = LONG_DAY
            elif role is Role.SECURITY:
                shift = LONG_DAY if family == "Okafor" else NIGHT
            else:
                shift = OFFICE
            self.shifts[staff_id] = shift

    def _by(self, role: Role, department: Department | None = None) -> list[Staff]:
        return [
            s for s in self.staff if s.role is role and (department is None or s.department is department)
        ]

    def _person(self, staff_id: str) -> Staff:
        return next(s for s in self.staff if s.id == staff_id)

    def _new_patient(
        self,
        given: str,
        family: str,
        address: Address,
        born: date,
        deceased_at: datetime | None = None,
    ) -> Patient:
        patient_id = f"P-{len(self.patients) + 1:03d}"
        email = f"{given}.{family}.{patient_id.replace('-', '')}@example.test".lower()
        patient = Patient(patient_id, given, family, born, address, deceased_at, email)
        self.patients.append(patient)
        return patient

    def _make_patients(self) -> None:
        # 283 ordinary patients; the last 17 are made for the planted cases and look-alikes.
        for number in range(283):
            pediatric = number % 5 == 0
            born = date(
                self.rng.randint(2012, 2023) if pediatric else self.rng.randint(1942, 2004),
                self.rng.randint(1, 12),
                self.rng.randint(1, 28),
            )
            street = PATIENT_STREETS[number % len(PATIENT_STREETS)]
            address = Address(f"{100 + number * 3} {street}", CITY, f"000{20 + number % 60:02d}")
            self._new_patient(
                self.rng.choice(GIVEN_NAMES), self.rng.choice(PATIENT_FAMILY_NAMES), address, born
            )

    # ---- care ----

    def _make_care(self) -> None:
        fm_doctors = self._by(Role.PHYSICIAN, Department.FAMILY_MEDICINE)
        peds_doctor = self._by(Role.PHYSICIAN, Department.PEDIATRICS)
        fm_nurses = self._by(Role.NURSE, Department.FAMILY_MEDICINE)
        peds_nurses = self._by(Role.NURSE, Department.PEDIATRICS)
        mas = self._by(Role.MEDICAL_ASSISTANT)
        joined = _at(date(2024, 3, 1), 9)
        for index, patient in enumerate(self.patients):
            pediatric = patient.birth_date.year >= 2012
            if pediatric:
                members = [peds_doctor[0].id, peds_nurses[index % len(peds_nurses)].id, mas[2].id]
            else:
                members = [
                    fm_doctors[index % len(fm_doctors)].id,
                    fm_nurses[index % len(fm_nurses)].id,
                    mas[index % 2].id,
                ]
            self.team[patient.id] = members
            for member in members:
                self.care_teams.append(CareTeamMember(patient.id, member, joined, None))
        # Five staff members are also the clinic's patients, cared for by Family Medicine.
        for staff_id in ("S-011", "S-019", "S-022", "S-016", "S-024"):
            person = self._person(staff_id)
            record = self._new_patient(person.given, person.family, person.address, date(1985, 6, 14))
            self.staff_records[staff_id] = record.id
            members = [fm_doctors[0].id, fm_nurses[0].id, mas[0].id]
            self.team[record.id] = members
            for member in members:
                self.care_teams.append(CareTeamMember(record.id, member, joined, None))
        self._visits()

    def _visits(self) -> None:
        """Visits in the 14 days, visits in the 90 days before (for billing),
        and appointments booked for the two weeks after."""
        ordinary = [p for p in self.patients if p.id not in self.staff_records.values()]
        fm_pool = [p for p in ordinary if p.birth_date.year < 2012]
        peds_pool = [p for p in ordinary if p.birth_date.year >= 2012]
        urgent = self._by(Role.PHYSICIAN, Department.URGENT_CARE)
        urgent_nurses = self._by(Role.NURSE, Department.URGENT_CARE)
        labs = self._by(Role.LAB_TECHNICIAN)
        for day_index in range(DAYS):
            day = _day(day_index)
            weekday = day.weekday() < 5
            if weekday:
                for slot, patient in enumerate(self.rng.sample(fm_pool, 10) + self.rng.sample(peds_pool, 3)):
                    team = self.team[patient.id]
                    start = _at(day, 8 + slot % 8, 15 * (slot % 4))
                    self._visit(patient.id, team, start, booked=True)
                    if slot % 3 == 0:
                        lab_start = start + timedelta(hours=1)
                        self._visit(patient.id, [labs[slot % 2].id], lab_start, booked=False)
            for slot, patient in enumerate(self.rng.sample(ordinary, 6)):
                start = _at(day, 8 + slot * 2, 30)
                team = [urgent[slot % 2].id, urgent_nurses[slot % 3].id]
                self._visit(patient.id, team, start, booked=False)
        for patient in self.rng.sample(fm_pool, 110):
            days_before = self.rng.randint(30, 85)
            start = _at(START.date() - timedelta(days=days_before), 10)
            self._visit(patient.id, self.team[patient.id][:2], start, booked=True)
        for patient in self.rng.sample(fm_pool + peds_pool, 90):
            day = _day(DAYS + self.rng.randint(0, 13))
            if day.weekday() >= 5:
                day += timedelta(days=2)
            start = _at(day, 9 + self.rng.randint(0, 6))
            self.appointments.append(
                Appointment(
                    f"AP-{len(self.appointments) + 1:04d}",
                    patient.id,
                    self.team[patient.id][0],
                    start,
                    start + timedelta(minutes=30),
                )
            )

    def _visit(self, patient: str, staff: list[str], start: datetime, *, booked: bool) -> Encounter:
        end = start + timedelta(minutes=45)
        encounter = Encounter(f"E-{len(self.encounters) + 1:04d}", patient, tuple(staff), start, end)
        self.encounters.append(encounter)
        if booked:
            self.appointments.append(
                Appointment(
                    f"AP-{len(self.appointments) + 1:04d}",
                    patient,
                    staff[0],
                    start,
                    start + timedelta(minutes=30),
                )
            )
        return encounter

    def _related(self, staff_id: str, patient: str, at: datetime) -> bool:
        """Whether the clinic's data accounts for this look (a simple copy of the
        spec's rules, used only to choose planted pairs that are truly unrelated)."""
        if any(m.patient == patient and m.staff == staff_id and m.end is None for m in self.care_teams):
            return True
        if any(
            e.patient == patient and staff_id in e.staff and abs((e.start.date() - at.date()).days) <= 1
            for e in self.encounters
        ):
            return True
        if any(
            a.patient == patient and a.staff == staff_id and a.start.date() == at.date()
            for a in self.appointments
        ):
            return True
        role = self._person(staff_id).role
        if role is Role.FRONT_DESK:
            return any(
                a.patient == patient and abs((a.start.date() - at.date()).days) <= 14
                for a in self.appointments
            )
        if role is Role.BILLING:
            return any(
                e.patient == patient and timedelta(0) < at - e.end <= timedelta(days=90)
                for e in self.encounters
            )
        return False

    # ---- the log ----

    def _open(self, staff_id: str, at: datetime, patient: str, section: Section, seconds: int) -> None:
        self.raw.append((staff_id, at, AccessKind.CHART, (patient,), section, seconds))

    def _search(self, staff_id: str, at: datetime, shown: list[str]) -> None:
        self.raw.append((staff_id, at, AccessKind.SEARCH, tuple(shown), None, 0))

    def _make_normal_accesses(self) -> None:
        sections = [Section.SUMMARY, Section.NOTES, Section.RESULTS, Section.MEDICINES]
        period = [e for e in self.encounters if e.start >= START]
        for encounter in period:
            for staff_id in encounter.staff:
                for look in range(self.rng.randint(2, 3)):
                    at = encounter.start + timedelta(minutes=self.rng.randint(-20, 40) + look * 7)
                    lab = self._person(staff_id).role is Role.LAB_TECHNICIAN
                    section = Section.RESULTS if lab else self.rng.choice(sections)
                    self._open(staff_id, at, encounter.patient, section, self.rng.randint(20, 400))
        front_desk = self._by(Role.FRONT_DESK)
        billing = self._by(Role.BILLING)
        ordinary = [p.id for p in self.patients if p.id not in self.staff_records.values()]
        for day_index in range(DAYS):
            day = _day(day_index)
            if day.weekday() >= 5:
                continue
            soon = sorted({a.patient for a in self.appointments if abs((a.start.date() - day).days) <= 13})
            for desk_index, desk in enumerate(front_desk):
                for n, patient in enumerate(self.rng.sample(soon, min(len(soon), 22))):
                    at = _at(day, 8 + (n * 23 + desk_index * 11) // 60, (n * 23 + desk_index * 11) % 60)
                    others = self.rng.sample([p for p in ordinary if p != patient], 3)
                    self._search(desk.id, at, sorted([patient, *others]))
                    self._open(
                        desk.id,
                        at + timedelta(seconds=40),
                        patient,
                        Section.SUMMARY,
                        self.rng.randint(15, 90),
                    )
            recent = sorted(
                {
                    e.patient
                    for e in self.encounters
                    if timedelta(0) < day - e.end.date() <= timedelta(days=89)
                }
            )
            for clerk_index, clerk in enumerate(billing):
                for n, patient in enumerate(self.rng.sample(recent, min(len(recent), 18))):
                    minute = n * 25 + clerk_index * 7
                    self._open(
                        clerk.id,
                        _at(day, 8 + minute // 60, minute % 60),
                        patient,
                        Section.BILLING,
                        self.rng.randint(30, 200),
                    )
            # Physicians look at their care-team patients' results between visits.
            for doctor in self._by(Role.PHYSICIAN, Department.FAMILY_MEDICINE):
                panel = sorted(p for p, members in self.team.items() if doctor.id in members)
                for n, patient in enumerate(self.rng.sample(panel, 4)):
                    self._open(
                        doctor.id, _at(day, 13 + n, 10), patient, Section.RESULTS, self.rng.randint(20, 120)
                    )

    # ---- planted cases ----

    def _label(
        self,
        planted: bool,
        kind: str,
        staff_id: str,
        patient: str | None,
        day: date,
        rules: list[str],
        note: str,
    ) -> None:
        prefix = "C" if planted else "L"
        number = sum(1 for label in self.labels if label.planted == planted) + 1
        self.labels.append(
            Label(f"{prefix}{number:02d}", planted, kind, staff_id, patient, day, tuple(rules), note)
        )

    def _snoop(self, staff_id: str, patient: str, at: datetime) -> None:
        assert not self._related(staff_id, patient, at), (staff_id, patient)
        sections = [Section.SUMMARY, Section.NOTES, Section.RESULTS]
        for look in range(self.rng.randint(1, 3)):
            self._open(
                staff_id, at + timedelta(minutes=look * 4), patient, sections[look], self.rng.randint(40, 420)
            )

    def _stranger(self, staff_id: str, at: datetime, exclude: set[str]) -> str:
        """An ordinary patient nothing links to `staff_id`."""
        candidates = [
            p.id
            for p in self.patients[:283]
            if p.id not in exclude
            and p.deceased_at is None
            and p.id not in self.vips
            and not self._related(staff_id, p.id, at)
            and not any(m.patient == p.id and m.staff == staff_id for m in self.care_teams)
        ]
        return self.rng.choice(candidates)

    def _plant(self) -> None:
        used: set[str] = set()
        days = [d for d in (_day(i) for i in range(DAYS)) if d.weekday() < 5]

        # Co-workers: four staff open another staff member's record.
        for n, (snooper, owner) in enumerate(
            [("S-002", "S-011"), ("S-008", "S-019"), ("S-013", "S-022"), ("S-005", "S-016")]
        ):
            record = self.staff_records[owner]
            day = days[n * 2]
            self._snoop(snooper, record, _at(day, 10 + n, 5))
            self._label(
                True,
                "co-worker",
                snooper,
                record,
                day,
                ["NO_RELATIONSHIP", "COWORKER"],
                f"opens the record of co-worker {owner}",
            )

        # Relatives at the same address: two share the staff member's last name, two don't.
        for n, snooper in enumerate(["S-009", "S-014", "S-003", "S-021"]):
            person = self._person(snooper)
            same_name = n < 2
            family = person.family if same_name else PATIENT_FAMILY_NAMES[-1 - n]
            relative = self._new_patient(
                GIVEN_NAMES[n * 7 % len(GIVEN_NAMES)], family, person.address, date(1958 + n * 9, 3, 2)
            )
            self._care_for(relative.id)
            day = days[1 + n * 2]
            self._snoop(snooper, relative.id, _at(day, 11, 20))
            rules = (
                ["NO_RELATIONSHIP", "SAME_LAST_NAME", "SAME_ADDRESS"]
                if same_name
                else ["NO_RELATIONSHIP", "SAME_ADDRESS"]
            )
            self._label(
                True,
                "relative at the same address",
                snooper,
                relative.id,
                day,
                rules,
                "opens the chart of someone living at their home address",
            )

        # Same last name, different address.
        for n, snooper in enumerate(["S-004", "S-012", "S-018"]):
            person = self._person(snooper)
            namesake = self._new_patient(
                GIVEN_NAMES[(n * 11 + 3) % len(GIVEN_NAMES)],
                person.family,
                Address(f"{700 + n} {PATIENT_STREETS[n]}", CITY, "00071"),
                date(1970 + n * 6, 8, 19),
            )
            self._care_for(namesake.id)
            day = days[2 + n * 3]
            self._snoop(snooper, namesake.id, _at(day, 14, 40))
            self._label(
                True,
                "same last name",
                snooper,
                namesake.id,
                day,
                ["NO_RELATIONSHIP", "SAME_LAST_NAME"],
                "opens the chart of a patient with their last name, no care relationship",
            )

        # VIPs: six patients the clinic marks VIP; four opened by staff with no reason.
        vip_pool = [p.id for p in self.patients[:283] if p.birth_date.year < 2012]
        for patient in self.rng.sample(vip_pool, 6):
            self.vips.add(patient)
        vip_list = sorted(self.vips)
        for n, patient in enumerate(vip_list[:4]):
            day = days[3 + n * 2]
            at = _at(day, 9, 50)
            snooper = next(
                s
                for s in ["S-006", "S-010", "S-012", "S-017", "S-005", "S-014"][n:]
                if not self._related(s, patient, at)
                and not any(m.patient == patient and m.staff == s for m in self.care_teams)
            )
            self._snoop(snooper, patient, at)
            self._label(
                True,
                "VIP",
                snooper,
                patient,
                day,
                ["NO_RELATIONSHIP", "VIP"],
                "opens a VIP's chart with no care relationship",
            )
        used.update(vip_list)

        # Own record: three staff members open their own chart.
        for n, owner in enumerate(["S-011", "S-019", "S-024"]):
            record = self.staff_records[owner]
            day = days[5 + n]
            self._snoop(owner, record, _at(day, 12, 15))
            self._label(True, "own record", owner, record, day, ["OWN_RECORD"], "opens their own chart")

        # Roles that never read charts: two security guards and one IT technician.
        for n, (guard, hour) in enumerate([("S-029", 15), ("S-030", 2), ("S-027", 11)]):
            day = days[6 + n]
            at = _at(day + timedelta(days=1) if hour < 7 else day, hour, 35)
            patient = self._stranger(guard, at, used)
            used.add(patient)
            self._snoop(guard, patient, at)
            self._label(
                True,
                "role that never reads charts",
                guard,
                patient,
                at.date(),
                ["ROLE_NO_CHARTS", "NO_RELATIONSHIP"],
                "a role that never reads charts opens one",
            )

        # Deceased patients, opened by staff with no reason.
        for n, snooper in enumerate(["S-007", "S-020"]):
            patient = self._stranger(snooper, _at(days[0], 9), used)
            used.add(patient)
            self._die(patient, _at(date(2026, 9, 3 + n * 9), 6))
            day = days[4 + n * 3]
            self._snoop(snooper, patient, _at(day, 15, 10))
            self._label(
                True,
                "deceased patient",
                snooper,
                patient,
                day,
                ["NO_RELATIONSHIP", "DECEASED"],
                "opens the chart of a patient who has died",
            )

        # Long after care ended: staff who once cared for a patient look again months later.
        for n, snooper in enumerate(["S-002", "S-008", "S-013"]):
            day = days[7 + n]
            patient = self._stranger(snooper, _at(day, 9), used)
            used.add(patient)
            self.care_teams.append(
                CareTeamMember(patient, snooper, _at(date(2024, 1, 8), 9), _at(date(2026, 6, 30), 17))
            )
            self._snoop(snooper, patient, _at(day, 16, 5))
            self._label(
                True,
                "long after care ended",
                snooper,
                patient,
                day,
                ["NO_RELATIONSHIP", "AFTER_CARE_ENDED"],
                "looks at a former patient months after their care ended",
            )

        # Outside shift: office staff open an unrelated chart at night.
        for n, snooper in enumerate(["S-004", "S-014", "S-025"]):
            day = days[n * 3 + 1]
            at = _at(day, 22, 10 + n)
            patient = self._stranger(snooper, at, used)
            used.add(patient)
            self._snoop(snooper, patient, at)
            self._label(
                True,
                "outside shift",
                snooper,
                patient,
                day,
                ["NO_RELATIONSHIP", "OUTSIDE_SHIFT"],
                "opens an unrelated chart late at night, off shift",
            )

        # Bursts: a billing clerk and a physician open far more charts than usual,
        # every one accounted for by their work.
        clerk_day = days[8]
        recent = sorted(
            {
                e.patient
                for e in self.encounters
                if timedelta(0) < clerk_day - e.end.date() <= timedelta(days=89)
            }
        )
        for n, patient in enumerate(self.rng.sample(recent, 75)):
            self._open("S-023", _at(clerk_day, 9, 0) + timedelta(minutes=n * 4), patient, Section.BILLING, 25)
        self._label(
            True,
            "burst of charts",
            "S-023",
            None,
            clerk_day,
            ["HIGH_VOLUME"],
            "75 charts in one day, each one a recent patient",
        )
        doctor_day = days[4]
        panel = sorted(p for p, members in self.team.items() if "S-001" in members)
        for n, patient in enumerate(self.rng.sample(panel, 65)):
            self._open(
                "S-001", _at(doctor_day, 8, 30) + timedelta(minutes=n * 6), patient, Section.SUMMARY, 20
            )
        self._label(
            True,
            "burst of charts",
            "S-001",
            None,
            doctor_day,
            ["HIGH_VOLUME"],
            "65 of their own patients' charts in one day",
        )

    def _care_for(self, patient: str) -> None:
        doctor = self._by(Role.PHYSICIAN, Department.FAMILY_MEDICINE)[1].id
        self.team[patient] = [doctor]
        self.care_teams.append(CareTeamMember(patient, doctor, _at(date(2024, 3, 1), 9), None))

    def _die(self, patient: str, at: datetime) -> None:
        index = next(i for i, p in enumerate(self.patients) if p.id == patient)
        old = self.patients[index]
        self.patients[index] = replace(old, deceased_at=at)
        # Off every care team's panel, and no visits or bookings after death.
        self.team[patient] = []
        self.encounters = [e for e in self.encounters if not (e.patient == patient and e.start > at)]
        self.appointments = [a for a in self.appointments if not (a.patient == patient and a.start > at)]
        # Charts are not opened after death; a search may still list the patient.
        self.raw = [r for r in self.raw if not (r[2] is AccessKind.CHART and patient in r[3] and r[1] > at)]
        self.care_teams = [
            m if m.patient != patient else CareTeamMember(m.patient, m.staff, m.start, at)
            for m in self.care_teams
        ]

    # ---- innocent look-alikes ----

    def _look_alikes(self) -> None:
        days = [d for d in (_day(i) for i in range(DAYS)) if d.weekday() < 5]
        fm_doctors = self._by(Role.PHYSICIAN, Department.FAMILY_MEDICINE)

        # A shared last name, with a visit that day.
        for n, doctor in enumerate(fm_doctors):
            namesake = self._new_patient(
                GIVEN_NAMES[(n * 5 + 2) % len(GIVEN_NAMES)],
                doctor.family,
                Address(f"{800 + n} {PATIENT_STREETS[4 + n]}", CITY, "00072"),
                date(1966 + n * 4, 2, 11),
            )
            self._care_for(namesake.id)
            day = days[n + 1]
            start = _at(day, 15, 0)
            self._visit(namesake.id, [doctor.id], start, booked=True)
            self._open(doctor.id, start + timedelta(minutes=5), namesake.id, Section.NOTES, 180)
            self._label(
                False,
                "same last name, with a visit",
                doctor.id,
                namesake.id,
                day,
                [],
                "shares the doctor's last name; seen that day",
            )

        # Relatives at the same address, seen by the staff member at a visit.
        for n, doctor in enumerate(fm_doctors[:2]):
            relative = self._new_patient(
                GIVEN_NAMES[(n * 13 + 6) % len(GIVEN_NAMES)],
                PATIENT_FAMILY_NAMES[-5 - n],
                doctor.address,
                date(1990 + n, 7, 7),
            )
            self._care_for(relative.id)
            day = days[n + 6]
            start = _at(day, 16, 0)
            self._visit(relative.id, [doctor.id], start, booked=True)
            self._open(doctor.id, start + timedelta(minutes=2), relative.id, Section.SUMMARY, 140)
            self._label(
                False,
                "same address, with a visit",
                doctor.id,
                relative.id,
                day,
                [],
                "lives at the doctor's address; seen that day",
            )

        # VIPs looked at by their own care team.
        vip_list = sorted(self.vips)
        for n, patient in enumerate(vip_list[:3]):
            doctor = self.team[patient][0]
            day = days[n + 2]
            self._open(doctor, _at(day, 13, 45), patient, Section.RESULTS, 95)
            self._label(
                False,
                "VIP seen by their care team",
                doctor,
                patient,
                day,
                [],
                "a VIP's own doctor reads their results",
            )

        # VIPs shown in a search list, chart never opened.
        desks = self._by(Role.FRONT_DESK)
        for n, patient in enumerate(vip_list[3:6]):
            day = days[n + 3]
            others = [p.id for p in self.patients[:283] if p.id not in self.vips][n * 3 : n * 3 + 3]
            self._search(desks[n].id, _at(day, 10, 12), sorted([patient, *others]))
            self._label(
                False,
                "VIP in a search list only",
                desks[n].id,
                patient,
                day,
                [],
                "a VIP's name appears in a search list; the chart is not opened",
            )

        # Staff members seen as patients by their own care team.
        for n, owner in enumerate(["S-016", "S-022"]):
            record = self.staff_records[owner]
            doctor = self.team[record][0]
            day = days[n + 4]
            self._open(doctor, _at(day, 11, 30), record, Section.RESULTS, 110)
            self._label(
                False,
                "co-worker seen by their care team",
                doctor,
                record,
                day,
                [],
                "a staff member's own doctor reads their chart",
            )

        # A deceased patient's last bill, within 90 days of the visit.
        clerk = self._by(Role.BILLING)[1].id
        labelled = {label.patient for label in self.labels}
        patient = next(
            p
            for p in self.patients[:283]
            if p.id not in self.vips
            and p.deceased_at is None
            and p.id not in labelled
            and any(
                e.patient == p.id and START - timedelta(days=60) <= e.start < START for e in self.encounters
            )
        )
        last_visit = max(e.end for e in self.encounters if e.patient == patient.id and e.start < START)
        self._die(patient.id, last_visit + timedelta(days=5))
        day = days[5]
        self._open(clerk, _at(day, 10, 40), patient.id, Section.BILLING, 160)
        self._label(
            False,
            "deceased patient's bill",
            clerk,
            patient.id,
            day,
            [],
            "billing closes the account of a patient who died after a recent visit",
        )

        # A doctor checks their own patients' results late in the evening.
        for n, doctor in enumerate(fm_doctors[:2]):
            panel = sorted(
                p for p, members in self.team.items() if doctor.id in members and p not in self.vips
            )
            patient = panel[n * 5]
            day = days[n + 7]
            self._open(doctor.id, _at(day, 21, 30), patient, Section.RESULTS, 75)
            self._label(
                False,
                "after hours, own patient",
                doctor.id,
                patient,
                day,
                [],
                "a doctor reads their own patient's results after hours",
            )

        # Covering nurses: helping at a visit nobody recorded them on. These are
        # innocent but the data can't show it, so they are flagged: false alarms.
        nurses = self._by(Role.NURSE, Department.FAMILY_MEDICINE)
        for n, nurse in enumerate(nurses):
            day = days[n + 2]
            visit = next(
                e
                for e in self.encounters
                if e.start.date() == day
                and e.patient not in self.vips
                and len(e.staff) > 1
                and not self._related(nurse.id, e.patient, e.start)
                and self._clean_stranger(nurse.id, e.patient)
            )
            self._open(nurse.id, visit.start + timedelta(minutes=10), visit.patient, Section.MEDICINES, 60)
            self._label(
                False,
                "covering nurse",
                nurse.id,
                visit.patient,
                day,
                ["NO_RELATIONSHIP"],
                "covers a colleague's visit; the record doesn't show it (a false alarm)",
            )

        # Front desk opens a chart to confirm a booking ten days ahead.
        booking = next(
            a
            for a in self.appointments
            if 8 <= (a.start.date() - days[2]).days <= 12 and a.patient not in self.vips
        )
        self._open(desks[3].id, _at(days[2], 15, 5), booking.patient, Section.SUMMARY, 30)
        self._label(
            False,
            "booking ten days ahead",
            desks[3].id,
            booking.patient,
            days[2],
            [],
            "the front desk confirms an appointment ten days away",
        )

        # A staff member's own record shows in a search list they ran.
        owner = "S-016"
        record = self.staff_records[owner]
        others = [p.id for p in self.patients[:283] if p.id not in self.vips][40:42]
        self._search(owner, _at(days[3], 14, 0), sorted([record, *others]))
        self._label(
            False,
            "own name in a search list",
            owner,
            record,
            days[3],
            [],
            "their own record appears in a search list they ran; not opened",
        )

    def _clean_stranger(self, staff_id: str, patient: str) -> bool:
        """No name, address, co-worker, former-care or death link to the staff member."""
        person = self._person(staff_id)
        record = next(p for p in self.patients if p.id == patient)
        return (
            record.family != person.family
            and record.address != person.address
            and patient not in self.staff_records.values()
            and record.deceased_at is None
            and not any(m.patient == patient and m.staff == staff_id for m in self.care_teams)
        )

    def _number_accesses(self) -> tuple[Access, ...]:
        ordered = sorted(self.raw, key=lambda r: (r[1], r[0], r[2], r[3]))
        workstation = {s.id: f"WS-{s.department.name[:4]}-{int(s.id[2:]) % 4 + 1:02d}" for s in self.staff}
        return tuple(
            Access(f"A-{n:05d}", staff_id, at, kind, patients, section, seconds, workstation[staff_id])
            for n, (staff_id, at, kind, patients, section, seconds) in enumerate(ordered, start=1)
        )
