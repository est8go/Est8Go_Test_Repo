/**
 * bot.js — Kora qualification bot logic
 * Handles the multi-turn WhatsApp conversation:
 * 1. Receives a buyer message
 * 2. Tracks which qualification question we're on (per phone number)
 * 3. Saves answers to the lead record
 * 4. Routes to a salesperson once qualified
 */

const db = require('./db');
const { sendTextMessage } = require('./whatsapp');

// ─────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────

function nowISO() {
  return new Date().toISOString();
}

function generateId(prefix) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 6).toUpperCase()}`;
}

/** Round-robin team assignment */
function assignTeamMember() {
  const team = db.get('team').filter({ active: true }).value();
  if (!team.length) return null;
  const idx    = db.get('config.roundRobinIndex').value();
  const member = team[idx % team.length];
  db.set('config.roundRobinIndex', (idx + 1) % team.length).write();
  return member;
}

/** Get the list of qualification questions from config */
function getQuestions() {
  return db.get('config.qualificationQuestions').value();
}

// ─────────────────────────────────────────────────────────
// Core message handler — called for every inbound message
// ─────────────────────────────────────────────────────────

/**
 * Process one inbound WhatsApp message from a buyer.
 * @param {string} from        - Sender phone number (E.164, no +)
 * @param {string} messageText - Text content of the message
 * @param {string} messageId   - WhatsApp message ID (wamid)
 * @param {number} timestamp   - Unix timestamp from webhook
 */
async function handleInboundMessage(from, messageText, messageId, timestamp) {
  const text = (messageText || '').trim();
  const questions = getQuestions();
  const botReplies = [];

  // Helper inside this invocation to track replies
  async function reply(leadRef, msg) {
    botReplies.push(msg);
    await sendAndRecord(leadRef, msg);
  }

  // ── Find or create lead record ─────────────────────────
  let lead = db.get('leads').find({ whatsapp: from }).value();

  if (!lead) {
    // FR-01: New enquiry — create lead record
    const enquiryDate = timestamp ? new Date(timestamp * 1000).toISOString() : nowISO();
    lead = {
      id:               generateId('LEAD'),
      whatsapp:         from,
      buyerName:        null,
      status:           'New',
      owner:            null,
      ownerId:          null,
      enquiryTime:      enquiryDate,
      firstResponseTime: null,
      lastMessageTime:  nowISO(),
      qualStep:         0,          // which question index we're asking next
      qualification:    {},         // collected answers
      task:             null,
      closureReason:    null,
      chat:             [
        {
          sender: 'buyer',
          text:   text,
          time:   nowISO(),
          msgId:  messageId || generateId('MSG')
        }
      ],
      createdAt:  nowISO(),
      updatedAt:  nowISO()
    };

    db.get('leads').push(lead).write();
    console.log(`[Bot] New lead created: ${lead.id} from ${from}`);

    // FR-02: Immediate 24/7 acknowledgement — send right away
    const greeting = process.env.GREETING_MESSAGE ||
      `Hello! Welcome to ${process.env.AGENCY_NAME || 'Bravies Homz'} 🏡\n\nI'm Kora, your 24/7 digital property advisor. To help match you with the best verified options, may I have your *full name* please?`;

    await reply(lead, greeting);
    setFirstResponseTime(lead);

    // Update status to Awaiting qualification
    updateLead(lead, { status: 'Awaiting qualification', qualStep: 1 });
    return { success: true, replies: botReplies, lead: db.get('leads').find({ id: lead.id }).value() };
  }

  // ── Existing lead — record new buyer message ───────────
  lead.chat.push({ sender: 'buyer', text, time: nowISO(), msgId: messageId || generateId('MSG') });
  updateLead(lead, { lastMessageTime: nowISO(), chat: lead.chat });

  // ── Already closed — politely inform ──────────────────
  if (lead.status === 'Closed') {
    const closedMsg = `Hi ${lead.buyerName || 'there'}! This enquiry was previously closed. ` +
      `Our team at *${process.env.AGENCY_NAME || 'Bravies Homz'}* has been notified of your new message and will reconnect with you shortly. 🙏`;
    await reply(lead, closedMsg);
    return { success: true, replies: botReplies, lead: db.get('leads').find({ id: lead.id }).value() };
  }

  // ── Already handed off — confirm and reassure ──────────
  if (lead.status === 'Handed off') {
    const handoffMsg = `Hi ${lead.buyerName || 'there'}! Your enquiry is active with *${lead.owner || 'our sales team'}*, who has been updated with your message. 📞`;
    await reply(lead, handoffMsg);
    return { success: true, replies: botReplies, lead: db.get('leads').find({ id: lead.id }).value() };
  }

  // ── Qualification flow ─────────────────────────────────
  const step = lead.qualStep || 0;

  if (step > 0 && step <= questions.length) {
    const answered = questions[step - 1]; // question we just got the answer to
    lead.qualification[answered.key] = text;

    // Update buyer name on lead root if this was the name question
    if (answered.key === 'name') {
      updateLead(lead, { buyerName: text });
    }

    const nextStep = step + 1;

    if (nextStep <= questions.length) {
      // Ask next question
      const nextQ = questions[nextStep - 1];
      await reply(lead, nextQ.question);
      updateLead(lead, { qualStep: nextStep, qualification: lead.qualification, chat: lead.chat });
    } else {
      // All questions answered — FR-03 complete → FR-05 handoff
      await qualifyAndHandOff(lead, reply);
    }

    return { success: true, replies: botReplies, lead: db.get('leads').find({ id: lead.id }).value() };
  }

  // ── Fallback (if outside step range) ───────────────────
  const currentQ = questions[Math.max(0, step - 1)];
  if (currentQ) {
    await reply(lead, currentQ.question);
  }
  return { success: true, replies: botReplies, lead: db.get('leads').find({ id: lead.id }).value() };
}

