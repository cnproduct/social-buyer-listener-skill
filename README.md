# Social Buyer Listener Skill

Codex skill for monitoring public LinkedIn/Facebook buyer-intent signals without platform API access.

It supports:

- Google Alerts RSS feeds for ongoing monitoring
- Google News RSS search feeds for immediate public-index scans
- buyer-intent scoring for products such as `baby feeding set` and `wheat straw lunch box`
- supplier-promotion filtering
- SQLite deduplication
- CSV output
- optional webhook notification

Run once:

```bash
python scripts/social_buyer_listener_rss.py --config assets/config.auto.json --once
```

Run continuously:

```bash
python scripts/social_buyer_listener_rss.py --config assets/config.example.json --loop --interval 30
```

This skill intentionally works only with public data and does not automate private LinkedIn/Facebook surfaces.
