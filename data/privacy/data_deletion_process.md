---
id: privacy-deletion
title: Data Deletion Process
category: privacy
tags: [deletion, erasure, right-to-be-forgotten, backups]
last_updated: 2026-03-05
---

# Data Deletion Process

## Purpose

This document describes the operational process TechCorp follows when a customer requests deletion of their personal data — whether under GDPR's right to erasure, CCPA, LGPD, or simply as an account-closure request. It defines timelines, verification steps, backup handling, and the exceptions where deletion is limited by law.

## Step 1: Intake and Verification

Deletion requests arrive through the privacy request form, the account settings page, or customer support. Every request is **verified within 72 hours** of receipt. Verification confirms the requester controls the account, using one of:

- confirmation link sent to the registered email address,
- authenticated in-app confirmation for logged-in users, or
- for edge cases (lost email access), a manual identity check run by the privacy team.

Requests that fail verification are not actioned; the requester is told what additional proof is needed. Unverifiable requests expire after 30 days.

## Step 2: Execution

Once verified, **deletion is completed within 30 days** of the original request. During this window:

- The account is immediately deactivated and removed from all customer-facing systems.
- Personal data is erased or irreversibly anonymized across production databases, analytics stores, and vendor systems (processors are instructed via automated deletion APIs or, where necessary, ticketed workflows with confirmation required).
- Marketing systems remove the customer from all audiences; a hashed suppression record is retained solely to prevent re-contact.

The 30-day execution window aligns with the account-data retention rule in the Data Retention Policy.

## Step 3: Backups

Production deletion does not instantly remove data from backups, which are immutable by design. **All backups containing the customer's personal data are purged within 90 days** of the deletion request, through the standard backup rotation cycle. If a backup must be restored during this window, re-deletion of the affected records is executed automatically as part of the restore runbook before the restored system returns to service.

## Step 4: Confirmation

When production deletion completes, a **confirmation email is sent** to the customer's registered address. This is the final message TechCorp will send; the address is then suppressed. Customers who request it are also given a summary of any data retained under the exceptions below.

## Exceptions

Two categories of data are excluded from deletion:

1. **Legal hold** — data preserved for active litigation, investigations, or regulatory orders, retained until Legal releases the hold.
2. **Financial records** — invoices and order/payment records retained for 7 years under tax law, per the Data Retention Policy. These are decoupled from the deleted account and stored in a restricted archive.

Customers are informed when an exception applies, including the legal basis and expected retention end date where known.

## Internal Responsibilities

The privacy operations team owns request tracking; missing the 72-hour verification or 30-day completion targets is an internal incident and must be escalated to the Data Protection Officer. See the GDPR Compliance Summary and Regional Privacy Exceptions for the surrounding legal framework.
