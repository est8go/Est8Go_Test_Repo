# Meta WhatsApp Message Templates

> ⚠️ **UNVERIFIED — pull from the Meta dashboard.**
> Every name, parameter and header type below was reconstructed from the
> Est8Go source code, **not** exported from Meta Business Manager. Nothing
> here has been checked against the approved templates. Confirm each row
> against the dashboard (WhatsApp Manager → Account tools → Message
> templates) and delete this banner once verified.
>
> A mismatch is silent: `send_meta_template` logs the Meta error and
> returns `False`, the recovery loop counts it as an error and moves on.
> A typo'd name, a wrong language code, or body params in the wrong order
> all fail the same way, with no other symptom.

## Why templates at all

Meta blocks business-initiated **free-form** messages outside the 24-hour
customer-service window. Only approved templates get through. Recovery is
cron-driven, so it is *always* outside that window and *always* sends
templates. The reply path (`send_meta_message`) is webhook-triggered and
therefore inside the window by definition — it correctly uses free-form
text and needs no templates.

## Recovery templates

Selected by `choose_recovery_template()` in
`backend/app/services/recovery_engine.py`. Sent by `send_meta_template()`
in `backend/app/services/meta_sender_service.py`.

All five are sent with `language={"code": "en"}`. Per the code comment,
all approved buttons are static Quick-Reply, so **no button component is
sent** in the payload.

| Template name | Body params (in order) | Header | Selected when |
|---|---|---|---|
| `reengaged_properties_images` | `[first_name, area]` | image (real listing photo) | `last_viewed_id` **and** `location` present in `data_json`, **and** the listing has a real image |
| `reengaged_high_values` | `[first_name]` | none | `lead_score >= 70` |
| `reengaged_awareness` | `[first_name]` | none | `funnel_stage == "awareness"` |
| `reengaged_verifications` | `[first_name]` | none | `funnel_stage == "verification"` |
| `reengaged_commitments` | `[first_name]` | none | `funnel_stage == "commitment"` |

### Selection precedence

1. `properties_images` — highest. If the listing has no real image, this
   falls through to the next rule rather than substituting a stock photo.
2. `high_values` — score-based, any recoverable stage.
3. Stage template — awareness / verification / commitment.

`handshake`, `closed` and unknown stages return `None` — no recovery.

### Guards applied before any send

- **Recency cutoff** — `RECOVERY_MAX_AGE_DAYS` (default 14). Leads idle
  longer than this are never chased.
- **Platform-care skip** — conversations with `platform_state` in
  `data_json`, and any conversation belonging to a tenant whose
  `tenant_type == "platform"`.
- **Credential refusal** — a tenant with no resolvable
  `phone_number_id` is logged as an error and skipped, never sent from
  the global platform number.
- **Kill switch** — nothing sends unless `RECOVERY_ENABLED` is exactly
  `"true"` (case-insensitive). Default off.

## Other templates referenced in code

| Template name | Where | Status |
|---|---|---|
| `property_carousel` | `send_meta_carousel()`, `meta_sender_service.py` | ❓ **Unconfirmed.** Used on the live reply path (several call sites in `conversation_service.py`). If it is not approved, every carousel send is failing silently — the function logs a non-200 and returns without raising. Worth checking first. |

## Fields to fill in from the dashboard

For each template, confirm and record:

- [ ] Exact name (case-sensitive)
- [ ] Language code — code sends `en`; confirm it is not `en_US`
- [ ] Category (MARKETING / UTILITY / AUTHENTICATION)
- [ ] Approval status and quality rating
- [ ] Header type and, for image headers, the expected aspect ratio
- [ ] Body placeholder count and order — `{{1}}`, `{{2}}`, …
- [ ] Button types (confirm all are static Quick-Reply)
