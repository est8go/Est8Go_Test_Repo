# Kora Pilot — Final Feature List & MoSCoW Prioritization

**Project:** Kora (WhatsApp Lead Capture & Qualification for Bravies Homz)  
**Target Timeline:** 5-Day Team Build (Pilot MVP)  
**Sources:** `requirements.md`, `screen-specification.md`

---

## 1. Executive Summary & 5-Day Build Scope

The primary objective of Kora's 5-day build is to solve Bravies Homz’s lead leakage: capturing after-hours buyer enquiries arriving on WhatsApp, instantly acknowledging and qualifying them via automated questions, and handing them off to an assigned salesperson with a visible follow-up commitment.

To ensure delivery within a **5-day sprint**, the **Must-Have** list is strictly capped at **6 core features**. 

### Cut-First Analysis (Scoping Down to ≤6 Must-Haves)
In the initial draft of `requirements.md`, 7 functional requirements were marked as "Must" (FR-01 through FR-07), in addition to several UI features described in `screen-specification.md`. Attempting all of them in 5 days risks shipping a half-finished system. Here is which features qualified for cutting/demoting first and why:

1. **Cut First — Automated Scheduled Push Notifications & Reminder Engine (from FR-06):**
   - *Original Scope:* A background cron/scheduler engine that delivers active push alerts (via WhatsApp, SMS, or email) when a follow-up becomes due or overdue.
   - *Why Demoted to Should Have:* Implementing background job workers, queue management, and external notification retries introduces high infrastructure risk in a 5-day sprint. The team can achieve 90% of the business outcome by displaying the follow-up due date and an visual "Overdue" status badge directly inside the Lead List web interface, without needing background push infrastructure.
2. **Cut Second — Standalone Manual Lead Lifecycle State Engine (from FR-04):**
   - *Original Scope:* Independent UI controls and transition guards allowing staff to arbitrarily change lead states between `New`, `Awaiting qualification`, `Qualified`, `Handed off`, and `Closed`.
   - *Why Demoted to Should Have:* The core lifecycle can be automatically derived from system events (`New` on inbound message, `Awaiting qualification` during chatbot Q&A, `Qualified` upon completion, `Handed off` upon salesperson assignment, `Closed` upon completing the follow-up). Eliminating manual state-override controls saves significant frontend modal and validation logic.
3. **Cut Third — Self-Service Admin Configuration UI (FR-09):**
   - *Original Scope:* Web-based admin dashboard to edit qualification prompts, response templates, and routing rules.
   - *Why Demoted to Should Have:* For a single pilot agency (Bravies Homz), these settings can be defined in environment variables or a configuration file in minutes, saving 2 days of frontend form and validation engineering.
4. **Cut Fourth — Dedicated In-App Reporting Dashboard (FR-08):**
   - *Original Scope:* Interactive visual analytics dashboard showing response time curves and qualification rates.
   - *Why Demoted to Should Have:* Explicitly ruled out by `screen-specification.md` ("There is no separate CRM, reporting dashboard, or inspection-booking screen in this scope"). Pilot metrics at Day 30 can be calculated via SQL queries or spreadsheet export.

---

## 2. MoSCoW Feature Table

