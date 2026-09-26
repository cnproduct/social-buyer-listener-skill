# Scoring And Compliance

## Accepted Sources

Use only data that is public and reasonably intended for broad discovery:

- Google Alerts RSS feeds
- Google News RSS search feeds
- public search index result snippets
- user-provided public post URLs
- user-provided exported files

Do not automate private LinkedIn/Facebook surfaces, closed groups, friend-only content, or authenticated scraping that violates platform rules.

## Buyer Intent Signals

High-confidence B2B buyer intent usually combines at least two of these:

- product phrase: `baby feeding set`, `wheat straw lunch box`, `小麦秸秆午餐盒`, `小麦秸秆`
- supplier-seeking phrase: `looking for supplier`, `寻求供应商`, `有货源吗`, `求报价`
- commercial signal: `MOQ`, `wholesale`, `quote`, `inquiry`, `采购`, `询价`, `报价`, `起订`, `样品`, `货期`
- account context: buyer, procurement, purchasing, supply chain, importer, distributor, retailer, sourcing

Supplier self-promotion should normally be rejected unless the user explicitly wants suppliers. Watch for phrases such as `manufacturer`, `factory`, `OEM`, `customized`, `we supply`, `our products`, and `direct factory`.

## Suggested Score Interpretation

- 80+: strong candidate, review first
- 60-79: likely relevant, manual verification needed
- 35-59: weak or ambiguous, keep only if volume is low
- below 35: normally discard

When no high-confidence matches are found, say so. Do not inflate supplier posts into buyer leads.

## Required Output Fields

Each candidate should include:

- `platform`
- `account_url`
- `account_name`
- `company_name`
- `job_title`
- `content_summary`
- `matched_keywords`
- `matched_signals`
- `intent_score`
- `content_url`
- `published_at`
- `review_status`
- `reason`

If a field is not publicly visible, use `Unknown` or leave it empty and explain that manual review is required.
