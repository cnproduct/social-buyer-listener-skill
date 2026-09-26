---
name: social-buyer-listener
description: Monitor public social web signals for B2B buyer intent on LinkedIn and Facebook without platform APIs, using RSS/search feeds, scoring rules, deduplication, and CSV/Webhook output.
metadata:
  short-description: Public LinkedIn/Facebook B2B buyer intent monitor
---

# Social Buyer Listener

Use this skill when the user wants to find B2B buyer accounts from public LinkedIn/Facebook content without applying for platform API access. It is optimized for product-driven buyer intent such as `baby feeding set`, `wheat straw lunch box`, and multilingual equivalents configured in the JSON assets.

The skill should preserve these boundaries:

- Work only with publicly visible data exposed through RSS feeds, public search indexes, or user-provided URLs/files.
- Do not bypass login walls, private groups, friend-only posts, anti-bot protections, or platform permissions.
- Treat automated results as lead candidates for manual review, not verified contacts.
- Prefer official platform APIs if the user later has access; otherwise keep the no-API workflow.

## Default Workflow

1. Start from `assets/config.example.json` for user-provided Google Alerts RSS feeds, or `assets/config.auto.json` for immediate public Google News RSS search.
2. Run `scripts/social_buyer_listener_rss.py` with `--once` for a single scan or `--loop` for repeated monitoring.
3. Sort candidates by `intent_score`, then return only records that show both product relevance and purchase/supplier-seeking intent.
4. Output each candidate with platform source, account/content link, company name if visible, job title if visible, content summary, matched keywords, matched signals, score, and reason for inclusion.
5. Explain limitations honestly: public search coverage for LinkedIn/Facebook is incomplete, and missing results do not prove there are no buyers.

## When To Read References

- Read `references/scoring-and-compliance.md` when adjusting scoring, adding products, explaining why a result was accepted/rejected, or advising on compliance.
- Use `assets/config.example.json` when the user can provide Google Alerts RSS URLs.
- Use `assets/config.auto.json` when the user wants an immediate first run without creating alerts.

## Useful Commands

Run once from the skill folder:

```bash
python scripts/social_buyer_listener_rss.py --config assets/config.auto.json --once
```

Run every 30 minutes:

```bash
python scripts/social_buyer_listener_rss.py --config assets/config.example.json --loop --interval 30
```

The default CSV output is `results/social_leads.csv`. The script creates a SQLite state file to avoid duplicate alerts.
