# Development, diagrams and sample screens

## Stack

- Python 3.14, Home Assistant config flow/coordinator/storage/WebSocket APIs.
- Vanilla JavaScript Web Component, Leaflet 1.9.4, Protomaps Leaflet 5.1.0,
  PMTiles 3.2.1; local esbuild bundle.
- pytest/pytest-asyncio, Ruff and strict mypy.
- Node test runner and actual Playwright/Leaflet browser regressions.

The source adapter is the only integration-compatibility boundary. It reads a
loaded normalized source coordinator, filters the exact configured vehicle and
projects allowlisted values. It never imports the source authentication SDK,
calls a source refresh, stores credentials or creates a second cloud client.

## Build and validate

Use the repository's declared development dependencies in an isolated environment:

```text
python -m venv .venv
python -m pip install -r requirements-dev.txt
npm ci
python -m pytest -q
python -m ruff check custom_components tests scripts
python -m mypy custom_components/haval_h6_th_location_tracker
npm test
npm run build:map
npm run test:browser
python scripts/check_public_tree.py
python scripts/build_release.py
```

Activate the virtual environment before running the commands. On Windows,
executables are under `.venv\Scripts`; in CI the runner selects Python directly.
Install Playwright's browser with `npx playwright install --with-deps chromium`
on Linux when needed; local Windows checks use the installed Edge channel.

The archive is created under `dist/<version>/`, contains the component and
license/install metadata, and is verified with SHA-256. Build refuses to overwrite
an existing archive. No map country archive, app binary or account material is
packaged.

## Reproduce the sample screens

```text
python scripts/generate_journey_demo.py
npm run docs:screenshots
```

The generator uses the **production classifier** with fixed fictional input.
The browser uses the **production card** with a tiny generated fictional
PMTiles/MVT archive on loopback. All external browser requests are blocked.
It produces:

- `docs/images/setup.png`: labelled setup illustration, not a live HA account.
- `docs/images/journeys.png`: fictional current marker, trail and battery popup.
- `docs/images/stops.png`: sampled door/battery stop details.
- `docs/images/no-gps.png`: genuine blank-current state with no invented city.
- An original neutral `brand/icon.png`, not OEM artwork.

Current demo timestamps are shifted only inside the explicitly synthetic demo.
Production code never shifts manufacturer timestamps to make a fix fresh.

Architecture, sequence and parking-state Mermaid diagrams are in the README
and [journey manual](journeys.md). GitHub renders their source directly.

## Validation boundary

Tests cover source/domain/vehicle binding, read-only ingestion, missing/stale
fields, admin/device permissions, deletion, seven-day timer pruning/storage
errors, movement/parking uncertainty and real map lifecycle behavior.

No CI account, car, live HA endpoint or owner journey is used. Synthetic tests
are evidence of software behavior, not proof of a physical parking event.
Run all three publication workflows (Checks, Hassfest, HACS) before a full
release or catalog submission.
