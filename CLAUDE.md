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

### 1. Data Retention Policy
Create backend/app/services/retention_service.py:
- Suspended tenants: hidden immediately
- After 30 days: anonymise PII (name → [Suspended], email → [redacted])
- After 90 days: hard delete available to Super Admin
- Deleted staff: same 30/90 day lifecycle
- Dormant accounts: 12 months → bot offline, credits preserved
- Create backend/run_retention.py scheduled job
- Add to render.yaml as daily cron

### 2. Platform Health Monitor (High Priority)
Continuous infrastructure monitoring with immediate
escalation to Super Admin on critical issues.

Backend: Create backend/app/services/health_service.py

CHECK INTERVALS:
  Every 15 minutes (free checks):
    - Database connectivity + response time
    - WhatsApp API connectivity
    - Paystack API connectivity
    - Stuck conversations (HANDOFF > 24hrs)
    - Failed payments (pending > 30 mins)
    - Security: failed logins > 10 in 1 hour

  Every 120 minutes (OpenAI active check):
    - Send minimal test prompt to GPT-4o-mini
    - Verify response received within 10 seconds
    - Check error rate from last 100 AI calls
    - Cost: ~₦216/month

ESCALATION LEVELS:
  INFO:     Log only
  WARNING:  Log + amber badge on Super Admin dashboard
  CRITICAL: Log + immediate email to est8go@gmail.com
            + red alert banner on Super Admin dashboard
            + retry check after 5 minutes to confirm

CRITICAL TRIGGERS (immediate email escalation):
  - Database unreachable
  - WhatsApp API returning 401 (token expired)
  - WhatsApp webhook silent > 2 hours during business hours
  - OpenAI API unreachable or error rate > 10%
  - Paystack API unreachable
  - Failed login attempts > 10 in 1 hour (security breach)
  - Any endpoint returning 500 errors > 5 times in 10 mins

WARNING TRIGGERS (dashboard badge only):
  - Database response time > 2 seconds
  - OpenAI response time > 8 seconds
  - Conversations stuck in HANDOFF > 24hrs
  - Tenants with credit balance < 10
  - Pending payments > 30 minutes
  - WhatsApp token expiry < 7 days away

HEALTH STATUS COLORS:
  Green  = all systems operational
  Amber  = warning — monitor closely
  Red    = critical — immediate action needed
  Grey   = check not yet run

Backend files to create:
  backend/app/services/health_service.py
    - run_all_checks()
    - check_database()
    - check_whatsapp()
    - check_openai() — every 120 mins
    - check_paystack()
    - check_conversations()
    - check_security()
    - escalate_critical(issue, detail)
    - HealthCheck model for storing results

  backend/app/admin/health_router.py
    - GET /admin/health/status
    - GET /admin/health/history?days=7
    - POST /admin/health/run (manual trigger)

  backend/run_health_check.py
    - One-shot script for cron job
    - Runs all 15-minute checks
    - Runs OpenAI check every 120 minutes
      (tracks last OpenAI check time in DB)

  backend/migrate_health.py
    - Creates health_checks table

render.yaml cron job:
  name: est8go-health-cron
  schedule: "*/15 * * * *"
  command: python backend/run_health_check.py

Super Admin Dashboard additions:
  - New "Health" tab showing all system statuses
  - Each system: icon + name + status + last checked
  - Alert history list (last 7 days)
  - "Run Full Check" button
  - Auto-refresh every 60 seconds
  - Red banner at top of ALL tabs when critical alert active
  - Amber badge on Health nav item when warnings exist

Email alert format (on CRITICAL):
  Subject: EST8GO ALERT: [System] is down
  Body:
    System: WhatsApp API
    Status: CRITICAL
    Detail: Token expired — all tenant bots offline
    Time: 14:32 WAT 25 May 2026
    Action needed: Refresh WhatsApp access token
    [View Dashboard] button

ESTIMATED COST:
  Render cron job:    ~1,500/month
  OpenAI checks:      ~216/month (120-min intervals)
  Total:              ~1,716/month
  ROI vs 1hr outage:  29x return

ISSUES TRACKER (part of Health Monitor):
Database table: platform_issues
  - id, title, description, severity, status
  - affected_area, tenant_id, assigned_to
  - diagnosis, fix_applied, resolved_at
  - created_at, updated_at

Super Admin Dashboard — Issues tab:
  - View all open/resolved issues
  - Create new issue manually
  - Auto-created by health monitor on critical alerts
  - Severity: critical/high/medium/low
  - Status: open/in_progress/resolved
  - Assign to staff member
  - Add diagnosis and fix notes
  - Resolve with one click
  - Export as CSV

API endpoints:
  GET  /admin/issues — list all issues
  POST /admin/issues — create new issue
  PATCH /admin/issues/{id} — update status/notes
  POST /admin/issues/{id}/resolve — mark resolved

ISSUES.md sync:
  When issue resolved in dashboard →
  append to ISSUES.md via git commit
  So Claude always has current issue history

### 3. Tenant Recovery Speed Settings
Add to business dashboard Settings section:
- Recovery speed: Gentle / Standard / Aggressive
- Send window: configurable start/end time
- Auto-stop keywords: add custom keywords
- Store in tenant settings or company_profiles table

### 4. Diaspora Trust Certificate PDF
- backend/app/services/trust_certificate_service.py
- Uses WeasyPrint or ReportLab
- Shows: trust score, GPS coords, docs verified, Est8Go seal
- Deducts 20 credits on generation
- Available from Trust tab in dashboard

### 5. Super Admin MMEF Monitoring
- Show MMEF compliance per tenant in Super Admin
- Flag tenants approaching grace period
- Manual override for special cases
- Background job: run_mmef_check.py daily

### 6. Market Intelligence (Phase 3)
- Property price trends by location
- Transaction volume by area
- Trust score distribution
- Available at /admin/market-intelligence

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
