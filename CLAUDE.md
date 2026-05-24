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
Build background job that:
- Suspended tenants: hidden from UI immediately
- After 30 days: data anonymised (name/email → "[Suspended]")
- After 90 days: hard delete option available to Super Admin
- Deleted tenants: same lifecycle
- Staff: same lifecycle
- Dormant accounts: 12 months inactivity → marked dormant, bot offline
- Create backend/app/services/retention_service.py
- Create backend/run_retention.py (scheduled job)

### 2. Onboarding Step 3 — WhatsApp Setup Simplified
Update backend/templates/onboarding.html Step 3:
- Option A: "Est8Go sets it up for me" (costs 50 credits)
  → Just enter WhatsApp phone number
  → Creates support ticket
  → Sends confirmation email
  → Marks account "Pending WhatsApp Setup"
- Option B: "I have Meta Business account" (advanced, free)
  → Shows Phone ID + Access Token fields
  → Test connection button
- Default to Option A

### 3. Drop-off Recovery Live Testing
Run backend/run_reminders.py against real conversations
Test 4 sequences: awareness, verification, commitment, handshake
Verify WhatsApp messages delivered

### 4. Conversation Engine Testing
Test full WhatsApp flow with real listings:
- Single message extraction (property + location + budget)
- Objection handling
- Handshake + Google Maps delivery
- Session memory (hot resume)

### 5. Super Admin Dashboard
- Clickable stat cards navigate to relevant tabs
- Data retention controls (manual override)
- MMEF compliance monitoring

### 6. Business Dashboard
- Credits tab showing full transaction history
- Service cost display before action executes
- Auto-deduct credits when reel generated
- Auto-deduct credits when priority verification requested

### 7. Diaspora Package
- Trust Certificate PDF generator
- backend/app/services/trust_certificate_service.py
- Uses ReportLab or WeasyPrint
- Shows: trust score, GPS coords, documents verified, Est8Go seal

### 8. Market Intelligence (Phase 3)
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
- Credit deduction uses bonus credits first then purchased
- Paystack webhook uses HMAC with PAYSTACK_SECRET_KEY
- Ledger is immutable — never UPDATE or DELETE
