/**
 * whatsapp.js — WhatsApp Cloud API client (Meta Graph API)
 * Handles sending text messages and reading delivery status.
 * Docs: https://developers.facebook.com/docs/whatsapp/cloud-api
 */

const GRAPH_API_VERSION = 'v20.0';
const BASE_URL = `https://graph.facebook.com/${GRAPH_API_VERSION}`;

/**
 * Send a plain text WhatsApp message to a recipient.
 * @param {string} to   - Recipient's phone number in E.164 format (e.g. "2348031234567")
 * @param {string} text - Message body (supports *bold* and _italic_ WhatsApp formatting)
 * @returns {Promise<object>} Meta API response
 */
async function sendTextMessage(to, text) {
  const phoneNumberId = process.env.WHATSAPP_PHONE_NUMBER_ID;
  const token         = process.env.WHATSAPP_ACCESS_TOKEN;

  if (!phoneNumberId || !token) {
    console.log(`[WhatsApp API Simulated] No Meta credentials in .env — simulated send to ${to}: "${text.substring(0, 60)}..."`);
    return { simulated: true, to, text };
  }

  const url  = `${BASE_URL}/${phoneNumberId}/messages`;
  const body = {
    messaging_product: 'whatsapp',
    recipient_type:    'individual',
    to:                to,
    type:              'text',
    text: {
      preview_url: false,
      body:        text
    }
  };

  const response = await fetch(url, {
    method:  'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type':  'application/json'
    },
    body: JSON.stringify(body)
  });

  const data = await response.json();

  if (!response.ok) {
    console.error('[WhatsApp API] Send error:', JSON.stringify(data, null, 2));
    throw new Error(`WhatsApp API error ${response.status}: ${data?.error?.message || 'Unknown error'}`);
  }

  console.log(`[WhatsApp] ✓ Message sent to ${to}: "${text.substring(0, 60)}..."`);
  return data;
}

/**
 * Mark an incoming message as read (shows double blue ticks to buyer).
 * @param {string} messageId - The wamid of the received message
 */
async function markAsRead(messageId) {
  const phoneNumberId = process.env.WHATSAPP_PHONE_NUMBER_ID;
  const token         = process.env.WHATSAPP_ACCESS_TOKEN;

  const url  = `${BASE_URL}/${phoneNumberId}/messages`;
  const body = {
    messaging_product: 'whatsapp',
    status:            'read',
    message_id:        messageId
  };

  try {
    await fetch(url, {
      method:  'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type':  'application/json'
      },
      body: JSON.stringify(body)
    });
  } catch (err) {
    // Non-critical — don't break flow if read receipt fails
    console.warn('[WhatsApp] Could not mark message as read:', err.message);
  }
}

module.exports = { sendTextMessage, markAsRead };
