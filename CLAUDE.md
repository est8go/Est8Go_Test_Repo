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

## NEXT SESSION TASKS (in order)

### 1. Email Service Foundation
Create backend/app/services/email_service.py with:
- send_password_reset(to_email, reset_url)
- send_role_change_request(admin_email, requester, new_role, approve_url)
- send_role_change_result(to_email, approved, role, expiry)
- send_tenant_signup_link(to_email, signup_url, plan, expiry)
- send_onboarding_complete(admin_email, tenant_name)
All emails use Resend SDK. HTML templates inline.

### 2. Password Reset Flow
Backend:
- POST /auth/forgot-password (accepts email, sends reset link)
- POST /auth/reset-password (accepts token + new password)
- PasswordResetToken model (token, user_id, expires_at, used_at)
Frontend:
- Login page: add "Forgot Password?" link
- Login page: fix password visibility toggle (eye icon)
- New reset_password.html page

### 3. Role Change Approval System
Backend:
- RoleChangeRequest model (requester_id, requested_role,
  tenant_id, status, approved_by, expires_at)
- POST /auth/request-role — tenant admin requests elevated role
- GET /admin/role-requests — superuser sees pending requests
- PATCH /admin/role-requests/{id}/approve
- PATCH /admin/role-requests/{id}/reject
Frontend (Super Admin Dashboard):
- New "Role Requests" section in Staff tab
  shows pending requests with Approve/Reject buttons
- Email sent on request + on decision

### 4. Tenant Onboarding UI — 5-step flow
Steps: Business Info → Plan → WhatsApp Setup → Admin Account → Confirm
Frontend: backend/templates/onboarding.html (same stack — no Tailwind)
Backend: reuse POST /admin/tenants — no new endpoints needed

### 5. Drop-off Recovery Live Testing
- Verify reminder_count / last_reminder_sent_at logic in Conversation model
- Test pipeline_router re-engagement flow on live WhatsApp number
- Set admin phone numbers for hot-lead SMS alerts

## BACKEND STACK
- FastAPI + SQLAlchemy + PostgreSQL (Render)
- JWT auth (jose), bcrypt passwords
- Jinja2 templates for all frontend pages
- All frontend: single-file SPA, no Tailwind CDN, no CDN at all
- Brand tokens: --bg:#0F172A --surface:#111827 --surface2:#1F2937 --indigo:#4F46E5 --em:#10B981 --warn:#F59E0B --risk:#F43F5E
- Fonts: Inter (body) + Syne (headings/metrics) from Google Fonts only
- sanitise() XSS function on ALL user data in innerHTML
- Auth.fetch() wrapper in /static/js/auth_guard.js handles JWT headers
