/**
 * server.js — Kora Pilot Backend
 *
 * Responsibilities:
 *   1. Serve the static dashboard (index.html + assets)
 *   2. Handle WhatsApp Business Cloud API webhook (receive messages)
 *   3. Expose REST API endpoints for the dashboard (leads, team, config)
 *
 * Start: node server.js
 * Docs:  https://developers.facebook.com/docs/whatsapp/cloud-api/guides/set-up-webhooks
 */

require('dotenv').config();

const express = require('express');
const cors    = require('cors');
const path    = require('path');
const db      = require('./db');
const { handleInboundMessage } = require('./bot');
const { markAsRead }           = require('./whatsapp');

const app  = express();
const PORT = process.env.PORT || 3000;

// ─────────────────────────────────────────────────────────
// Middleware
// ─────────────────────────────────────────────────────────

app.use(cors());
app.use(express.json());

// Serve all static files (dashboard, CSS, JS) from this directory
app.use(express.static(path.join(__dirname)));

// ─────────────────────────────────────────────────────────
// WEBHOOK — GET: Verification handshake (Meta calls this once)
// ─────────────────────────────────────────────────────────

app.get('/webhook', (req, res) => {
  const mode      = req.query['hub.mode'];
  const token     = req.query['hub.verify_token'];
  const challenge = req.query['hub.challenge'];

  if (mode === 'subscribe' && token === process.env.WEBHOOK_VERIFY_TOKEN) {
    console.log('[Webhook] ✓ Verified by Meta');
    return res.status(200).send(challenge);
  }

  console.warn('[Webhook] ✗ Verification failed — check WEBHOOK_VERIFY_TOKEN in .env');
  res.sendStatus(403);
});

// ─────────────────────────────────────────────────────────
// WEBHOOK — POST: Receive inbound WhatsApp messages from Meta
// ─────────────────────────────────────────────────────────

app.post('/webhook', async (req, res) => {
  // Always respond 200 immediately — Meta will retry if we're slow
  res.sendStatus(200);

  const body = req.body;

  // Safety check — only process WhatsApp messages
  if (body?.object !== 'whatsapp_business_account') return;

  const entries = body.entry || [];

  for (const entry of entries) {
    const changes = entry.changes || [];

    for (const change of changes) {
      const value    = change.value || {};
      const messages = value.messages || [];

      for (const message of messages) {
        // Only process text messages (ignore status updates, reactions, etc.)
        if (message.type !== 'text') {
          console.log(`[Webhook] Skipping message type: ${message.type}`);
          continue;
        }

        const from      = message.from;        // e.g. "2348031234567"
        const text      = message.text?.body;
        const messageId = message.id;
        const timestamp = parseInt(message.timestamp, 10);

        console.log(`[Webhook] ← Inbound from ${from}: "${text?.substring(0, 60)}"`);

        // Mark the message as read (shows blue double tick to buyer)
        await markAsRead(messageId);

        // Run the qualification bot
        try {
          await handleInboundMessage(from, text, messageId, timestamp);
        } catch (err) {
          console.error(`[Bot] Error processing message from ${from}:`, err.message);
        }
      }
    }
  }
});

// ─────────────────────────────────────────────────────────
// REST API — User-Facing WhatsApp Automated Chatbot
// ─────────────────────────────────────────────────────────

/** POST /api/chat/message — Process buyer message through automated bot */
app.post('/api/chat/message', async (req, res) => {
  const { phone, text, messageId } = req.body;
  if (!text || !text.trim()) {
    return res.status(400).json({ success: false, error: 'Message text is required' });
  }

  const senderPhone = (phone || '2348035550192').replace(/[^0-9]/g, '');
  const msgId = messageId || `WEB-${Date.now()}`;
  const timestamp = Math.floor(Date.now() / 1000);

  try {
    const result = await handleInboundMessage(senderPhone, text.trim(), msgId, timestamp);
    res.json({
      success: true,
      replies: result.replies || [],
      lead: result.lead
    });
  } catch (err) {
    console.error('[API Chat] Error handling message:', err.message);
    res.status(500).json({ success: false, error: err.message });
  }
});

/** GET /api/chat/history/:phone — Retrieve chat history for user-facing WhatsApp chatbot */
app.get('/api/chat/history/:phone', (req, res) => {
  const phone = req.params.phone.replace(/[^0-9]/g, '');
  const lead = db.get('leads').find({ whatsapp: phone }).value();
  if (!lead) {
    return res.json({ success: true, exists: false, chat: [] });
  }
  res.json({ success: true, exists: true, lead, chat: lead.chat || [] });
});

