-- The clinic as read from its FHIR server: staff, patients, care and the access log.
create table staff (
    id text primary key,
    given text not null,
    family text not null,
    role text not null,
    department text not null,
    address_line text not null,
    city text not null,
    postal_code text not null
);

create table patients (
    id text primary key,
    given text not null,
    family text not null,
    birth_date date not null,
    address_line text not null,
    city text not null,
    postal_code text not null,
    deceased_at timestamptz
);

create table care_team_members (
    patient text not null references patients (id),
    staff text not null references staff (id),
    start_at timestamptz not null,
    end_at timestamptz,
    primary key (patient, staff, start_at)
);

create table encounters (
    id text primary key,
    patient text not null references patients (id),
    staff text[] not null,
    start_at timestamptz not null,
    end_at timestamptz not null
);

create table appointments (
    id text primary key,
    patient text not null references patients (id),
    staff text not null references staff (id),
    start_at timestamptz not null,
    end_at timestamptz not null
);

create table accesses (
    id text primary key,
    staff text not null references staff (id),
    at timestamptz not null,
    kind text not null check (kind in ('chart opened', 'search list')),
    patients text[] not null,
    section text,
    seconds integer not null,
    workstation text not null
);
create index accesses_patients on accesses using gin (patients);
create index accesses_staff_at on accesses (staff, at);

-- Every version of the clinic's rules; a change adds a version, never edits one.
create table rule_set_versions (
    version integer primary key,
    settings jsonb not null,
    created_at timestamptz not null,
    created_by text not null
);

-- Cases: one per staff member and patient, or one per staff member and day for high volume.
create table cases (
    id bigserial primary key,
    staff text not null references staff (id),
    patient text references patients (id),
    day date,
    flagged_at timestamptz not null,
    check ((patient is null) <> (day is null))
);

-- One rule firing on one access under one rule-set version; never changed.
create table flags (
    id bigserial primary key,
    access text not null references accesses (id),
    code text not null,
    version integer not null references rule_set_versions (version),
    weight integer not null,
    case_id bigint not null references cases (id),
    flagged_at timestamptz not null,
    unique (access, code, version)
);
create index flags_case on flags (case_id);

-- The privacy officer's decisions; a later one adds to the history.
create table decisions (
    id bigserial primary key,
    case_id bigint not null references cases (id),
    outcome text not null check (outcome in ('appropriate', 'follow-up', 'possible breach')),
    reason text not null check (char_length(btrim(reason)) >= 10),
    decided_by text not null,
    decided_at timestamptz not null
);
create index decisions_case on decisions (case_id);

-- Every step, append-only: the database refuses to change or delete an entry.
create table audit_events (
    id bigserial primary key,
    at timestamptz not null,
    actor text not null,
    action text not null,
    subject_type text not null,
    subject_id text not null,
    details jsonb not null default '{}'
);

create function refuse_change() returns trigger language plpgsql as $$
begin
    raise exception '% is append-only', tg_table_name;
end;
$$;

create trigger audit_events_append_only before update or delete on audit_events
    for each row execute function refuse_change();
create trigger audit_events_no_truncate before truncate on audit_events
    for each statement execute function refuse_change();
create trigger decisions_append_only before update or delete on decisions
    for each row execute function refuse_change();
create trigger decisions_no_truncate before truncate on decisions
    for each statement execute function refuse_change();
create trigger flags_append_only before update or delete on flags
    for each row execute function refuse_change();
