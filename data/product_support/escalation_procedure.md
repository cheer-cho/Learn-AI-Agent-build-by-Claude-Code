---
id: support-escalation
title: Support Escalation Procedure
category: product_support
tags: [escalation, sla, support-tiers, refund-approval]
last_updated: 2026-04-02
---

# Support Escalation Procedure

## Purpose

This procedure defines how customer support cases move between support tiers at TechCorp, the response-time commitments at each tier, and which cases must be escalated immediately. It applies to all inbound support channels: email, chat, and the support portal.

## Support Tiers at a Glance

| Tier | Who | First-Response SLA | Authority |
|------|-----|--------------------|-----------|
| Tier 1 | Frontline support agents | 24 hours | Standard policy resolutions; refunds up to $500 |
| Tier 2 | Senior agents and support managers | 48 hours | Policy exceptions; refunds over $500 |
| Tier 3 | Legal, Security, and executive escalations | Case-dependent | Legal matters, data incidents |

## Tier 1: Frontline Support

Every new case lands with Tier 1, which must send a **first response within 24 hours** of ticket creation. Tier 1 agents resolve the large majority of cases using published policies: returns, damaged-product claims, warranty intake, order-status questions, and account issues.

## Escalation to Tier 2

A case escalates to Tier 2 when any of the following occurs:

- The case remains **unresolved after 2 exchanges** between the customer and Tier 1 (an exchange is one customer message plus one agent reply).
- The resolution requires an exception to published policy.
- The customer explicitly requests a manager.

Tier 2 carries a **48-hour SLA** for its first substantive response after escalation. Tier 2 owns the case through resolution; it is not bounced back to Tier 1.

### Refund Approval Threshold

**Any refund over $500 requires Tier 2 manager approval**, regardless of which policy the refund falls under. Tier 1 agents should set customer expectations that approval adds up to 48 hours, prepare the case file (order details, evidence, policy basis), and escalate with a recommendation. Approvals and denials are logged with the approving manager's ID.

## Direct Escalation to Tier 3

Some cases bypass Tier 2 entirely. Escalate **directly to Tier 3** — immediately, without further customer-facing replies — when a customer:

- makes or implies a **legal threat** (lawsuit, attorney involvement, regulatory complaint), or
- mentions a possible **data breach**, leaked personal data, or unauthorized account access.

For these cases, agents must not admit fault, promise outcomes, or discuss details; acknowledge receipt, flag the ticket `tier3-legal` or `tier3-security` as appropriate, and Tier 3 takes ownership. Suspected data incidents are simultaneously reported to the Security on-call channel per the incident-response runbook.

## Documentation Standards

Every escalation must include: the full ticket history, order number(s), the specific ask, evidence collected (photos, logs), and the policies already applied. Escalations missing this context are returned to the escalating agent, which restarts the SLA clock — do it right the first time.

## Related Policies

See Refunds for Damaged Products, the Standard Return Policy, and the Warranty Policy for the substantive rules that Tier 1 applies before escalation is needed.
