# EST8GO SERVICE LIMITED — CLAUDE.md

## Project
Multi-tenant SaaS real estate trust platform for Nigerian market.
Live: https://est8go-api.onrender.com
Super admin: est8go@gmail.com / Est8Go@2026

## COMPLETE ✅
- WhatsApp conversation engine (Kora v3) — fully tested live
- Intent filter v2.0 — property type, budget, location extraction
- Sales funnel — awareness → verification → commitment → handshake
- Objection engine — 12 Nigerian RE objections
- Trust architecture — GPS + AI Vision + Documents + Witnesses = 100pts
- Pipeline router — HITL takeover, reactivation, hot lead alerts
- Reel engine — FFmpeg video generation
- Business dashboard — FAB, channels, WhatsApp takeover, trust selector, images, XSS sanitisation, role modules, menu drawer
- Login page — complete
- Auth guard — JWT, 401 redirects to login
- 25 demo listings seeded across Abuja + Lagos
- Super Admin Dashboard — 5-tab SPA (Pulse/Tenants/Verify/Audit/Menu), no Tailwind, solid surfaces, sanitise() everywhere, auto-refresh, conversation tracer, staff role assignment, tenant suspend/reactivate/delete
- Admin backend — /admin/conversations, /admin/verify-queue, /admin/listings/{id}/verify|flag|reject, /admin/tenants/{id}/suspend|reactivate, DELETE /admin/tenants/{id}, /admin/staff/{id}/role

## COMPLETED THIS SESSION ✅
- Email service (Resend SDK) — 7 functions, working
- Password reset flow — forgot_password.html, reset_password.html, endpoints live
- Login page — forgot password link + eye toggle working
- Role change approval system — request, email, password confirm, approve/reject
- Tenant signup links — generate, email, branded onboarding page
- Onboarding page — 5-step flow, validates code, creates tenant+user
- Referral system — ReferralCode, ReferralConversion models, /referrals/my-code
- Credit economy — full ledger, wallet, bundles, Paystack integration
- Paystack payment flow — tested and working with test cards
- Credit widget — professional wallet pill, colour-coded states
- Super Admin credit management — award credits, view all wallets
- Data migration — all new tables created on Supabase production
- Credit bundles seeded — Starter/Growth/Pro/Scale
- Credit deductions wired on all services:
  Reel generation: 10 credits (reel_engine.py)
  Document upload: 3 credits (document_router.py)
  AI vision audit: 5 credits (ai_vision_service.py)
  Recovery messages: 1 credit (recovery_engine.py)
  All wrapped in try/except — never block service delivery
- Credits tab in business dashboard:
  Balance overview (purchased/bonus/total spent)
  9-item service costs reference table
  Transaction history with icons and labels
  Wallet pill navigates to credits tab
  confirmCreditAction() warns before expensive actions
- Drop-off recovery engine:
  Timing: 4h/24h/48h/7d for awareness
  Smart send window: 7am-9pm WAT
  Auto-stop on negative keywords + Nigerian Pidgin
  Bot permanently deactivated on opt-out
  Hourly cron job on Render (est8go-reminder-cron)
- Recovery message labels in ACTION_LABELS
- Meta templates ARE wired — recovery sends APPROVED TEMPLATES,
  never free-form text (send_meta_template + choose_recovery_template,
  5 reengaged_* templates). This is what makes it 24h-window safe.
  Guards before any send: RECOVERY_MAX_AGE_DAYS recency cutoff
  (default 14d), platform-care skip, refusal when a tenant has no
  phone_number_id.
  Template inventory: docs/meta_templates.md — VERIFIED against the
  Meta dashboard. All 5 reengaged_* are Active/Approved, category
  Marketing, language en, matching the code. The account holds exactly
  6 templates (the 5 plus hello_world).
  RECOVERY_ENABLED still "false" — nothing sends.
- property_carousel DELETED from the codebase — it never existed in
  Meta, so every send returned HTTP 400 and was logged and swallowed.
  send_meta_carousel + prepare_meta_carousel removed, all 6 call sites
  removed, plus the unreachable trigger_global_search branch. The
  hardcoded en_US language bug died with it.