// Explicit route for user-facing WhatsApp chatbot
app.get('/chat', (req, res) => {
  res.sendFile(path.join(__dirname, 'chat.html'));
});

// Explicit route for admin dashboard
app.get('/admin', (req, res) => {
  res.sendFile(path.join(__dirname, 'index.html'));
});

// ─────────────────────────────────────────────────────────
// REST API — Leads (for the dashboard)
// ─────────────────────────────────────────────────────────

/** GET /api/leads — return all leads, newest first */
app.get('/api/leads', (req, res) => {
  const leads = db.get('leads')
    .orderBy('createdAt', 'desc')
    .value();

  // Automatically flag overdue tasks
  const now = Date.now();
  const enriched = leads.map(lead => {
    if (lead.task && lead.task.dueTime && lead.task.state === 'Open') {
      lead.task.isOverdue = new Date(lead.task.dueTime).getTime() < now;
    }
    return lead;
  });

  res.json({ success: true, data: enriched, count: enriched.length });
});

/** GET /api/leads/:id — single lead */
app.get('/api/leads/:id', (req, res) => {
  const lead = db.get('leads').find({ id: req.params.id }).value();
  if (!lead) return res.status(404).json({ success: false, error: 'Lead not found' });
  res.json({ success: true, data: lead });
});

/** PATCH /api/leads/:id — update lead fields (assignment, task, closure) */
app.patch('/api/leads/:id', (req, res) => {
  const lead = db.get('leads').find({ id: req.params.id }).value();
  if (!lead) return res.status(404).json({ success: false, error: 'Lead not found' });

  const allowed = ['status', 'owner', 'ownerId', 'task', 'closureReason', 'buyerName',
                   'qualification', 'nextFollowUp'];
  const patch   = {};
  for (const key of allowed) {
    if (req.body[key] !== undefined) patch[key] = req.body[key];
  }
  patch.updatedAt = new Date().toISOString();

  db.get('leads').find({ id: req.params.id }).assign(patch).write();
  res.json({ success: true, data: db.get('leads').find({ id: req.params.id }).value() });
});

/** POST /api/leads/:id/close — close a lead with mandatory reason */
app.post('/api/leads/:id/close', (req, res) => {
  const { reason, notes } = req.body;
  if (!reason) return res.status(400).json({ success: false, error: 'Closure reason is required' });

  const lead = db.get('leads').find({ id: req.params.id }).value();
  if (!lead) return res.status(404).json({ success: false, error: 'Lead not found' });

  db.get('leads').find({ id: req.params.id }).assign({
    status:        'Closed',
    closureReason: notes ? `${reason} — ${notes}` : reason,
    closedAt:      new Date().toISOString(),
    updatedAt:     new Date().toISOString(),
    ...(lead.task ? { task: { ...lead.task, state: 'Completed', isOverdue: false } } : {})
  }).write();

  res.json({ success: true });
});

/** POST /api/leads/:id/complete-task — mark follow-up done, schedule next */
app.post('/api/leads/:id/complete-task', (req, res) => {
  const { notes, nextAction, nextDueHours } = req.body;
  const lead = db.get('leads').find({ id: req.params.id }).value();
  if (!lead) return res.status(404).json({ success: false, error: 'Lead not found' });

  const completedTask = { ...lead.task, state: 'Completed', isOverdue: false, completedAt: new Date().toISOString(), completionNote: notes };

  let patch = { updatedAt: new Date().toISOString() };

  if (nextAction) {
    const dueHours = nextDueHours || 24;
    patch.task = {
      id:        `TASK-${Date.now()}`,
      action:    nextAction,
      owner:     lead.owner,
      ownerId:   lead.ownerId,
      dueTime:   new Date(Date.now() + dueHours * 60 * 60 * 1000).toISOString(),
      state:     'Open',
      isOverdue: false,
      createdAt: new Date().toISOString()
    };
    patch.status = 'Handed off';
  } else {
    patch.task   = completedTask;
    patch.status = 'Closed';
  }

  db.get('leads').find({ id: req.params.id }).assign(patch).write();
  res.json({ success: true, data: db.get('leads').find({ id: req.params.id }).value() });
});

