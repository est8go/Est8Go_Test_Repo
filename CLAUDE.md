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

### 1. Diaspora Trust Certificate PDF
- backend/app/services/trust_certificate_service.py
- Uses WeasyPrint or ReportLab
- Shows: trust score, GPS coords, docs verified, Est8Go seal
- Deducts 20 credits on generation
- Available from Trust tab in dashboard

### 2. Conversation engine full test (NEXT)
- Test complete WhatsApp flow with real listings
- Single message extraction
- Objection handling
- Handshake + Google Maps delivery
- Session memory hot resume

### 4. Admin phone numbers for lead alerts
- Set realtor phone numbers so pipeline alerts deliver

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
