# EST8GO ISSUES LOG

Use this file to log platform issues before opening Claude.ai.
Format: Date, Status (OPEN/RESOLVED), Problem, Error, Fix applied

---

## ISSUE TEMPLATE (copy this for each new issue)

## Issue #X
Date: 
Status: OPEN
Problem: 
Error message: 
Render logs show: 
Endpoint affected: 
Last time it worked: 
Suspected cause: 
Fix applied: 

---

## ACTIVE ISSUES

(none currently)

---

## RESOLVED ISSUES

## Issue #3
Date: 28 May 2026
Status: RESOLVED
Problem: Property page button opened wrong WhatsApp
Fix: _get_wa_number() normalises to E.164 format,
     falls back to WHATSAPP_BUSINESS_NUMBER env var
     wa.me URL built with proper encoding
Files: backend/app/public/router.py,
       backend/templates/property_detail.html,
       backend/templates/matches_gallery.html

## Issue #2
Date: 26 May 2026
Status: RESOLVED
Problem: Trust Certificate PDF failing on Render
Error: PDF.__init__() takes 1 positional argument but 3 were given
Endpoint affected: GET /listings/{id}/trust-certificate
Suspected cause: WeasyPrint 60.2 uses pydyf internally; version conflict with Render's environment
Fix applied: Pinned weasyprint>=52.5,<53 in requirements.txt (52.x uses cairocffi, no pydyf dependency)
File: backend/requirements.txt

## Issue #1
Date: 25 May 2026
Status: RESOLVED
Problem: Base import error on startup
Error: cannot import name Base from app.database.db
Fix applied: Changed all new model imports to app.database.base