// ─────────────────────────────────────────────────────────
// REST API — Team Members
// ─────────────────────────────────────────────────────────

app.get('/api/team', (req, res) => {
  res.json({ success: true, data: db.get('team').value() });
});

app.post('/api/team', (req, res) => {
  const { name, role } = req.body;
  if (!name) return res.status(400).json({ success: false, error: 'Name is required' });
  const member = { id: `tm-${Date.now()}`, name, role: role || 'Sales Attendant', active: true };
  db.get('team').push(member).write();
  res.status(201).json({ success: true, data: member });
});

// ─────────────────────────────────────────────────────────
// REST API — Analytics (for Day-30 pilot review)
// ─────────────────────────────────────────────────────────

app.get('/api/analytics', (req, res) => {
  const leads = db.get('leads').value();
  const now   = Date.now();

  const total     = leads.length;
  const qualified = leads.filter(l => ['Qualified', 'Handed off', 'Closed'].includes(l.status)).length;
  const handedOff = leads.filter(l => ['Handed off', 'Closed'].includes(l.status)).length;
  const closed    = leads.filter(l => l.status === 'Closed').length;
  const overdue   = leads.filter(l =>
    l.task?.state === 'Open' && l.task?.dueTime && new Date(l.task.dueTime).getTime() < now
  ).length;

  // Average first response time in seconds
  const withFRT   = leads.filter(l => l.firstResponseAt && l.enquiryTime);
  const avgFRTsec = withFRT.length
    ? Math.round(withFRT.reduce((sum, l) =>
        sum + (new Date(l.firstResponseAt) - new Date(l.enquiryTime)) / 1000, 0
      ) / withFRT.length)
    : null;

  res.json({
    success: true,
    data: {
      total,
      qualified,
      handedOff,
      closed,
      overdue,
      qualificationRate: total ? Math.round((qualified / total) * 100) : 0,
      avgFirstResponseSec: avgFRTsec,
      avgFirstResponseFormatted: avgFRTsec != null ? `${avgFRTsec}s` : 'N/A'
    }
  });
});

// ─────────────────────────────────────────────────────────
// REST API — Config (qualification questions, greeting)
// ─────────────────────────────────────────────────────────

app.get('/api/config', (req, res) => {
  res.json({ success: true, data: db.get('config').value() });
});

app.patch('/api/config', (req, res) => {
  const { qualificationQuestions } = req.body;
  if (qualificationQuestions) {
    db.set('config.qualificationQuestions', qualificationQuestions).write();
  }
  res.json({ success: true, data: db.get('config').value() });
});

// ─────────────────────────────────────────────────────────
// Health check
// ─────────────────────────────────────────────────────────

app.get('/api/health', (req, res) => {
  const waReady = !!(process.env.WHATSAPP_PHONE_NUMBER_ID && process.env.WHATSAPP_ACCESS_TOKEN);
  res.json({
    status:           'ok',
    server:           'Kora Pilot',
    agency:           process.env.AGENCY_NAME || 'Bravies Homz',
    whatsappConfigured: waReady,
    leads:            db.get('leads').size().value(),
    timestamp:        new Date().toISOString()
  });
});

// ─────────────────────────────────────────────────────────
// Catch-all — serve dashboard for any unmatched route
// ─────────────────────────────────────────────────────────

app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'index.html'));
});

// ─────────────────────────────────────────────────────────
// Start
// ─────────────────────────────────────────────────────────

app.listen(PORT, () => {
  console.log('\n╔═══════════════════════════════════════════════╗');
  console.log('║         KORA PILOT SERVER — RUNNING           ║');
  console.log('╠═══════════════════════════════════════════════╣');
  console.log(`║  Dashboard:  http://localhost:${PORT}             ║`);
  console.log(`║  API Health: http://localhost:${PORT}/api/health  ║`);
  console.log(`║  Webhook:    http://localhost:${PORT}/webhook      ║`);
  console.log('╠═══════════════════════════════════════════════╣');

  const waReady = !!(process.env.WHATSAPP_PHONE_NUMBER_ID && process.env.WHATSAPP_ACCESS_TOKEN);
  if (waReady) {
    console.log('║  WhatsApp:   ✓ Configured                     ║');
  } else {
    console.log('║  WhatsApp:   ✗ NOT configured (.env missing)  ║');
    console.log('║  → Copy .env.example to .env and fill values  ║');
  }
  console.log('╚═══════════════════════════════════════════════╝\n');
});