- Property cards on ALL results paths — _send_property_card() in
  conversation_service.py. Image card (photo + summary caption) with
  text fallback, is_main-first photo selection matching
  choose_recovery_template. Replaces 2 inlined copies and fixes 3
  paths that previously sent text only: welcome-choice resume,
  "continue" handler, budget objection. Needs live WhatsApp testing.
- credits/history returns action_type or event_type
- Onboarding Step 3 redesigned — two option cards:
  Option A: Est8Go sets up WhatsApp (50 credits, phone number only)
  Option B: Self-managed (Phone ID + Access Token + Test Connection)
  Option A selected by default, admin notified by email on signup
- Language cleanup — all user-facing "bot" and "AI" replaced:
  bot → automation, AI assistant → sales assistant
  Bot active → Automation active, AI Assist → Smart Assist
  Variable names and function names unchanged
- Data Retention Policy:
  retention_service.py — 3-stage sweep (backfill suspended_at, anonymise PII at 30d, disable automation at 12mo dormancy)
  run_retention.py — daily cron at 02:00 UTC
  migrate_retention.py — 4 new columns on Supabase (suspended_at, anonymised_at on tenants; deleted_at, anonymised_at on users)
  suspend_tenant stamps suspended_at, reactivate clears it
  render.yaml — est8go-retention-cron added
- Platform Health Monitor + Issues Tracker:
  health_service.py — checks DB/WhatsApp/Paystack/OpenAI/conversations/security
  health_router.py — GET /admin/health/status, /history, POST /run
  issues_router.py — full CRUD for platform issues
  run_health_check.py — 15-min cron, OpenAI throttled to 120min
  migrate_health.py — health_checks table created on Supabase
  render.yaml — est8go-health-cron every 15 minutes
  Super Admin — Health Monitor tab + Issues Tracker tab in menu drawer
  Auto-escalation emails on CRITICAL alerts to est8go@gmail.com
  Red banner across all tabs on CRITICAL, amber badge on warnings
  platform_issues table — RLS enabled on Supabase
- Tenant Recovery Speed Settings:
  CompanyProfile model: recovery_speed, send_window_start, send_window_end columns
  GET/PATCH /tenants/me/profile/recovery-settings
  Business dashboard Settings tab: 3 speed cards (Gentle/Standard/Aggressive), WAT send window selector, live timing preview table
  Recovery engine reads per-tenant settings on each run
  migrate_recovery_settings.py run on production
- Trust score fixes:
  ai_verified_real default changed to False
  calculate_listing_trust() single source of truth
  ListingOut schema now includes all 11 trust fields
  New listings always start as pending_review
  Verify queue now shows pending_review listings
  All existing listings recalculated correctly (migrate_fix_ai_default.py)
- Market Intelligence (Phase 3):
  GET /admin/market-intelligence — price trends, trust distribution, volume, property type breakdown
  Super Admin menu drawer → Market Intelligence tab
  4 stat cards: Total Listings, Avg Price, Avg Trust Score, Gold+ Verified
  Trust grade distribution bars (emerald/gold/silver/bronze/ungraded)
  Price & volume by location (avg/min/max price, avg trust, listing count)
  By property type table (count, avg price, avg trust)
- Super Admin MMEF Monitoring:
  GET /admin/mmef/compliance — filters Core/Growth tenants
  POST /admin/mmef/{id}/override — manual compliance override
  POST /admin/mmef/{id}/extend-grace — extend grace 7 days
  run_mmef_check.py — daily cron at 01:00 UTC
  Warning emails at 7 and 3 days left in month
  MMEF tab in Super Admin with 4 stat cards
  Progress bar per tenant with colour coding
  Mark Compliant + Extend Grace buttons
  est8go-mmef-cron added to render.yaml
  Mobile label fix — 9px font, Non-Compliant splits 2 lines
