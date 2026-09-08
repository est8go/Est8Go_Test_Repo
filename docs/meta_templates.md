# Meta WhatsApp Message Templates

> ✅ **VERIFIED against the Meta dashboard (2026-09-08).**
> The five `reengaged_*` templates below are Active/Approved, language
> **English (`en`)**, category **Marketing** — matching what the code
> sends. No action needed on them.
>
> 🗑️ **`property_carousel` never existed in Meta and has been removed
> from the codebase.** The account holds exactly six templates: the five
> `reengaged_*` plus `hello_world` (Utility, `en_US`). `send_meta_carousel()`
> and `prepare_meta_carousel()` are deleted — see "Removed" below.

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

All five are sent with `language={"code": "en"}` — **confirmed correct**
against the dashboard (they are registered as English / `en`, not
`en_US`). All five are category **Marketing** and status
**Active/Approved**. Per the code comment, all approved buttons are
static Quick-Reply, so **no button component is sent** in the payload.

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

## Removed: `property_carousel`

`send_meta_carousel()` and `prepare_meta_carousel()` have been **deleted**
from `meta_sender_service.py`, along with all six call sites in
`conversation_service.py`.

The template was never created in Meta, so every call returned HTTP 400
(error 132001, "template name does not exist"). The function caught the
non-200, logged it and returned `None` without raising, so callers carried
on and nothing broke visibly.

**The cards buyers actually see come from `send_meta_image_message()`**
(`notification_service.py`) — a plain WhatsApp `type: "image"` message with
the property summary as its caption. That is free-form, needs no template
approval, and was already running on the main search path immediately
before each failing carousel call. Deleting the carousel changed nothing a
buyer receives; it only removed a guaranteed-failing API round-trip per
search.

Two bugs died with the function:

- **Hardcoded `en_US`.** Every Est8Go template is `en`; only Meta's stock
  `hello_world` is `en_US`. Had `property_carousel` ever been created as
  `en` to match the account, the send would have failed a second time for
  this separate reason.
- **Messenger-format buttons.** `prepare_meta_carousel` built `web_url` and
  `postback` buttons — Facebook Messenger Send API format, not WhatsApp —
  in a `buttons` key that `send_meta_carousel` never read. Dead data inside
  dead code, and not a usable starting point had the template been built.

Also removed: the unreachable `trigger_global_search` branch in
`conversation_service.py`, which contained one of the six call sites.
Nothing in the repo ever produced that reply value — `kora_behavior.py`
only passes it through — so the branch had never executed.

If a carousel is wanted in future, design the template in Meta first and
write the payload to match it. Do not resurrect the deleted code.

### Templates that actually exist in the account (6 total)

| Name | Category | Language | Status |
|---|---|---|---|
| `reengaged_awareness` | Marketing | `en` | Active |
| `reengaged_verifications` | Marketing | `en` | Active |
| `reengaged_commitments` | Marketing | `en` | Active |
| `reengaged_high_values` | Marketing | `en` | Active |
| `reengaged_properties_images` | Marketing | `en` | Active |
| `hello_world` | Utility | `en_US` | Active (Meta's default sample — unused by Est8Go) |

Note the language split: every Est8Go template is `en`. Only Meta's
stock `hello_world` is `en_US`, and it is unused by Est8Go. No code
sends `en_US` any more — `send_meta_template` defaults to `en`, which
matches all five live templates.

## Verification record

Checked against WhatsApp Manager on 2026-09-08:

- [x] Exact names — all five `reengaged_*` match the code
- [x] Language — `en` for all five; code sends `en`. Correct.
- [x] Category — Marketing for all five
- [x] Approval status — Active/Approved for all five
- [x] Account contains exactly 6 templates (5 + `hello_world`)
- [x] `property_carousel` — **absent**, and now deleted from the codebase

Still unrecorded (not needed for correctness, useful if templates are
edited later): body placeholder counts per template, image header
aspect ratio for `reengaged_properties_images`, and per-template
quality ratings.