| Feature | Description | MoSCoW Category | Reason |
| :--- | :--- | :--- | :--- |
| **Inbound WhatsApp Enquiry Capture** | Ingests incoming buyer messages via WhatsApp Business webhook and creates a centralized lead record with timestamp, phone number, and conversation context. | **Must have** | The product is broken and pointless without this; it is the foundational data intake for the entire system. |
| **Immediate 24/7 Automated Acknowledgement** | Dispatches an approved instant greeting to any incoming enquiry at all hours (especially after-hours) and logs the first-response timestamp. | **Must have** | Core value proposition; directly eliminates buyer drop-off caused by delayed responses outside working hours. |
| **Conversational WhatsApp Lead Qualification** | Automated multi-turn conversational script asking for buyer name, preferred location, property type, budget, and purchase timeline, saving each answer. | **Must have** | Core value proposition; without qualification, sales attendants are still handed raw, unqualified chats requiring manual vetting. |
| **Sales-Team Lead Handoff & Assignment** | Assigns or routes a qualified lead to a designated salesperson or customer-service rep, establishing unambiguous individual ownership. | **Must have** | Broken without it; without designated ownership, leads sit unaddressed, recreating the exact memory-dependent failure mode. |
| **Central Lead List & Status Overview** | Web workspace table displaying buyer identity, status, assigned owner, last message timestamp, first-response time, and next follow-up due time. | **Must have** | Pointless without visibility; agency staff and founders must have a unified screen to see active leads and identify uncontacted prospects. |
| **Lead Workspace & Follow-Up Task Management** | Dedicated lead screen presenting conversation history, captured qualification details, next follow-up due date setting, and completion action. | **Must have** | Sales attendants must see conversational context before calling the prospect, and must be able to record follow-up completion to close the loop. |
| **Automated Follow-Up Reminders & Alerts** | Asynchronous scheduler sending external alerts (WhatsApp/SMS/email) to lead owners when follow-up tasks become due or overdue. | **Should have** | Important for proactive agent alerting, but the product works without it by having reps check the Overdue list view. High infrastructure complexity for 5 days. |
| **Lead List Filtering Views (My / All / Overdue)** | Tabbed quick-filters on the Lead List allowing staff to toggle between their personal leads, the agency roster, and overdue follow-ups. | **Should have** | Highly valuable for daily triage, but basic table sorting by due date allows staff to operate if tab filtering is simplified. |
| **Visual Overdue Marker & Highlighting** | Distinct visual badges or row highlights flagging leads whose follow-up deadline has expired. | **Should have** | Aids rapid visual scanning for managers, but overdue status is already deduced from the displayed due date. |
| **Manual Qualification Data Correction** | Form inputs in the Lead Workspace enabling staff to edit, correct, or append buyer qualification details captured by the bot. | **Should have** | Important for correcting buyer typos or adding details learned during calls, but initial bot-captured data suffices for Day 1 handoff. |
| **Lead Reassignment Control** | UI dropdown in the Lead Workspace allowing managers to reassign an active lead to a different team member. | **Should have** | Useful when staff are unavailable, but for a 3-person pilot team, initial automated or static routing is sufficient. |
| **Close Lead with Mandatory Reason** | Structured closure flow requiring agents to input a standard reason (e.g. invalid contact, budget mismatch, deal lost) before archiving a lead. | **Should have** | Important for pilot reporting and pipeline hygiene, but leads can be marked complete/inactive without forced multi-step modals. |
| **Conversation & Action History Audit Trail** | Chronological persistent log tracking lead status updates, reassignments, task completions, and system events over time. | **Should have** | Valuable for post-mortem analysis and team accountability, but raw WhatsApp chat logs and current lead state provide primary operational context. |
| **Response & Follow-Up Performance Reporting** | Aggregated metrics reporting average response times, qualification percentages, and overdue follow-up rates across selectable periods. | **Should have** | Vital for the Day-30 founder pilot review, but can be derived via SQL/Excel export rather than building an in-app reporting UI. |
| **Self-Service Pilot Configuration UI** | Administrative interface to edit qualification questions, welcome message copy, team rosters, and assignment rules without code changes. | **Should have** | High convenience for the agency, but pilot parameters are stable and can be configured via environment/config files in a 5-day sprint. |
| **Inspection Appointment Scheduling** | In-app module to coordinate, schedule, and confirm physical property inspection dates, times, and locations directly from the lead record. | **Could have** | Nice convenience, but explicitly excluded from screen spec; real estate agents routinely schedule inspections directly over WhatsApp/phone. |
| **Dynamic Conversational Fallback & Clarification** | Natural-language branching to handle non-standard buyer answers, re-prompting politely when required qualification fields are ambiguous. | **Could have** | Improves user experience, but a standard sequential structured question sequence is adequate for the initial pilot. |
| **WhatsApp Media & Attachment Rendering** | Ability to view flyer images, PDFs, voice notes, or location pins sent by the buyer directly inside the Lead Workspace context view. | **Could have** | Real estate buyers frequently share property screenshots, but plain text captures the vital qualification criteria (budget, location, timeline). |
| **Lead Search & Free-Text Filter** | Search bar on the Lead List allowing instant lookup by buyer phone number, buyer name, or keyword. | **Could have** | Convenient as lead volume grows, but with 10–30 pilot leads per week, standard list browsing is manageable. |
| **Full CRM & Deal Pipeline Management** | Multi-stage deal pipelines, negotiation tracking, commission calculations, and property transaction ledgers. | **Won't have (this build)** | Explicitly out of scope; Kora is focused strictly on front-of-funnel capture, qualification, and handoff, not closing or accounting. |
| **Property Inventory & Public Listing Portal** | Property database, photo catalogs, listing fee collection, unit availability trackers, and buyer-facing property search portal. | **Won't have (this build)** | Explicitly out of scope; Bravies Homz publishes listings on Instagram/Facebook; Kora only processes the resulting inbound chats. |
| **Automated AI Negotiation & Deal Closing** | Autonomous agent attempting to negotiate prices, recommend alternative inventory, or execute purchase contracts without human involvement. | **Won't have (this build)** | Explicitly out of scope; Nigerian real estate transactions require human agent trust, physical inspections, and personal verification. |
| **Automated Lost-Deal Causality Analytics** | Algorithmic attribution claiming that delayed responses or missed tasks directly caused a specific lost sale. | **Won't have (this build)** | Explicitly out of scope; the pilot records empirical operational timestamps and activity rates, avoiding speculative financial causality. |
| **Third-Party CRM, Ad, & Telephony Integrations** | Pre-built bi-directional connectors for HubSpot, Salesforce, Meta Ads Lead forms, payment gateways (Paystack/Stripe), or Twilio voice. | **Won't have (this build)** | Explicitly out of scope; introduces external API dependencies and integration fragility during a tightly scoped 5-day build. |
| **Multi-Agency Tenancy & Self-Serve SaaS Architecture** | Multi-tenant organization isolation, agency billing portals, self-registration, and multi-city localization. | **Won't have (this build)** | Explicitly out of scope; the system is custom-tailored for Bravies Homz's single-agency 3-month pilot validation. |
| **Custom AI Model Training & Predictive Lead Scoring** | Machine learning models trained on proprietary agency chat logs to predict buyer closing likelihood or assign algorithmic lead scores. | **Won't have (this build)** | Explicitly out of scope; unproven complexity that distracts from core responsiveness and visibility metrics. |
| **In-App Billing, Subscription, & Invoicing Tools** | Payment processing, recurring subscription management, CAC/LTV forecasting, and pilot invoicing workflows. | **Won't have (this build)** | Explicitly out of scope; pilot pricing is handled via direct contract and traditional invoice. |

---

## 3. Five-Day Team Build Allocation Plan

```
Day 1: Inbound WhatsApp Webhook & Immediate Acknowledgement (FR-01, FR-02)
Day 2: Conversational Qualification State Engine (FR-03)
Day 3: Handoff Engine & Lead List Screen (FR-05, FR-07 / Screen Spec §2)
Day 4: Lead Workspace Screen & Follow-Up Task Logging (Screen Spec §3, FR-06 core)
Day 5: End-to-End Testing with Bravies Homz Test Phone, Bug Fixes, & Seed Data (FR-01 → FR-07)
```

With this strict 6-feature Must-Have scope, the engineering team has a deterministic, zero-bloat path to delivering a functional pilot on schedule.
