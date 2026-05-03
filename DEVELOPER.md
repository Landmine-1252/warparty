# Developer Notes

## Local Setup

Use Python 3.12 or newer and `uv`.

```bash
uv venv --python 3.12
uv sync --extra dev
uv run uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
```

Convenience scripts:

- Linux/macOS start: `./scripts/dev-start.sh`
- Windows start: `scripts\dev-start.bat`

The Linux/macOS script creates or reuses `.venv`. The Windows script creates or reuses `.venv-win` to avoid conflicts with WSL/Linux virtual environments. Both start uvicorn in the current terminal so logs stay visible and `Ctrl+C` stops the server.

## Checks

```bash
uv run ruff check .
uv run black --check .
uv run pytest
```

Format code:

```bash
uv run black .
uv run ruff check . --fix
```

## Project Structure

```text
app/
  main.py              FastAPI app setup
  config.py            environment settings
  database.py          SQLAlchemy engine/session setup
  models.py            SQLite ORM models
  constants.py         supported activity definitions
  planner.py           route planner
  realtime.py          in-process WebSocket manager
  services/            business rules and serializers
  routers/             HTML, JSON API, and WebSocket routes
  templates/           Jinja2 pages and partials
  static/              Pure.css subset and Warparty theme CSS
tests/                 planner, progress, party flow, realtime tests
scripts/               local uv start scripts
```

## Planner Notes

The planner treats every War Plan as an ordered list and searches over player progress states. A move is one activity run. A player advances only when that activity matches their current step.

The BFS minimizes total remaining activity runs. Candidate moves are ordered by:

1. Most players advanced.
2. Fewest waiting players.
3. Stable activity order from `app.constants.ACTIVITY_ORDER`.

Route rows are tagged as:

- `shared` when multiple players advance.
- `solo` when exactly one player advances and no one waits.
- `sync` when exactly one player advances while other active players wait.

## Progress Rules

`progress_index` is the number of completed activities. The current step is `activities[progress_index]`, and the plan is complete when `progress_index >= len(activities)`.

The service layer only exposes one-step progress operations:

- `mark_current_complete` increments by one.
- `undo_last_progress` decrements by one.

Future steps are not directly addressable from the UI or API.

## Real-Time Updates

The party room connects to `/ws/party/{party_id}`. Mutating route handlers broadcast:

```json
{
  "type": "party_updated",
  "party_id": "...",
  "reason": "warplan_saved"
}
```

The browser reloads the page after a short debounce. This is intentionally simple and reliable for single-container deployments. Multi-container deployments need a shared pub/sub layer.

## Docker

Build locally:

```bash
docker build -t warparty .
```

Run locally:

```bash
docker run --rm -p 8080:8080 \
  -e WARPARTY_PUBLIC_BASE_URL=http://localhost:8080 \
  -e WARPARTY_SECRET_KEY=change-this-secret \
  -v warparty-data:/app/App_Data \
  warparty
```

Compose:

```bash
docker compose up --build
```

The app listens on port `8080` and persists SQLite data in `/app/App_Data`.

## Container Publishing

`.github/workflows/container.yml` publishes multi-architecture images to GHCR on semantic version tags. For `https://github.com/Landmine-1252/warparty`, the image name is:

```text
ghcr.io/landmine-1252/warparty
```

The workflow also adds OCI labels, uses GitHub Actions cache, and creates a build provenance attestation.

## Current Limitations

- No Alembic migrations yet; first version uses `Base.metadata.create_all`.
- WebSocket updates are in-process and single-container only.
- Session cookies store `player_id:token`; only the token hash is persisted in SQLite.
