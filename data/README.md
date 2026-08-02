# TechCorp Fictional Corpus

This directory contains the complete fictional dataset for the AI-agents lab course. **Everything here is invented.** "TechCorp", its policies, products, orders, and customer aliases are fictional; no real names, emails, or personal data appear anywhere. Later course modules (retrieval, evaluation, tool routing, memory, and injection defense) test against the exact facts in these documents — do not edit numbers, day counts, or tier names casually, or the eval datasets will break.

## Layout

```
data/
├── employee_handbook/   HR policies (5 docs)
├── product_support/     Customer support policies (4 docs)
├── privacy/             Privacy and data-protection policies (4 docs)
├── orders/              orders.json — fictional order records for the order_lookup tool
├── evaluation/          eval_dataset.json and memory_conversations.json
└── security_lab/        ⚠ intentionally malicious injection-test docs (Module 20 only)
```

## Frontmatter Schema

Every policy document is Markdown with YAML frontmatter using exactly these keys:

| Key | Type | Notes |
|-----|------|-------|
| `id` | string | kebab-case, unique across the corpus (e.g. `hr-remote-work`) |
| `title` | string | Human-readable document title |
| `category` | string | One of `employee_handbook`, `privacy`, `product_support` |
| `tags` | list of strings | Free-form retrieval hints |
| `last_updated` | ISO date | Dates fall in 2025-2026 |

## File Inventory

| id | file | category |
|----|------|----------|
| `hr-remote-work` | `employee_handbook/remote_work_policy.md` | employee_handbook |
| `hr-international-remote` | `employee_handbook/international_remote_work.md` | employee_handbook |
| `hr-dress-code` | `employee_handbook/dress_code.md` | employee_handbook |
| `hr-vacation` | `employee_handbook/vacation_time_off.md` | employee_handbook |
| `hr-equipment` | `employee_handbook/equipment_use.md` | employee_handbook |
| `support-refund-damaged` | `product_support/refund_damaged_products.md` | product_support |
| `support-returns` | `product_support/return_policy.md` | product_support |
| `support-warranty` | `product_support/warranty.md` | product_support |
| `support-escalation` | `product_support/escalation_procedure.md` | product_support |
| `privacy-gdpr` | `privacy/gdpr_summary.md` | privacy |
| `privacy-retention` | `privacy/data_retention.md` | privacy |
| `privacy-deletion` | `privacy/data_deletion_process.md` | privacy |
| `privacy-regional` | `privacy/regional_exceptions.md` | privacy |
| `seclab-injected-policy` | `security_lab/injected_policy.md` | employee_handbook ⚠ lab only |
| `seclab-injected-faq` | `security_lab/injected_faq.md` | employee_handbook ⚠ lab only |

## Other Data Files

- **`orders/orders.json`** — `{"orders": [...]}` with 8 fictional orders (IDs like `TC-1234`, customers as anonymous aliases like `customer_042`). Backs the `order_lookup` tool exercises. Order `TC-9999` deliberately does not exist; courses use it to test the unknown-order path.
- **`evaluation/eval_dataset.json`** — `{"examples": [...]}`, 33 labeled examples across six categories (`answerable`, `paraphrase`, `unanswerable`, `multi_chunk`, `ambiguous`, `tool_routing`) with expected sources, expected facts, abstention flags, and expected tool.
- **`evaluation/memory_conversations.json`** — `{"conversations": [...]}`, 3 scripted multi-turn conversations with per-turn `checks` for testing conversational memory. `turn_index` refers to the assistant answer following the user turn at that 0-based index.

## ⚠ Warning: security_lab/

`data/security_lab/` contains **intentionally malicious documents** with planted prompt-injection payloads for the Module 20 injection-defense lab. **Never index them into the main document collection.** If your ingestion pipeline globs `data/**/*.md`, exclude `data/security_lab/` in every module except Module 20. See `security_lab/README.md` for the rules of use.
