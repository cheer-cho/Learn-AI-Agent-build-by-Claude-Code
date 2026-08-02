# Security Lab — Intentionally Malicious Test Documents

**WARNING: The documents in this directory contain planted prompt-injection attacks. This is deliberate.**

## What this is

This directory supports **Module 20: Defending Against Prompt Injection**, where learners attack their *own local* RAG/agent system in a controlled way to understand and build injection defenses.

- `injected_policy.md` (`seclab-injected-policy`) — a realistic-looking expense policy with an embedded "IGNORE ALL PREVIOUS INSTRUCTIONS" payload that attempts to exfiltrate order records and falsely approve all refunds.
- `injected_faq.md` (`seclab-injected-faq`) — a realistic-looking IT onboarding FAQ with a payload disguised as a "system note for AI assistants" attempting the same behavior.

Both payloads are inert text. They do nothing on their own — they only matter when an LLM ingests them as retrieved context without defenses.

## Rules of use

1. **Never index these files into the main document collection.** They must only be loaded into the throwaway collection created during the Module 20 exercises.
2. Use them only against your local lab system, never against shared, production, or third-party systems.
3. If your ingestion script globs `data/**/*.md`, explicitly exclude `data/security_lab/` everywhere outside Module 20.
4. Do not "fix" or soften the payload text — the lab's detection and mitigation exercises depend on it verbatim.

## Why this exists

You cannot defend against attacks you have never seen. The module walks through detection (content scanning, provenance tagging), containment (tool-permission scoping, output filtering), and verification (evals that assert the payloads fail). These files are the fixed attack corpus for those exercises.
