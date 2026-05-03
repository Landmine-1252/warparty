# Warparty

Warparty is a small private web app for coordinating Diablo-style War Plan routes with a party. Each player joins a private party, enters their own ordered War Plan, tracks only their own progress, and follows a recommended shared route so the group completes everyone's plans with fewer practical activity runs.

Warparty is not affiliated with Blizzard Entertainment.

## Features

- Create a private Warparty with an invite URL and short invite code.
- Join up to four players by default.
- Keep each browser tied to one player identity with a private session cookie.
- Remember the last player name locally to pre-fill future create and join forms.
- Let the party leader remove stale members so open slots can be reused. Removing a player rotates the invite code.
- Let non-leaders leave a party and let leaders transfer leadership before leaving.
- Copy one invite message that includes both the invite URL and short code.
- Manually enter War Plans from the supported activity set.
- Mark progress through your own selected activity level, or click completed levels to roll back your own progress.
- Recalculate the recommended route from persisted player progress.
- Push real-time party update events over WebSockets and reload connected rooms.
- Store data in SQLite with no Redis or external database requirement.

Supported activities:

- Helltide
- Pit
- Nightmare Dungeon
- Infernal Hordes
- Lair Boss
- Kurast Undercity

## Run Locally With uv

Install `uv`, then start the dev server:

```bash
./scripts/dev-start.sh
```

On Windows:

```bat
scripts\dev-start.bat
```

The app runs at <http://localhost:8080>. Local data is stored in `App_Data/warparty.db`.
The Windows script uses `.venv-win` so it does not conflict with a Linux/WSL `.venv`. The start scripts keep uvicorn attached to the current terminal so you can see live logs. Press `Ctrl+C` to stop.

## Manual Local Commands

```bash
uv venv --python 3.12
uv sync --extra dev
WARPARTY_DATA_DIR=./App_Data \
WARPARTY_DATABASE_PATH=./App_Data/warparty.db \
uv run uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
```

Run checks:

```bash
uv run ruff check .
uv run black --check .
uv run pytest
```

## Docker

Build and run:

```bash
docker build -t warparty .
docker run --rm -p 8080:8080 \
  -e WARPARTY_PUBLIC_BASE_URL=http://localhost:8080 \
  -v warparty-data:/data \
  warparty
```

Or use Compose:

```bash
docker compose up --build
```

The container listens on port `8080`, runs as non-root UID/GID `10001`, and stores mutable runtime data in `/data`.

## Podman

Named volumes work well with rootless Podman:

```bash
podman build -t warparty .
podman volume create warparty-data
podman run --rm -p 8080:8080 \
  -e WARPARTY_PUBLIC_BASE_URL=http://localhost:8080 \
  -v warparty-data:/data \
  warparty
```

For a rootless Podman bind mount on SELinux systems, use `:Z` and run as your host user:

```bash
mkdir -p ./data
podman run --rm --userns keep-id --user "$(id -u):$(id -g)" \
  -p 8080:8080 \
  -e WARPARTY_PUBLIC_BASE_URL=http://localhost:8080 \
  -v "$(pwd)/data:/data:Z" \
  warparty
```

### Bind Mounts

Docker and Podman named volumes work without extra setup. If you use a host bind mount, the mounted directory must be writable by UID/GID `10001`, or you must run the container with a `--user` value that can write to that host directory.

Example bind mount:

```bash
mkdir -p ./data
chown -R 10001:10001 ./data
docker run --rm -p 8080:8080 \
  -e WARPARTY_PUBLIC_BASE_URL=http://localhost:8080 \
  -v "$(pwd)/data:/data:rw" \
  ghcr.io/landmine-1252/warparty:latest
```

`PUID` and `PGID` environment variables are not used by this image. Use Docker/Podman `--user`, or fix ownership on the mounted host directory.

## Unraid

Recommended Unraid settings:

- Container port: `8080`
- Host port: any free port, for example `5150`
- Container path: `/data`
- Host path: `/mnt/user/appdata/warparty`
- Access mode: read/write
- `WARPARTY_PUBLIC_BASE_URL`: your external URL, for example `https://warparty.example.com`
- `WARPARTY_ALLOWED_HOSTS`: your public host plus local hosts, for example `warparty.example.com,localhost,127.0.0.1`

Warparty accepts both `WARPARTY_PUBLIC_BASE_URL` and the older `.NET`-style `Warparty__PublicBaseUrl`, but the uppercase `WARPARTY_` name is preferred.

If startup logs say SQLite is unable to open the database file, the `/data` mount is not writable by the container. Fix it with one of these approaches:

```bash
chown -R 10001:10001 /mnt/user/appdata/warparty
```

Or run the container as Unraid's usual appdata owner by adding this to Extra Parameters:

```text
--user 99:100
```

If you use `--user 99:100`, make sure `/mnt/user/appdata/warparty` is writable by `nobody:users`.

## Configuration