- Property page WhatsApp buttons fully wired:
  I am Interested + Chat to Buy → correct WA Business number
  _get_wa_number() normalises E.164 from tenant or WHATSAPP_BUSINESS_NUMBER env
  Property reference detection in intent_filter (priority 0, before all checks)
  Fast-track to commitment stage on button tap (funnel_stage=commitment, lead_score=75)
  Realtor hot lead alert fires immediately via alert_realtor_of_lead
  Full funnel path: property page tap → property card → inspection booking
- 10 conversation engine improvements:
  AI AUDITED badge gated on ai_verified_real (property_detail.html)
  Trust badge: ≥70 → Verified Trusted Listing, ≥30 → GPS Verified
  PROPERTY_TYPE_ALIASES + normalise_property_type() — flat→apartment, plot→land etc
  PATCH /admin/staff/{id}/phone — set realtor phone via Super Admin
  Realtor alert fallback to tenant.whatsapp_phone_number when phone_number is null
  NEARBY_AREAS map — no-results message suggests nearby areas (Maitama→Asokoro etc)
  Budget parser: 100k→100,000; half million→500,000; quarter million→250,000
  Trust score displays as /100 with GPS Verified / Pending Verification label
  COMPARISON_PATTERNS intent + comparison handler + last_match_ids saved per search
  send_meta_image_message() — first property photo sent after text delivery
  Recovery awareness nudge 1 personalised with previous search context
- Light/Dark theme system — business_dashboard.html + super_admin_dashboard.html:
  No-flash IIFE, localStorage persistence, system preference detection, manual toggle
- World class property page redesign (Phase 1) — property_detail.html:
  Hero image carousel with touch/drag swipe and dot navigation
  Animated SVG trust score ring (colour-coded by grade, draws on load)
  Verification timeline: GPS date, AI audit, docs (C of O/Deed/Survey), witnesses
  Embedded Google Maps iframe (only when lat+lng present)
  Agent profile card with plan badge and Est8Go Verified badge
  Sticky action bar: I am Interested (WhatsApp), Chat, Share
  Web Share API + clipboard fallback
  Open Graph + Twitter Card meta tags for social sharing
  Light/dark theme with no-flash, mobile-first, touch targets 44px+
  Classic rollback preserved at /public/property/{id}/classic
- Public tenant vault page (Phase 2) — /public/{tenant_slug}:
  Agency header with Est8Go Verified badge and WhatsApp Chat button
  Hero stats: total listings, GPS verified count, AI audited count
  Sticky filter chips by property type and location (query params)
  Property grid: 1 col mobile → 2 col @640px → 3 col @960px
  Trust score overlay (colour-coded by grade) on each card
  GPS Verified tag on verified listings
  WhatsApp button per card with property reference pre-filled
  Powered by Est8Go footer
  Tenant.slug column added to model, unique index, auto-generated on signup
  migrate_tenant_slug.py — run to backfill slugs for existing tenants
  urlencode Jinja2 filter registered on templates.env
- Est8Go Embed Widget (Phase 3) — backend/static/embed.js + /public/api/{tenant_slug}/listings:
  embed.js v1.1 — zero dependencies, vanilla JS, Shadow DOM isolation
  Light/dark/auto theme via CSS variables (.widget / .widget.light classes)
  Customisation: data-accent (hex), data-radius (px), data-columns (1-3)
  data-show-price, data-show-wa, data-show-trust, data-show-branding (true/false)
  Responsive grid: 1 col mobile / ≤2 col @480px / cfg.columns @768px
  Auto-refreshes every 30 minutes via setInterval
  Auto theme: matchMedia listener toggles .light class — no re-fetch
  host.className='est8go-embed-host' for demo widget cleanup
  Interactive developer demo at /public/embed with live controls
  (theme/columns/limit/radius/accent update widget without page reload)
  JSON API: GET /public/api/{tenant_slug}/listings (type/location/limit params)
  Returns: id, title, location, property_type, price, trust_score, trust_grade,
  gps_verified, image_url, wa_number, property_url
  Works on WordPress, Wix, Squarespace, Webflow, custom HTML
  Attribute table: 12 attrs with Plan column (All / Growth+ / Pro only)
