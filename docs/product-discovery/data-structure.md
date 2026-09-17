# Kora Pilot Data Structure

This is a plain-language list of the information Kora needs to retain for the Bravies Homz pilot. A **record** means one saved entry for one thing, such as one lead or one follow-up task.

## Required for the Must-have pilot flow

### 1. Agency

The pilot agency whose enquiries Kora handles.

- Agency ID
- Agency name
- WhatsApp business number
- Operating hours and time zone
- Active/inactive status
- Date created and last updated

### 2. Team member

An agency employee who can own a lead or a follow-up.

- Team member ID
- Agency ID
- Full name
- Role, such as customer-service representative, salesperson, manager, or founder
- Work contact used for notifications
- Active/inactive status
- Date created and last updated

### 3. Buyer contact

The person who sends the WhatsApp enquiry.

- Buyer contact ID
- Agency ID
- WhatsApp phone number
- Name, when supplied
- Date first seen and last updated

### 4. Lead

The agency’s working record for one buyer enquiry.

- Lead ID
- Agency ID
- Buyer contact ID
- Current status: New, Awaiting qualification, Qualified, Handed off, or Closed
- Current assigned team member ID, if assigned
- Lead temperature: Hot, Warm, or Cold
- Lead-temperature reason, such as “Timeline: within 30 days” or “No reply after follow-up”
- Lead-temperature last calculated time
- First enquiry time
- First-response time
- Last customer-message time
- Last agency/system-response time
- Next follow-up due time, if one is open
- Closed time and closure reason, when closed
- Date created and last updated

### 5. Conversation message

One message exchanged in the WhatsApp conversation.

- Message ID
- Lead ID
- Sender: buyer, agency team member, or Kora
- Message text or supported attachment reference
- Direction: incoming or outgoing
- Sent/received time
- Delivery state, if available
- Whether Kora sent it as an automatic acknowledgement or qualification question

### 6. Qualification answer

One answer collected from the buyer during qualification.

- Qualification answer ID
- Lead ID
- Question name: buyer name, preferred location, property type, budget, purchase timeline, or another approved question
- Answer value
- Whether the answer is required for qualification
- Time captured
- Source: buyer message or team member entry

### 7. Lead assignment

The handoff of a qualified lead to the person responsible for acting on it.

- Assignment ID
- Lead ID
- Assigned team member ID
- Assigned by: Kora routing rule or a named team member
- Assigned time
- Assignment state: active, reassigned, or completed
- Reason or routing note, when supplied

### 8. Follow-up task

The specific next action an assigned team member must take for a lead.

- Follow-up task ID
- Lead ID
- Owner team member ID
- Task description
- Due time
- Task state: open, completed, overdue, or cancelled
- Completed time, when completed
- Completion note or next action, when supplied
- Date created and last updated

### 9. Reminder / notification

A recorded alert that tells a team member about a new assignment or overdue follow-up.

- Notification ID
- Recipient team member ID
- Related lead ID
- Related follow-up task ID, if applicable
- Notification type: lead assigned, follow-up due, or follow-up overdue
- Delivery channel
- Scheduled time and sent time
- Delivery state: pending, sent, failed, or acknowledged

## Needed for Should-have features

### 10. Lead activity

A time-stamped record of important changes, used to show the history of a lead.

- Activity ID
- Lead ID
- Activity type: status change, assignment, follow-up update, or system action
- Person or system that made the change
- Before and after values, where relevant
- Time of the change

### 11. Pilot configuration

The agency-specific settings used to tailor Kora without changing the product.

- Configuration ID
- Agency ID
- Approved first-response message
- Qualification questions and their required/optional status
- Team routing rules
- Default follow-up due-time rule
- Configuration version, active status, and last updated time

## Could-have feature

### 12. Inspection appointment

An optional future appointment created from a qualified lead.

- Appointment ID
- Lead ID
- Assigned team member ID
- Proposed date and time
- Confirmed date and time
- Meeting location or property reference
- Appointment state: proposed, confirmed, completed, cancelled, or no-show
- Notes
