# Est8Go — Project Reference for Claude

Est8Go is a multi-tenant AI-powered real estate trust/verification SaaS for the Nigerian market. Agencies and freelance realtors (tenants) use it to run a WhatsApp chatbot that qualifies leads, verifies properties via GPS + AI + documents, and scores property trust on a 100-point scale.

Deployed on Render: `https://est8go-api.onrender.com`

---

## Stack

- **Backend:** FastAPI, SQLAlchemy, PostgreSQL (Supabase), Python 3.11
- **AI:** OpenAI gpt-4o-mini (conversation brain + AI vision audit)
- **Messaging:** Meta/WhatsApp Cloud API webhooks
- **Frontend:** Jinja2 templates, vanilla JS, no build step — all CSS/JS inline in single HTML files
- **Auth:** JWT (python-jose), role-based, IP-bound for platform roles
- **Hosting:** Render (single service, `render.yaml`)

---

## Folder Structure

```
backend/
├── app/
│   ├── main.py                        # FastAPI app, router mounts
│   ├── models_registry.py             # Imports all models for Alembic
│   ├── auth/                          # JWT login, token refresh, schemas
│   ├── core/                          # Config (settings), security (hashing, tokens)
│   ├── database/                      # Base, db session, audit log, seed scripts
│   ├── users/                         # User model, router (/users/me)
│   ├── tenants/                       # Tenant model, router
│   │   ├── profile_router.py          # ⚠️ BROKEN — references non-existent fields
│   │   └── router.py                  # Minimal — missing deactivate/update/get-single
│   ├── company_profiles/              # ✅ Correct profile router (use this, not profile_router)
│   ├── listings/                      # Listing model, CRUD router, document_router
│   ├── conversations/                 # Bot pipeline: brain, intent_filter, objection_engine,
│   │   │                              #   ai_fallback, templates, responses, pipeline_router
│   │   └── engine.py                  # Legacy shim
│   ├── messages/                      # Message model
│   ├── ai_cache/                      # GPT response cache model
│   ├── services/
│   │   ├── conversation_service.py    # Master orchestrator — 765 lines, 7-step pipeline
│   │   ├── trust_engine.py            # 100-pt trust score calculator
│   │   ├── document_trust_engine.py   # Nigerian doc hierarchy scoring
│   │   ├── ai_vision_service.py       # OpenAI vision audit (40% complete)
│   │   ├── meta_sender_service.py     # WhatsApp message sender
│   │   ├── notification_service.py    # Push/alert notifications
│   │   ├── recovery_engine.py         # Bot recovery from dead sessions
│   │   ├── reel_engine.py             # Property reel generator (30% complete)
│   │   ├── reel_router.py             # Reel API routes
│   │   ├── tenant_service.py          # Tenant helpers
│   │   ├── tenant_resolver.py         # Resolves tenant from WhatsApp number
│   │   ├── auth_service.py            # ⚠️ Stub only — real auth in auth/router.py
│   │   └── chatbot/                   # search_service, message_builder, kora_behavior, fallback_engine
│   ├── channels/whatsapp/router.py    # Meta webhook handler
│   ├── public/router.py               # HTML page routes + public listing API
│   └── admin/router.py                # Superuser-only API
├── templates/
│   ├── business_dashboard.html        # ✅ PRIMARY — Business Command Center (single-file SPA)
│   ├── super_admin_dashboard.html     # Est8Go staff portal
│   ├── login.html                     # Auth page
│   ├── property_detail.html           # Public property trust page
│   └── matches_gallery.html           # Bot match results gallery
└── static/
    ├── js/auth_guard.js               # Token check on page load
    ├── auth.js
    ├── admin_portal.js
    └── realtor_portal.js
```

---

## Trust Score System (100 pts)

| Signal | Points | How |
|--------|--------|-----|
| GPS Verification | 30 | Listing has `latitude` + `longitude` |
| AI Vision Audit | 20 | `ai_verified_real = true` |
| Document Score | 40 | Nigerian doc hierarchy (C of O = 35pts, R of O = 35pts, etc.) |
| Witness Signals | 10 | Up to 2 witnesses × 5 pts |

**Grades:** Emerald (85–100) · Gold (75–84) · Silver (50–74) · Bronze (0–49) · Flagged (override)

---

## RBAC Roles

**Platform:** `superuser` (1hr token, IP-bound), `super_staff` (8hr, IP-bound)

**Tenant:** `tenant_admin`, `realtor`, `staff`, `support`, `marketing`