- Hosting recommendation documented:
  Stage 1 (now): Render Starter $7/mo + Supabase free
  Stage 2 (10-50 tenants): Render Standard + Supabase Pro
  Stage 3 (50+): Railway or DigitalOcean
  Domain: api.est8go.com → CNAME to Render

## DO NOT OVERWRITE ⚠️
- backend/app/conversations/intent_filter.py
- backend/app/conversations/templates.py
- backend/app/services/conversation_service.py
- backend/app/services/chatbot/kora_behavior.py
- backend/templates/business_dashboard.html
- backend/templates/login.html

## EMAIL SERVICE
- Provider: Resend (resend.com)
- SDK: pip install resend (add to requirements.txt)
- RESEND_API_KEY is in .env
- FROM_EMAIL: onboarding@resend.dev (temporary until custom domain)
- Future: noreply@est8go.com

## ENVIRONMENT VARIABLES (ALL SET ON RENDER + .env)
RESEND_API_KEY, FROM_EMAIL, BASE_URL
PAYSTACK_SECRET_KEY, PAYSTACK_PUBLIC_KEY, PAYSTACK_WEBHOOK_SECRET
DATABASE_URL, SECRET_KEY, OPENAI_API_KEY
WHATSAPP_ACCESS_TOKEN, WHATSAPP_PHONE_ID, META_VERIFY_TOKEN
SUPABASE_URL, SUPABASE_KEY

## CREDIT ECONOMY SUMMARY
Currency: Est8 Credits
Tiers: Pilot / Access / Core / Growth / Enterprise
Bundles: Starter(50/₦2,500) Growth(200/₦8,000) Pro(600/₦20,000) Scale(1,500/₦42,000)
MMEF: Core ₦2,500/mo, Growth ₦6,000/mo
Expiry: Purchased=never, Bonus=90 days, Dormant=12 months
Welcome: 10 bonus credits on signup
Ledger: Immutable, 11 event types
Wallet: Split purchased vs bonus, deduct bonus first

## NEXT TASKS (in order)

### Landing Page — Pending Corrections (Priority 1)
File: landing/index.html
Stages 1–4 complete. Final corrections before deploy.

#### PENDING CORRECTIONS (Landing Page)

1. Embed section white space fix: ✅ DONE
   - embed-platforms moved inside embed-left
   - embed-right sticky top: 80px
   - Right column aligns with header

2. Replace 234XXXXXXXXXX with real WA number
   in landing/index.html
   Search: XXXXXXXXXX (appears ~8 times)

3. api.est8go.com DNS — add CNAME in Netlify:
   Domain management → DNS settings → Add record:
   Type: CNAME
   Name: api
   Value: est8go-api.onrender.com
   Then update BASE_URL on Render to:
   https://api.est8go.com

4. Deploy landing page to Netlify after WA number updated
   (drag and drop landing/ folder to Netlify dashboard)
   - Test on mobile and desktop
   - Verify all animations and links work

5. Speak to Bravieshomz management
   for real listings approval

6. Set admin phone numbers in Super Admin
   → Staff & Phones tab

### 1. Est8Go Landing Page ✅ STAGES 1–3 COMPLETE
URL: est8go.com (hosted on Namecheap or Netlify free)
File: landing/index.html (standalone, no backend needed)

World class landing page that makes real estate companies say "I need this."

Sections:
1. Hero — "Truth as a Service" tagline
   - Headline: "The Trust Layer for African Real Estate"
   - Subheadline: GPS verified. AI audited. Document checked.
   - CTA: "Get Started Free" → tenant signup link
   - CTA: "See Live Demo" → /public/bravieshomz-limited
   - Hero visual: property card with trust score ring

2. Problem section
   - "₦billions lost to property fraud every year"
   - 3 pain points: fake listings, stolen photos, forged documents

3. Solution — How Est8Go Works
   - Step 1: List your property
   - Step 2: GPS verify on-site
   - Step 3: AI audits your photos
   - Step 4: Buyers trust your listing

4. Trust Score explanation
   - Visual breakdown: GPS 30pts, AI 20pts, Docs 40pts, Witnesses 10pts
   - Grade tiers: Bronze / Silver / Gold / Emerald

