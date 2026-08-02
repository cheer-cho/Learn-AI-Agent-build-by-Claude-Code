---
id: privacy-retention
title: Data Retention Policy
category: privacy
tags: [retention, deletion, records, tax, compliance]
last_updated: 2025-09-12
---

# Data Retention Policy

## Purpose

TechCorp retains personal data only as long as needed for the purpose it was collected, or as long as the law requires — whichever governs. This policy defines the retention schedule for the main categories of customer data. System owners are responsible for implementing these periods technically; Legal owns the schedule and reviews it annually.

## Retention Schedule

### Customer Account Data

Account profile data — name, email, addresses, preferences, and login credentials — is retained while the account is active. After a customer submits an **account deletion request, account data is retained for 30 days** and then permanently deleted. The 30-day window exists to allow cancellation of accidental requests and to complete in-flight transactions. Deletion mechanics, verification, and backup purging are described in the Data Deletion Process document.

### Order and Financial Records

**Order records — invoices, payment records, and shipping documentation — are kept for 7 years**, as required by applicable tax law. This retention applies even when the associated account has been deleted: order records are decoupled from the deleted account and retained in a restricted financial archive with access limited to Finance and audit functions. Customers cannot request early deletion of these records; this is a recognized legal-obligation exception under GDPR and equivalent laws.

### Support Tickets

**Customer support tickets, including chat transcripts and email threads, are retained for 3 years** from ticket closure. This period supports warranty claims (our standard warranty runs 24 months), dispute resolution, and service-quality analysis. After 3 years, tickets are deleted; aggregated, de-identified metrics derived from them may be kept indefinitely.

### Marketing Consent Data

Records of marketing consent are retained while the consent is active. When a customer **withdraws marketing consent, the associated marketing data is deleted immediately** — the customer is removed from all campaign audiences within the same processing cycle, and no grace period applies. A minimal suppression record (a hashed identifier proving the opt-out) is kept to ensure the customer is not re-contacted; this suppression record contains no marketable data.

## Exceptions and Legal Hold

Two situations override the schedule above:

1. **Legal hold** — data subject to litigation, regulatory investigation, or a preservation order is retained until Legal releases the hold, regardless of category.
2. **Statutory financial retention** — the 7-year order-record requirement described above.

No other exceptions may be granted at team level. Requests to retain data longer than scheduled must be approved in writing by Legal.

## Enforcement

Automated retention jobs run against production systems daily and against backups per the backup rotation described in the Data Deletion Process. System owners must certify compliance with this schedule during the annual privacy review. Discovering data held beyond its scheduled period must be reported to the privacy team within 2 business days.

## Related Documents

See the Data Deletion Process for request handling and the GDPR Compliance Summary for the broader legal framework.