**Module access (`ROLE_MODULES` in business_dashboard.html):**
- superuser / super_staff / tenant_admin → all 8 tabs
- realtor → home, properties, pipeline, operations, trust, studio
- staff → home, properties, pipeline, operations
- marketing → home, properties, studio

---

## Business Dashboard (`business_dashboard.html`)

Single-file SPA (~3600 lines). Served at `/public/business` and `/public/realtor-portal`.

### Architecture
- All CSS, HTML, JS in one file — no build step, no framework
- Fixed collapsible header with ResizeObserver + scroll listener
- 5-slot bottom nav: Home · Properties · [FAB] · Pipeline · Menu
- FAB is `position:fixed` outside `<nav>`, centered with `pointer-events:none` container + `pointer-events:all` on button — never clipped
- 8 tabs: home, properties, pipeline, operations, trust, studio, network, analytics
- MENU_ONLY_TABS (trust, studio, network, analytics) show Menu nav button as active

### Key JS Objects
```js
CFG         // API endpoints, tenant ID, token, role, tenantType
ST          // Runtime state: tab, leads, listings, timer, koraOpen, trustLoaded
CHANNELS    // whatsapp (live), instagram/messenger (coming soon)
FAB_ACTIONS // Per-tab action sets: home/properties/pipeline/operations
ROLE_MODULES// Tab visibility per role
```

### Key Functions
| Function | Purpose |
|----------|---------|
| `resolveCurrentUser()` | Fetches `/users/me`, sets CFG._role, populates header UI |
| `applyRole(role)` | Shows/hides agency-only elements, enforces ROLE_MODULES on nav |
| `switchTab(tab)` | Switches active tab, calls updateFAB(tab), triggers load function |
| `renderLeads(leads)` | Pipeline lead cards with channel badges, takeover button |
| `takeover(id,phone,name,ch)` | POSTs bot pause, opens WhatsApp deep link |
| `loadTrust()` | Fetches listings, renders trust ring + breakdown + listing selector |
| `renderTrustListing(l)` | Populates GPS/AI/doc/witness rows for one listing |
| `openFAB()` | createElement per action, immediate addEventListener |
| `sanitise(str)` | HTML-escapes all user data before innerHTML insertion |
| `formatMoney(n)` | Returns ₦ formatted string or `—` for null/NaN |

### CSS Design Tokens
```css
--bg: #0F172A        --surface: #111827    --surface2: #1F2937
--indigo: #4F46E5    --indigo-lg: #4338CA  --indigo-dim: rgba(67,56,202,0.12)
--em: #10B981        --warn: #F59E0B       --risk: #F43F5E
--text: #F1F5F9      --muted: #94A3B8      --border: rgba(255,255,255,0.08)
```

---

## Conversation Pipeline (7 steps)

In `services/conversation_service.py` (master orchestrator):

1. Tenant Resolution — resolve tenant from WhatsApp number
2. Intent Pre-Filter — Python rules, handles 80% without GPT
3. Objection Handler — 12 Nigerian RE objections
4. Session Memory — hot/warm/cold lead temperature
5. Lead Scoring — update `lead_score` on `Conversation`
6. GPT Extraction — gpt-4o-mini for intent + entity extraction
7. Search + Delivery — query listings, build WhatsApp reply

---

## API Routes (key ones)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/auth/token` | Login → JWT |
| GET | `/users/me` | Current user + tenant fields |
| GET | `/listings/` | Tenant's listings |
| POST | `/listings/` | Create listing |
| GET | `/listings/{id}/documents` | Listing documents |
| POST | `/listings/{id}/upload` | Upload property docs |
| GET/POST | `/conversations/pipeline` | Lead pipeline |
| POST | `/conversations/pipeline/{id}/takeover` | Pause bot, hand to human |
| POST | `/channels/whatsapp/webhook` | Meta webhook |
| GET | `/public/business` | Business dashboard HTML |
| GET | `/public/realtor-portal` | Same (legacy alias) |
| GET | `/public/property/{id}` | Public trust page |
| GET | `/public/matches` | Bot match gallery |

Both `/public/business` and `/public/realtor-portal` return `Cache-Control: no-cache` headers.

---

## Known Bugs / Tech Debt

