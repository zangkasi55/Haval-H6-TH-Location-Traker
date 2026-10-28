# Contributing

Read [development](docs/development.md), [privacy](docs/privacy.md) and
[journey limitations](docs/journeys.md) first.

- Use synthetic observations only. Never commit account/device credentials,
  source storage, a live HA backup, real routes or personal images.
- Preserve the local-only read boundary, explicit unknown states and fixed
  seven-day retention. No wake/control endpoint or second cloud login belongs
  in this companion.
- A new power mapping needs source evidence and end-to-end tests, not a constant
  name or a petrol-engine proxy. Do not label an unverified stop as parking.
- Add focused tests, run existing lint/type/frontend/browser checks and update
  directly affected manuals.
- Keep MIT attribution and map-library/data notices.

Open a reproducible issue or pull request. Maintainers may request independent
model/firmware validation; synthetic tests do not certify every Thailand vehicle.