5. Embed Widget showcase
   - "Add to your website in 60 seconds"
   - Live embed demo using bravieshomz-limited
   - One line of code snippet

6. Pricing tiers
   - Pilot (free), Starter, Growth, Pro, Enterprise

7. Social proof
   - "X properties verified"
   - "X trusted agents"
   - "X diaspora buyers served"

8. CTA Footer
   - "Start verifying your listings today"
   - WhatsApp contact button

Design: Est8Go brand colours, Inter + Syne fonts
        Mobile-first, fast load, no frameworks, no CDN
        Light/dark theme toggle

CONTEXT:
- Embed widget live at /static/embed.js
- Tenant slug for live demo: bravieshomz-limited
- Signup link generated via Super Admin → Tenants tab
- Live API base: https://est8go-api.onrender.com

### 2. Light/Dark Theme System ✅ DONE
Added to business_dashboard.html and super_admin_dashboard.html:
- Auto system preference detection, manual toggle 🌙/☀️, localStorage persistence
- No theme flash on load, exact brand colours, zero backend changes

### 3. Diaspora Trust Certificate PDF
- backend/app/services/trust_certificate_service.py
- Uses WeasyPrint or ReportLab
- Shows: trust score, GPS coords, docs verified, Est8Go seal
- Deducts 20 credits on generation
- Available from Trust tab in dashboard

### 4. Conversation Engine Final Polish
1. Fix "ph" extracted from "physical" as Port Harcourt
   File: backend/app/conversations/intent_filter.py
   Add LOCATION_FALSE_POSITIVES set — skip single-word matches that appear inside longer words

2. Fix "9 o'clock" time detection
   File: backend/app/services/conversation_service.py
   Add r"\b\d{1,2}\s*o'?clock\b" pattern to has_time_pattern regex block

3. Image as card with caption (not separate message)
   File: backend/app/services/conversation_service.py + notification_service.py
   Combine text + image into single WhatsApp image message with caption
   instead of text message followed by separate image

4. Property page "Continue on WhatsApp" button
   File: backend/templates/property_detail.html
   Add green WhatsApp button below "I am Interested" that links back to
   the tenant's WhatsApp chat (wa.me link, no pre-filled text)

5. Property page link text update
   File: backend/app/services/chatbot/message_builder.py
   Change "View High-Res Photos & GPS Audit" to "View Property Details & Photos"

### 5. Conversation engine full test
- Test complete WhatsApp flow with real listings
- Single message extraction
- Objection handling
- Handshake + Google Maps delivery
- Session memory hot resume

## EST8GO BRAND COLOUR SYSTEM

### Dark Theme (Default)
Background:     #0F172A
Cards:          #111827
Surfaces:       #1E293B
Border:         rgba(255,255,255,0.07)
Text Primary:   #F8FAFC
Text Muted:     #94A3B8
Text Disabled:  #64748B

### Light Theme
Background:     #F8FAFC
Cards:          #FFFFFF
Border:         rgba(15,23,42,0.08)
Text Primary:   #0F172A
Text Muted:     #64748B

### Accent Colours (Both Themes)
Primary Indigo:  #4F46E5
Deep Indigo:     #4338CA
Emerald Trust:   #10B981
Amber Warning:   #F59E0B
Crimson Risk:    #F43F5E
Info Blue:       #3B82F6
Neutral Slate:   #334155

