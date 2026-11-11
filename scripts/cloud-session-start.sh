#!/usr/bin/env bash
# SessionStart hook: prepares a Claude Code on the web session: commit
# signing, Postgres, Mailpit and HAPI FHIR in Docker, and the Python tools.
# Does nothing on a developer's own machine.
set -uo pipefail
[ -n "${CLAUDE_CODE_REMOTE:-}" ] || exit 0
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0

# Signs commits with the SSH key in GIT_SIGNING_KEY_B64 (registered on GitHub
# as a signing key), so every commit shows as verified. The key lives outside
# the repository, never in it.
if [ -n "${GIT_SIGNING_KEY_B64:-}" ]; then
    command -v ssh-keygen >/dev/null || { apt-get update -qq && apt-get install -y -qq openssh-client; } >/dev/null 2>&1
    key="$HOME/.ssh/cloud_signing"
    mkdir -p "$HOME/.ssh" && chmod 700 "$HOME/.ssh"
    (umask 077; printf '%s' "$GIT_SIGNING_KEY_B64" | base64 -d >"$key") && chmod 600 "$key"
    git config --local user.name Enriquez-Johnmark
    git config --local user.email enriquezjohnmark15@gmail.com
    git config --local gpg.format ssh
    git config --local gpg.ssh.program ssh-keygen
    git config --local user.signingkey "$key"
    git config --local commit.gpgsign true
fi
[ -f .env ] || cp .env.example .env
log() { echo "cloud-session-start: $*" >&2; }

# The cloud VM has Docker installed but doesn't always start the daemon.
if ! docker info >/dev/null 2>&1; then
    nohup dockerd >/tmp/dockerd.log 2>&1 &
    for _ in $(seq 1 30); do docker info >/dev/null 2>&1 && break; sleep 1; done
fi

port_open() { (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }

# Docker Hub rate-limits anonymous pulls (429); mirror.gcr.io serves the same
# official images, so pull from there and give them their usual names.
pull() {
    docker image inspect "$1" >/dev/null 2>&1 && return
    docker pull -q "$1" >/dev/null 2>&1 && return
    case "$1" in */*) mirror="mirror.gcr.io/$1" ;; *) mirror="mirror.gcr.io/library/$1" ;; esac
    docker pull -q "$mirror" >/dev/null 2>&1 && docker tag "$mirror" "$1"
}

# Another project in this session may already run Postgres on 5432, Mailpit
# on 8025 and HAPI on 8090: use them, adding this project's role and database.
services=()
if port_open 5432; then
    container=$(docker ps --filter publish=5432 --format '{{.Names}}' | head -1)
    if [ -n "$container" ]; then
        admin=$(docker exec "$container" printenv POSTGRES_USER 2>/dev/null || echo postgres)
        docker exec "$container" psql -U "$admin" -d postgres -qc \
            "create role record_access login createdb password 'record_access'" >/dev/null 2>&1
        docker exec "$container" psql -U "$admin" -d postgres -qc \
            "create database record_access owner record_access" >/dev/null 2>&1
    fi
else
    services+=(postgres)
fi
port_open 8025 || services+=(mailpit)
port_open 8090 || services+=(hapi)
for service in "${services[@]}"; do
    case "$service" in
        postgres) pull postgres:17 ;;
        mailpit) pull axllent/mailpit:v1.27.11 ;;
        hapi) pull hapiproject/hapi:v8.4.0-1 ;;
    esac
done
if [ ${#services[@]} -gt 0 ] && ! docker compose --profile fhir up -d "${services[@]}" >/dev/null 2>&1; then
    log "docker compose failed; database and FHIR tests will not run"
fi

# The cloud proxy's certificate is in the system store, which uv reads with this.
export UV_SYSTEM_CERTS=1
unset UV_NATIVE_TLS
command -v uv >/dev/null || pip install -q "uv==0.11.32" >/dev/null 2>&1 || log "installing uv failed"
uv sync -q || log "uv sync failed; the checks will not run"
(cd web && pnpm install --frozen-lockfile >/tmp/cloud-session-start-web.log 2>&1) || log "pnpm install failed in web/"
exit 0
