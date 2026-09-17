# Bravies Homz MVP prototype

This folder preserves the original local Node/Express prototype that informed
the Bravies Homz staff dashboard. It is included for product reference and
local demonstrations only; the deployable application is the FastAPI service
in `../backend`.

## What is intentionally excluded

- `node_modules/` — install locally with `npm install` when needed.
- `.env` — secrets never belong in source control.
- `leads.json` — browser/demo lead records are not production data.

## Production mapping

The refined staff UI now lives at `backend/templates/business_dashboard.html`
and loads authenticated, tenant-scoped data from `/pipeline`, `/tasks`, and
`/users`. Buyer WhatsApp messages remain handled by the production Meta
webhook at `/webhooks/meta`.
