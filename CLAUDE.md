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

### 2. Tenant Recovery Speed Settings
Add to business dashboard Settings section:
- Recovery speed: Gentle / Standard / Aggressive
- Send window: configurable start/end time
- Auto-stop keywords: add custom keywords
- Store in tenant settings or company_profiles table

### 3. Diaspora Trust Certificate PDF
- backend/app/services/trust_certificate_service.py
- Uses WeasyPrint or ReportLab
- Shows: trust score, GPS coords, docs verified, Est8Go seal
- Deducts 20 credits on generation
- Available from Trust tab in dashboard

### 4. Super Admin MMEF Monitoring
- Show MMEF compliance per tenant in Super Admin
- Flag tenants approaching grace period
- Manual override for special cases
- Background job: run_mmef_check.py daily

### 5. Market Intelligence (Phase 3)
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
