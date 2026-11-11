-- The tool's own users: the privacy officer and the administrator.
create table users (
    id serial primary key,
    email text not null unique,
    name text not null,
    role text not null check (role in ('privacy officer', 'administrator'))
);

-- Login links (used once, 15 minutes) and sessions (12 hours). Only hashes are stored.
create table login_tokens (
    token_hash text primary key,
    who text not null check (who in ('user', 'patient')),
    person_id text not null,
    created_at timestamptz not null,
    expires_at timestamptz not null,
    used_at timestamptz
);

create table sessions (
    secret_hash text primary key,
    who text not null check (who in ('user', 'patient')),
    person_id text not null,
    created_at timestamptz not null,
    expires_at timestamptz not null
);