// ─────────────────────────────────────────────────────────
// Qualification complete → assign to salesperson
// ─────────────────────────────────────────────────────────

async function qualifyAndHandOff(lead, replyFn) {
  const q = lead.qualification;
  const reply = replyFn || (async (l, m) => await sendAndRecord(l, m));

  // Build a readable summary
  const summary =
    `✅ *Enquiry Qualified!*\n\n` +
    `Here is your property profile:\n` +
    `• 📍 Location: *${q.location || 'Not specified'}*\n` +
    `• 🏠 Property: *${q.type || 'Not specified'}*\n` +
    `• 💰 Working Budget: *${q.budget || 'Not specified'}*\n` +
    `• 📅 Timeline: *${q.timeline || 'Not specified'}*\n\n` +
    `I have assigned your file to our senior sales team. A dedicated consultant will contact you with verified options shortly. Thank you! 🙏`;

  await reply(lead, summary);

  // Assign to next team member (round-robin)
  const assignee = assignTeamMember();

  // Create follow-up task (FR-06)
  const task = {
    id:          generateId('TASK'),
    action:      `Call ${lead.buyerName} — ${q.type || 'property enquiry'} in ${q.location || 'Lagos'} (Budget: ${q.budget || 'TBC'})`,
    owner:       assignee ? assignee.name : 'Unassigned',
    ownerId:     assignee ? assignee.id   : null,
    dueTime:     new Date(Date.now() + 2 * 60 * 60 * 1000).toISOString(), // 2 hours from now
    state:       'Open',
    isOverdue:   false,
    createdAt:   nowISO()
  };

  updateLead(lead, {
    status:          'Handed off',
    owner:           assignee ? assignee.name : 'Unassigned',
    ownerId:         assignee ? assignee.id   : null,
    qualification:   lead.qualification,
    task:            task,
    qualStep:        questions.length + 1
  });

  console.log(`[Bot] Lead ${lead.id} qualified → assigned to ${task.owner}`);

  // Notify the assigned team member (via WhatsApp if they have a number, or just log)
  console.log(`[Bot] 🔔 Notify ${task.owner}: New qualified lead from ${lead.buyerName} (${lead.whatsapp})`);
}

// ─────────────────────────────────────────────────────────
// Utility functions
// ─────────────────────────────────────────────────────────

async function sendAndRecord(lead, text) {
  try {
    await sendTextMessage(lead.whatsapp, text);
    lead.chat = lead.chat || [];
    lead.chat.push({ sender: 'kora', text, time: nowISO() });
    db.get('leads').find({ id: lead.id }).assign({ chat: lead.chat, updatedAt: nowISO() }).write();
  } catch (err) {
    console.error(`[Bot] Failed to send message to ${lead.whatsapp}:`, err.message);
  }
}

function setFirstResponseTime(lead) {
  if (!lead.firstResponseTime) {
    const frt = new Date() - new Date(lead.enquiryTime);
    const frtSecs = Math.round(frt / 1000);
    db.get('leads').find({ id: lead.id }).assign({
      firstResponseTime: `${frtSecs}s`,
      firstResponseAt:   nowISO()
    }).write();
  }
}

function updateLead(lead, patch) {
  Object.assign(lead, patch, { updatedAt: nowISO() });
  db.get('leads').find({ id: lead.id }).assign({ ...patch, updatedAt: nowISO() }).write();
}

module.exports = { handleInboundMessage };
