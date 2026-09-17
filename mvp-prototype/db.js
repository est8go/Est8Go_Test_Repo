/**
 * db.js — Simple JSON file database using lowdb v1 (CommonJS)
 * Stores leads, conversation state, and team configuration.
 * Persists to leads.json on disk.
 */

const low  = require('lowdb');
const FileSync = require('lowdb/adapters/FileSync');
const path = require('path');

const adapter = new FileSync(path.join(__dirname, 'leads.json'));
const db = low(adapter);

// Seed default structure if file is empty
db.defaults({
  leads: [],
  team: [
    { id: 'tm-1', name: 'Chioma N.',  role: 'Sales Attendant',    active: true },
    { id: 'tm-2', name: 'Emeka O.',   role: 'Senior Salesperson', active: true },
    { id: 'tm-3', name: 'Tunde B.',   role: 'Customer Service',   active: true }
  ],
  config: {
    roundRobinIndex: 0,
    qualificationQuestions: [
      { key: 'name',     label: 'Full Name',          question: 'What is your *full name* please?',                               required: true },
      { key: 'location', label: 'Preferred Location', question: 'Which area of Lagos are you looking in? (e.g. Lekki, Ikoyi, Ajah, Ikeja)',  required: true },
      { key: 'type',     label: 'Property Type',      question: 'What type of property are you looking for? (e.g. duplex, flat, land)',       required: true },
      { key: 'budget',   label: 'Budget Range',       question: 'What is your estimated budget? (e.g. ₦80M – ₦150M)',                        required: false },
      { key: 'timeline', label: 'Purchase Timeline',  question: 'How soon are you planning to buy? (e.g. immediately, 1–3 months)',           required: true }
    ]
  }
}).write();

module.exports = db;
