# Kora Pilot Requirements

Status: draft for the Bravies Homz three-month pilot. Source: `raw-notes.md`.

## Problem statement

Founder-led Nigerian real-estate agencies that generate buyer leads through Facebook and Instagram into WhatsApp are losing prospects when enquiries arrive after operating hours or when manual follow-ups are forgotten. At Bravieshomz, a customer-service representative replies within minutes during working hours, but after-hours enquiries wait until the next day or are missed; qualified leads are then tracked in Excel and reminders depend on memory. Kora must prove that it can immediately capture and qualify these WhatsApp enquiries, hand them to the responsible salesperson, and make follow-up ownership visible, so that the pilot agency can measure whether more leads receive a timely qualified response and fewer go cold.

## Target user

**Primary buyer and pilot sponsor:** the CEO/founder of **Bravies Homz**, a Nigerian real-estate agency that receives buyer enquiries in WhatsApp and has committed to a three-month pilot. The founder’s personal name and pilot price are still unrecorded and must be confirmed before launch.

**Primary operator:** the customer-service representative or sales attendant who receives WhatsApp enquiries, qualifies prospects, records leads in Excel, schedules inspections, and sends follow-up reminders.

**Secondary user:** the sales manager or founder who needs to see which enquiries were answered, qualified, assigned, and still awaiting follow-up.

## Functional requirements

| ID | Feature | Description | Priority |
| --- | --- | --- | --- |
| FR-01 | Inbound WhatsApp capture | Receive each new buyer enquiry from the pilot agency’s WhatsApp business number and create a lead record with message time and conversation context. | Must |
| FR-02 | Immediate acknowledgement | Send an approved first response to every new enquiry, including outside normal operating hours, and record the response timestamp. | Must |
| FR-03 | Lead qualification | Ask a configured set of questions to capture the buyer’s name, contact details, preferred location, property type, budget where supplied, and purchase timeline. | Must |
| FR-04 | Lead status | Mark each enquiry as new, awaiting qualification, qualified, handed off, or closed; preserve the current status on its record. | Must |
| FR-05 | Sales-team handoff | Assign or route a qualified lead to a named salesperson or customer-service representative and notify that person that action is required. | Must |
| FR-06 | Follow-up task and reminder | Create a follow-up task with an owner and due time after handoff; notify the owner when it becomes due or overdue. | Must |
| FR-07 | Lead list | Provide the pilot team with a simple list of leads, owner, status, last customer message, last response time, and next follow-up due time. | Must |
| FR-08 | Lead temperature | Classify leads as Hot, Warm, or Cold from recorded qualification progress, purchase timeline, buyer engagement, and overdue follow-ups. Show the label and its reason in the lead list and workspace. | Should |
| FR-09 | Response and follow-up reporting | Show counts and rates for new enquiries, first-response time, qualified leads, assigned leads, and overdue follow-ups for a selectable period. | Should |
| FR-10 | Configuration | Allow an authorised pilot administrator to set qualification questions, first-response copy, team members, and routing rules. | Should |
| FR-11 | Conversation and action history | Retain a time-stamped history of customer messages, system replies, assignments, and follow-up actions for each lead. | Should |
| FR-12 | Inspection scheduling | Create or coordinate inspection appointments from a qualified lead record. | Could |

## User stories

- As a buyer who messages the agency after hours, I want an immediate acknowledgement and basic questions, so that I know my enquiry has been received and can move forward without waiting until the next day.
- As a customer-service representative, I want each WhatsApp enquiry captured in one lead record, so that I do not have to rely on memory or manually recreate the conversation in Excel.
- As a customer-service representative, I want the system to collect consistent qualification details, so that I can give the salesperson enough context to act.
- As a sales attendant, I want to be notified when a qualified lead is assigned to me, so that no lead waits unnoticed.
- As a sales attendant, I want follow-up tasks with due times and reminders, so that I do not forget to contact a prospect.
- As the Bravies Homz founder, I want to see response time, qualification, assignment, and overdue-follow-up data, so that I can judge whether the pilot reduces missed leads.
- As a sales attendant, I want each lead labelled Hot, Warm, or Cold with a visible reason, so that I contact buyers in the right order.
- As an authorised pilot administrator, I want to edit the initial reply, qualification questions, and team routing, so that Kora reflects the agency’s process without a product change.

## Out of scope for this build

- A full CRM, deal pipeline, accounting system, or property-management platform.
- Listing publication, listing-fee collection, property inventory management, or public property search.
- Replacement of human agents for inspections, negotiations, property recommendations, or closing deals.
- Automated claims that a delayed response caused a lost sale; the pilot will record response and follow-up activity, not infer lost-deal causality.
- Custom integrations with HubSpot, Salesforce, other CRMs, Facebook/Instagram advertising platforms, payment systems, or telephony systems.
- Multi-agency tenancy, expansion beyond the pilot agency, or city-wide rollout.
- Advanced AI training on agency data, predictive lead scoring, or an asserted proprietary “unfair advantage.”
- Pricing, billing, CAC optimisation, revenue forecasts, and retention guarantees.
- Guaranteed improvement targets until Bravies Homz’s baseline, pilot price, and day-30 success threshold are agreed in writing.

## Pilot decisions still required

1. Record the Bravies Homz CEO/founder’s name and confirm the signer for the pilot.
2. Agree the three-month pilot price.
3. Define the baseline for current response time, qualification rate, and missed follow-ups.
4. Agree the single day-30 continuation threshold, for example: “X% of WhatsApp enquiries receive a qualified reply within Y minutes.”

## Lead temperature rules for the pilot

- **Hot (red):** all required qualification details are present, the buyer says they intend to buy soon, and there is an open or recently completed next action. An overdue follow-up still displays as overdue, even if the lead is Hot.
- **Warm (amber):** the buyer has replied and partially completed qualification, or has a longer purchase timeline. The team should continue qualification or complete the next follow-up.
- **Cold (blue-grey):** required details remain incomplete after the configured follow-up attempt, the buyer has stopped responding, or the lead is closed as not pursuing a purchase.
- The label is a prioritisation aid, not a prediction that a buyer will purchase. Kora must display the reason for the label, such as “Timeline: within 30 days” or “No reply after follow-up.”