### Gradients
Indigo:  linear-gradient(135deg, #4338CA 0%, #4F46E5 100%)
Trust:   linear-gradient(135deg, #059669 0%, #10B981 100%)
Surface: linear-gradient(180deg, #111827 0%, #0F172A 100%)

### Typography
Body:     Inter
Headings: Syne (weights 700, 800)

### Brand Feel
Calm operational intelligence — NOT flashy neon crypto UI
Communicates: trust, professionalism, operational clarity,
confidence, verification, modern African infrastructure

## BACKEND STACK
- FastAPI + SQLAlchemy + PostgreSQL (Render)
- JWT auth (jose), bcrypt passwords
- Jinja2 templates for all frontend pages
- All frontend: single-file SPA, no Tailwind CDN, no CDN at all
- Brand tokens: --bg:#0F172A --surface:#111827 --surface2:#1F2937 --indigo:#4F46E5 --em:#10B981 --warn:#F59E0B --risk:#F43F5E
- Fonts: Inter (body) + Syne (headings/metrics) from Google Fonts only
- sanitise() XSS function on ALL user data in innerHTML
- Auth.fetch() wrapper in /static/js/auth_guard.js handles JWT headers

## IMPORTANT REMINDERS
- Never overwrite intent_filter.py, templates.py,
  conversation_service.py, kora_behavior.py
- Always sanitise() user data in innerHTML
- No backdrop-filter anywhere
- Mobile first — min touch targets 44px
- Credit deduction: bonus first then purchased
- Paystack webhook uses HMAC with PAYSTACK_SECRET_KEY
- Ledger is immutable — never UPDATE or DELETE
- Recovery engine: 7am-9pm WAT send window
- MMEF: Core ₦2,500/mo, Growth ₦6,000/mo

## SUPPORT WORKFLOW

### When Issues Arise
1. Check Render logs first
2. Note exact error message and endpoint
3. Open new Claude.ai conversation
4. Paste: "Read CLAUDE.md. I have this issue: [error]"
5. Claude will diagnose and fix

### Common Issues + Quick Fixes
Database connection error:
  Check DATABASE_URL in Render environment
  Check Supabase dashboard for connection limit

WhatsApp not responding:
  Check WHATSAPP_ACCESS_TOKEN not expired
  Meta tokens expire every 60 days — regenerate in Meta Developer Portal
  Check WHATSAPP_PHONE_ID is correct

Render deployment failed:
  Check build logs for import errors
  Usually missing package in requirements.txt
  Or Base import path wrong (use app.database.base not app.database.db)

Credits not deducting:
  Check credit_wallets table exists
  Run python migrate_credits.py
  Check tenant has a wallet record

Email not sending:
  Check RESEND_API_KEY in Render environment
  Check Resend dashboard for bounces
  Verify FROM_EMAIL format: Name <email@domain>

Paystack webhook not crediting:
  Check PAYSTACK_SECRET_KEY in Render (no duplicates)
  Verify webhook URL set in Paystack dashboard
  Check x-paystack-signature header present

Bot not responding to WhatsApp:
  Check META_VERIFY_TOKEN matches
  Check webhook URL registered in Meta
  Check conversation state not stuck in HANDOFF

### Meta WhatsApp Token Renewal
Tokens expire every 60 days.
When expired: all tenant bots go offline immediately.
Fix:
  1. Go to Meta Developer Portal
  2. Generate new permanent token
  3. Update WHATSAPP_ACCESS_TOKEN in Render
  4. Redeploy

### Emergency Contacts
Platform down completely:
  Check https://status.render.com
  Check https://status.supabase.com
  Check https://developers.facebook.com/status

## SECURITY RULES — NEVER VIOLATE

### Tenant Isolation (Critical)
- Every endpoint that returns tenant data MUST use
  current_user = Depends(get_current_user)
- Never use x_tenant_id header as the sole auth
- Never default tenant_id to 1 or any hardcoded value
- Regular users: always use current_user.tenant_id
- Superusers only: may accept x_tenant_id header

### Admin Endpoints (Critical)
- All /admin/* and /listings/admin/* endpoints MUST use
  current_user = Depends(require_superuser)
- Never check if x_tenant_id == "1" as admin auth
- Admin access = verified JWT with role="superuser"

### Data Validation
- Never trust client-supplied tenant_id
- Always verify listing.tenant_id == current_user.tenant_id
  before returning or modifying listing data
- Cross-tenant access always raises 403 not 404
  (404 leaks existence of the resource)

### Security Headers (Always Present)
- X-Frame-Options: DENY
- X-Content-Type-Options: nosniff
- X-XSS-Protection: 1; mode=block
- Referrer-Policy: strict-origin-when-cross-origin

### Frontend
- Always pass CFG.JH (JWT headers) in every fetch()
- Never hardcode fallback data values (no || 72)
- Sanitise all user data before innerHTML
