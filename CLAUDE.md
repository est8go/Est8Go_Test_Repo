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

## DO NOT OVERWRITE ⚠️
- backend/app/conversations/intent_filter.py
- backend/app/conversations/templates.py
- backend/app/services/conversation_service.py
- backend/app/services/chatbot/kora_behavior.py
- backend/templates/business_dashboard.html
- backend/templates/login.html

## NEXT TASKS (in order)
1. Super Admin Dashboard — rebuild backend/templates/super_admin_dashboard.html
   - Brand: #0F172A bg, #111827 cards, #4338CA indigo, #10B981 emerald
   - No Tailwind CDN, no backdrop-filter, solid surfaces only
   - 5 bottom tabs: Pulse, Tenants, Verify, Audit, Menu
   - Menu drawer: Staff, Billing, Conversation Tracer, Risk Monitor
   - Tenant: suspend, reactivate, delete with DELETE confirmation
   - Staff: role assignment superuser/super_staff
   - Conversation Tracer: search by date/phone/tenant, full thread, export
   - Verify queue: property images + GPS link + document checklist
   - Auto-refresh Pulse tab
   - sanitise() on all user data

2. Backend endpoints needed for Super Admin:
   - GET/GET/{id}/export /admin/conversations (create conversations_router.py)
   - PATCH /admin/tenants/{id}/suspend and /reactivate
   - DELETE /admin/tenants/{id} soft delete
   - PATCH /admin/staff/{id}/role

3. Tenant onboarding UI — 5-step flow

4. Drop-off recovery live testing

5. Set admin phone numbers for lead alerts