| Variable | Default | Notes |
| --- | --- | --- |
| `WARPARTY_PUBLIC_BASE_URL` | `http://localhost:8080` | Used to build invite links. |
| `WARPARTY_DATABASE_PATH` | `/data/warparty.db` in containers | SQLite database file path. |
| `WARPARTY_DATA_DIR` | `/data` in containers | Runtime data directory for the database and generated secret. |
| `WARPARTY_MAX_PLAYERS_PER_PARTY` | `4` | Maximum party slots. |
| `WARPARTY_SECRET_KEY` | unset | Optional override. If unset, a persistent secret is created in `WARPARTY_SECRET_KEY_FILE`. |
| `WARPARTY_SECRET_KEY_FILE` | `<data_dir>/secret_key` | File used for the generated persistent secret. |
| `WARPARTY_COOKIE_SECURE` | true for HTTPS public URLs | Forces the session cookie `Secure` flag. |
| `WARPARTY_ALLOWED_HOSTS` | public host, `localhost`, `127.0.0.1` | Comma-separated Host header allow-list. Use `*` only for trusted local testing. |
| `WARPARTY_LOG_LEVEL` | `info` | Uvicorn/application log level. |
| `WARPARTY_PORT` | `8080` | Container listen port. |
| `WARPARTY_SQLITE_BUSY_TIMEOUT_MS` | `5000` | SQLite lock wait timeout. |
| `WARPARTY_SQLITE_WAL` | `true` | Enables SQLite WAL mode. |
| `WARPARTY_STALE_PLAYER_MINUTES` | `60` | Age after which leader controls treat a player as stale. |
| `WARPARTY_AUTO_MIGRATE_LEGACY_DATA` | `true` | Copies old `/app/App_Data` database and secret files into the configured data path if the new files are missing. |
| `WARPARTY_LEGACY_DATA_DIR` | `/app/App_Data` | Legacy data path checked during one-time upgrade adoption. |
| `WARPARTY_ENV` | `development` | Set to `production` for container deployments. |

## Healthcheck

- Liveness: `GET /healthz`
- Readiness: `GET /readyz`

`/readyz` performs a lightweight SQLite query.

## SQLite Storage

SQLite is intended for a single Warparty container with modest traffic. It is not a multi-writer clustered database. Move to PostgreSQL or another server database before running multiple app containers, deploying across hosts, needing high availability, or expecting sustained concurrent writes.

Warparty enables SQLite foreign keys, WAL mode, `synchronous=NORMAL`, and a configurable busy timeout. Keep writes short and keep the database on local persistent storage, not a network filesystem if you can avoid it.

### Backup

The safest backup is taken while the container is stopped:

```bash
docker stop warparty
cp /path/to/data/warparty.db ./warparty.db.backup
cp /path/to/data/secret_key ./secret_key.backup
docker start warparty
```

If the container is running in WAL mode, also include `warparty.db-wal` and `warparty.db-shm` if they exist, or stop the container first.

### Restore

Stop the container, replace `warparty.db` and `secret_key` in the mounted data directory, then start the container. Restoring the `secret_key` keeps existing browser sessions and CSRF tokens consistent.

### Upgrade

Pull the new image, stop the old container, back up `/data`, then start the new container with the same volume. This first version uses SQLAlchemy `create_all`; future schema migrations should be handled before more complex releases.

Older Warparty images used `/app/App_Data`. Current images use `/data`. On startup, Warparty checks `/app/App_Data` and copies `warparty.db`, `warparty.db-wal`, `warparty.db-shm`, and `secret_key` into the configured data path only when the target files do not already exist. This is enabled by `WARPARTY_AUTO_MIGRATE_LEGACY_DATA=true` and never overwrites an existing database.

That compatibility copy only works if the old data is still visible inside the container. The safest upgrade path is still:

```bash
docker stop warparty
cp -a /path/to/current/data ./warparty-data-backup
docker pull ghcr.io/landmine-1252/warparty:latest
docker run ... -v /path/to/current/data:/data ...
```

If your existing host mount points at old data, either move/copy the host directory contents to the new `/data` mount location, or keep using the old path explicitly:

```bash
-v /path/to/old-data:/app/App_Data \
-e WARPARTY_DATA_DIR=/app/App_Data \
-e WARPARTY_DATABASE_PATH=/app/App_Data/warparty.db
```

## Troubleshooting

- `unable to open database file`: `/data` is missing or not writable by the container user.
- `database is locked`: verify only one app container is using the SQLite file, keep the database on local storage, and increase `WARPARTY_SQLITE_BUSY_TIMEOUT_MS` if needed.
- Login/session issues behind HTTPS: set `WARPARTY_PUBLIC_BASE_URL` to the `https://` URL and leave `WARPARTY_COOKIE_SECURE` enabled.
- Reverse proxy issues: proxy WebSockets for `/ws/...`, preserve `Host`, and set `WARPARTY_ALLOWED_HOSTS` to the public host.

## Publishing

The container workflow publishes to GitHub Container Registry from semantic version tags:

- `v1.2.3`
- `1.2.3`
- `v1.2.3-rc.1`
- `1.2.3-rc.1`

For the GitHub project `https://github.com/Landmine-1252/warparty`, the image is published as:

```text
ghcr.io/landmine-1252/warparty
```

If GHCR rejects the push with `permission_denied: write_package`, open the package settings for `ghcr.io/landmine-1252/warparty` and grant this repository write access under Actions access.

## Notes

Real-time updates are in-process. They work for single-container deployments, but they are not distributed across multiple containers. Add Redis, Postgres pub/sub, or another shared event bus before scaling horizontally.