1. **`tenants/profile_router.py` is broken** — references `short_about`, `phone`, `payment_options`, `inspection_policy`, `manager_name`, `handoff_message` which don't exist on the model. Use `company_profiles/router.py` instead.
2. **`.env` file had live secrets committed** — OpenAI key, Supabase credentials, WhatsApp tokens. Should be removed from git history and credentials rotated.
3. **Auth guards commented out** in `listings/router.py` lines ~165, 178, 200.
4. **`auth_service.py` is a 36-line stub** — real auth logic is in `auth/router.py` and `conversation_service.py`.
5. **Deprecated user fields** — `is_admin`, `is_superuser` still used alongside new `role` field in some places.
6. **`realtor_dashboard.html` deleted** — `/public/realtor-portal` now serves `business_dashboard.html`.

---

## What's Complete

- ✅ Auth system (JWT, refresh, lockout, IP-binding for platform roles)
- ✅ Multi-tenancy (3-layer isolation: tenant_id on all models, middleware, deps)
- ✅ Listings CRUD + document upload
- ✅ Trust engine (100-pt scoring, grade calculation)
- ✅ WhatsApp bot pipeline (7-step orchestrator)
- ✅ Lead pipeline (funnel stages, temperature, takeover)
- ✅ Business dashboard SPA — header, 8 tabs, FAB, channels, trust center, modals, Kora AI assistant
- ✅ Kora chat (in-dashboard AI assistant, left panel)
- ✅ Property trust public page (`/public/property/{id}`)
- ✅ Bot match gallery (`/public/matches`)
- ✅ Super admin dashboard (skeleton)
- ✅ XSS sanitisation on all user data in dashboard innerHTML
- ✅ Cache-Control headers on dashboard routes

---

## What Needs Building Next

### High Priority
- [ ] **Document OCR/parsing** — `document_trust_engine.py` scores uploaded docs but doesn't parse/extract data. Integrate Tesseract or Azure Document Intelligence for Nigerian C of O, Survey plans.
- [ ] **AI Vision audit** — `ai_vision_service.py` exists (40% done) but isn't wired into listing creation flow. Should auto-run on image upload.
- [ ] **Tenant management UI** — No UI for tenant admin to manage team members (invite worked, but listing/removing/role-change missing). Wire to `/users/` endpoints.
- [ ] **Real-time pipeline** — Pipeline currently polls every 25s. Upgrade to WebSocket or SSE for live lead notifications.
- [ ] **Super admin dashboard** — HTML skeleton exists but no data binding. Needs tenant list, user list, platform metrics.

### Medium Priority
- [ ] **Reel engine** — `reel_engine.py` exists (30%) but reel generation isn't functional end-to-end. Needs media assembly and WhatsApp media upload.
- [ ] **Network tab** — Placeholder. Should show referral network, agent connections, shared listings.
- [ ] **Analytics tab** — Placeholder. Revenue/pipeline/conversion charts using existing data.
- [ ] **Operations tab** — Placeholder. Task board, visit scheduling, reminders.
- [ ] **Witness attestation** — Trust score has 10pts for witnesses but no witness submission flow in dashboard.
- [ ] **GPS capture on mobile** — `captureGPS()` works but needs UX polish (map preview, accuracy indicator).

### Low Priority / Polish
- [ ] **Push notifications** — `notification_service.py` exists but not wired to dashboard.
- [ ] **Dark/light mode toggle** — Dashboard is dark-only.
- [ ] **Property search/filter** — Vault tab shows all listings with no filter.
- [ ] **Listing edit flow** — No edit UI for existing listings.
- [ ] **Recovery engine** — `recovery_engine.py` built but integration with bot pipeline unverified.
- [ ] **Channel routing** — Instagram and Messenger channels marked "coming soon" in dashboard.

### Security / Infra
- [ ] Rotate all credentials (OpenAI, Supabase, WhatsApp) — `.env` was in git history.
- [ ] Fix commented-out auth guards in `listings/router.py`.
- [ ] Remove/replace deprecated `is_admin`/`is_superuser` fields.
- [ ] Fix or remove broken `tenants/profile_router.py`.
- [ ] Add rate limiting on WhatsApp webhook endpoint.

---

## Development Notes

- The dashboard is a single HTML file — all changes go to `backend/templates/business_dashboard.html`.
- When editing the dashboard, the file is ~3600 lines. Read the specific section before editing; don't overwrite large blocks blindly.
- `sanitise()` must be called on all user-supplied strings before inserting into `innerHTML`. Never skip this.
- `formatMoney(n)` returns `—` for null/undefined/NaN. Don't add `₦` prefix at call sites — it's built in.
- FAB is `position:fixed` outside `<nav>` — it must stay there. Moving it back inside nav causes clipping.
- Both `/public/business` and `/public/realtor-portal` serve the same template. Keep them in sync.
- Render auto-deploys on push to `main`. Changes are live ~2 minutes after push.
