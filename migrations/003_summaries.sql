-- Each summary the model wrote for a case: the facts it was given, its answer,
-- and whether the checks let a person see it. Never changed once written.
create table summaries (
    id bigserial primary key,
    case_id bigint not null references cases (id),
    model text not null,
    request_hash text not null,
    facts jsonb not null,
    answer jsonb,
    status text not null check (status in ('shown', 'blocked', 'unreadable')),
    problems jsonb not null default '[]',
    written_at timestamptz not null
);
create index summaries_case on summaries (case_id, id);

create trigger summaries_append_only before update or delete on summaries
    for each row execute function refuse_change();
create trigger summaries_no_truncate before truncate on summaries
    for each statement execute function refuse_change();
