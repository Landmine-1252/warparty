# Warparty

Warparty is a small private web app for coordinating Diablo-style War Plan routes with a party. Each player joins a private party, enters their own ordered War Plan, tracks only their own progress, and follows a recommended shared route so the group completes everyone plans with fewer practical activity runs.

Warparty is not affiliated with Blizzard Entertainment.

## Features

- Create a private Warparty with an invite URL and short invite code.
- Join up to four players by default.
- Keep each browser tied to one player identity with a private session cookie.
- Manually enter War Plans from the supported activity set.
- Mark only the current activity complete and undo only the most recent completion.
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
cd warparty-python
./scripts/dev-start.sh
```

On Windows:

```bat
cd warparty-python
scripts\dev-start.bat
```

The app runs at <http://localhost:8080>. Local data is stored in `App_Data/warparty.db`.
The Windows script uses `.venv-win` so it does not conflict with a Linux/WSL `.venv`. The start scripts keep uvicorn attached to the current terminal so you can see live logs. Press `Ctrl+C` to stop.

## Manual Local Commands

```bash
uv venv --python 3.12
uv sync --extra dev
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
  -e WARPARTY_SECRET_KEY=change-this-secret \
  -v warparty-data:/app/App_Data \
  warparty
```

Or use Compose:

```bash
docker compose up --build
```

## Configuration

| Variable | Default | Notes |
| --- | --- | --- |
| `WARPARTY_PUBLIC_BASE_URL` | `http://localhost:8080` | Used to build invite links. |
| `WARPARTY_DATABASE_PATH` | `/app/App_Data/warparty.db` | SQLite database file path. |
| `WARPARTY_DATA_DIR` | `/app/App_Data` | Runtime data directory. |
| `WARPARTY_MAX_PLAYERS_PER_PARTY` | `4` | Maximum party slots. |
| `WARPARTY_SECRET_KEY` | generated in development | Required when `WARPARTY_ENV=production`. |
| `WARPARTY_ENV` | `development` | Set to `production` for container deployments. |

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

## Notes

Real-time updates are in-process. They work for single-container deployments, but they are not distributed across multiple containers. Add Redis, Postgres pub/sub, or another shared event bus before scaling horizontally.
