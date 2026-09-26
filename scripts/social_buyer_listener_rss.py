import argparse
import csv
import hashlib
import json
import re
import sqlite3
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Dict, List, Optional
from xml.etree import ElementTree


HTML_TAG_RE = re.compile(r"<[^>]+>")


def strip_html(text: str) -> str:
    if not text:
        return ""
    return re.sub(HTML_TAG_RE, " ", unescape(text)).replace("\xa0", " ").strip()


def tag_name(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def read_config(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def node_text(node: Optional[ElementTree.Element]) -> str:
    if node is None:
        return ""
    return strip_html("".join(node.itertext()))


def fetch_feed(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; SocialBuyerListener/1.0)",
            "Accept": "application/rss+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def find_first(raw: ElementTree.Element, names: List[str]) -> Optional[ElementTree.Element]:
    for name in names:
        found = raw.find(name)
        if found is not None:
            return found
    return None


def collect_feed_items(xml_text: str, feed_name: str, default_platform: str) -> List[Dict]:
    root = ElementTree.fromstring(xml_text)
    root_tag = tag_name(root.tag)

    if root_tag == "rss":
        channels = root.findall("channel")
    elif root_tag == "feed":
        channels = [root]
    else:
        channels = []

    entries: List[Dict] = []
    for channel in channels:
        item_nodes = channel.findall("item") if root_tag == "rss" else channel.findall("entry")
        for raw in item_nodes:
            title = node_text(raw.find("title"))

            link_node = raw.find("link")
            link = ""
            if link_node is not None:
                link = (link_node.text or link_node.attrib.get("href", "") or "").strip()

            pub_node = find_first(raw, ["pubDate", "updated", "published"])
            published = (pub_node.text or "").strip() if pub_node is not None else ""

            description = node_text(raw.find("description"))
            summary = node_text(raw.find("summary"))
            content = node_text(raw.find("content"))
            content_text = " ".join(filter(None, [title, summary, description, content])).strip()

            guid_node = find_first(raw, ["guid", "id"])
            if guid_node is not None and guid_node.text:
                item_id = guid_node.text.strip()
            else:
                item_id = hashlib.sha1((title + link + published).encode("utf-8")).hexdigest()

            author_name = ""
            author_url = ""
            author_node = raw.find("author")
            if author_node is not None:
                if author_node.text:
                    author_name = strip_html(author_node.text)
                name_node = author_node.find("name")
                uri_node = author_node.find("uri")
                if name_node is not None and name_node.text:
                    author_name = strip_html(name_node.text)
                if uri_node is not None and uri_node.text:
                    author_url = uri_node.text.strip()

            creator_node = raw.find("{http://purl.org/dc/elements/1.1/}creator")
            if not author_name and creator_node is not None and creator_node.text:
                author_name = strip_html(creator_node.text)

            entries.append(
                {
                    "feed_name": feed_name,
                    "platform": default_platform,
                    "item_id": item_id,
                    "title": title,
                    "link": link,
                    "published_at": published,
                    "published_dt": parse_datetime(published),
                    "author_name": author_name,
                    "author_link": author_url,
                    "content": content_text,
                }
            )
    return entries


def score_item(text: str, config: Dict) -> Dict:
    lower = text.lower()
    product_keywords = config.get("product_keywords", [])
    intent_keywords = config.get("intent_keywords", [])
    buyer_keywords = config.get("buyer_role_keywords", [])
    supplier_keywords = config.get("supplier_promo_keywords", [])
    positive_patterns = config.get("positive_patterns", [])
    weights = config.get("score_weights", {})

    matched_product = sorted([k for k in product_keywords if k.lower() in lower])
    matched_intent = sorted([k for k in intent_keywords if k.lower() in lower])
    matched_signal = sorted([k for k in positive_patterns if k.lower() in lower])
    matched_buyer = sorted([k for k in buyer_keywords if k.lower() in lower])
    matched_supplier = sorted([k for k in supplier_keywords if k.lower() in lower])

    score = 0
    score += len(matched_product) * int(weights.get("product_keyword", 10))
    score += len(matched_intent) * int(weights.get("intent_keyword", 8))
    score += len(matched_signal) * int(weights.get("positive_signal", 8))

    if "?" in text or "？" in text:
        score += int(weights.get("question_bonus", 6))
    if matched_buyer:
        score += int(weights.get("buyer_profile_bonus", 10))
    if matched_supplier and not matched_signal:
        score -= len(matched_supplier) * int(weights.get("supplier_penalty", 18))

    return {
        "intent_score": max(0, score),
        "matched_product_keywords": matched_product,
        "matched_intent_keywords": matched_intent,
        "matched_positive_signals": matched_signal,
        "matched_supplier_promo": matched_supplier,
    }


def extract_company_name(title: str, content: str) -> str:
    text = f"{title} {content}"
    patterns = [
        r"\|\s*([^|\-–—]{2,60})\s*(?:- LinkedIn| \||$)",
        r"-\s*([^-\u2013\u2014]{2,60})\s*(?:\|| at | \(LinkedIn\)|$)",
        r"\bat\s+([A-Z][A-Za-z0-9&.,' ]{2,60})",
    ]
    for pat in patterns:
        match = re.search(pat, text)
        if match:
            cand = match.group(1).strip()
            if 2 <= len(cand) <= 60 and not cand.lower().startswith(("linkedin", "facebook")):
                return cand
    return ""


def extract_job_title(text: str) -> str:
    for title in [
        "procurement manager",
        "采购经理",
        "采购总监",
        "sourcing manager",
        "supply chain",
        "供应链",
        "buyer",
        "procurement",
        "采购",
    ]:
        if title.lower() in text.lower():
            return title
    return ""


def platform_from_link(url: str, fallback: str) -> str:
    low = (url or "").lower()
    if "linkedin.com" in low:
        return "LinkedIn"
    if "facebook.com" in low or "fb.com" in low:
        return "Facebook"
    return fallback


def summarize(text: str, limit: int = 240) -> str:
    clean = " ".join((text or "").split())
    return clean if len(clean) <= limit else clean[:limit].rstrip() + "..."


def account_link_from_content(raw_link: str) -> str:
    if not raw_link:
        return ""
    match = re.search(r"/(in|company|pages|profile\.php|groups)/[^/?#]+", raw_link)
    return raw_link[: match.end()] if match else raw_link


@dataclass
class Lead:
    platform: str
    account_url: str
    account_name: str
    company_name: str
    job_title: str
    content_summary: str
    matched_keywords: str
    matched_signals: str
    intent_score: int
    content_id: str
    content_url: str
    published_at: str
    review_status: str
    reason: str


class LeadStore:
    def __init__(self, path: str):
        self.conn = sqlite3.connect(path)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS seen_items(
                item_id TEXT PRIMARY KEY,
                seen_at TEXT NOT NULL
            )
            """
        )
        self.conn.commit()

    def has_seen(self, item_id: str) -> bool:
        cur = self.conn.execute("SELECT 1 FROM seen_items WHERE item_id=?", (item_id,))
        return cur.fetchone() is not None

    def mark_seen(self, item_id: str) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO seen_items(item_id, seen_at) VALUES (?, ?)",
            (item_id, datetime.now(timezone.utc).isoformat()),
        )
        self.conn.commit()


def append_csv(path: Path, leads: List[Lead]) -> None:
    if not leads:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(Lead.__dataclass_fields__.keys())
    exists = path.exists()
    with path.open("a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        for item in leads:
            writer.writerow(asdict(item))


def send_webhook(webhook_url: str, leads: List[Lead]) -> None:
    if not webhook_url or not leads:
        return
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(leads),
        "leads": [asdict(item) for item in leads],
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        _ = resp.read()


def build_reason(score_pack: Dict) -> str:
    parts = []
    if score_pack["matched_product_keywords"]:
        parts.append("product keyword matched")
    if score_pack["matched_intent_keywords"]:
        parts.append("purchase/supplier intent matched")
    if score_pack["matched_positive_signals"]:
        parts.append("positive buyer signal matched")
    if score_pack["matched_supplier_promo"]:
        parts.append("supplier-promotion terms detected; review carefully")
    return "; ".join(parts) or "rule match"


def run_once(cfg: Dict) -> List[Lead]:
    scoring = cfg.get("scoring", {})
    min_score = int(scoring.get("min_score", 35))
    max_results = int(scoring.get("max_results_per_run", 100))
    store = LeadStore(cfg.get("state_db_path", "state.sqlite"))
    hits: List[Lead] = []

    for feed in cfg.get("feeds", []):
        name = feed.get("name", "")
        feed_url = feed.get("rss_url", "")
        platform = feed.get("platform", "Unknown")
        if not feed_url or "REPLACE_WITH" in feed_url:
            print(f"[WARN] {name}: missing real RSS URL")
            continue

        try:
            xml_text = fetch_feed(feed_url)
            items = collect_feed_items(xml_text, name, platform)
        except (urllib.error.URLError, urllib.error.HTTPError, ElementTree.ParseError, TimeoutError) as e:
            print(f"[WARN] failed to fetch/parse {name}: {e}")
            continue

        for item in items:
            item_id = item.get("item_id", "")
            if not item_id or store.has_seen(item_id):
                continue

            content = item.get("content", "")
            score_pack = score_item(content, scoring)
            score = int(score_pack["intent_score"])
            if score < min_score:
                store.mark_seen(item_id)
                continue

            raw_link = item.get("link", "")
            matched_keywords = ",".join(
                score_pack["matched_product_keywords"] + score_pack["matched_intent_keywords"]
            )
            matched_signals = ",".join(score_pack["matched_positive_signals"])
            account_url = item.get("author_link") or account_link_from_content(raw_link)
            account_name = item.get("author_name", "")
            company_name = extract_company_name(item.get("title", ""), content)
            job_title = extract_job_title(content + " " + item.get("title", ""))

            hits.append(
                Lead(
                    platform=platform_from_link(raw_link, platform),
                    account_url=account_url or raw_link,
                    account_name=account_name or "Unknown",
                    company_name=company_name or "Unknown",
                    job_title=job_title or "Unknown",
                    content_summary=summarize(content),
                    matched_keywords=matched_keywords,
                    matched_signals=matched_signals,
                    intent_score=score,
                    content_id=item_id,
                    content_url=raw_link,
                    published_at=item.get("published_at", ""),
                    review_status="needs_manual_review",
                    reason=build_reason(score_pack),
                )
            )
            store.mark_seen(item_id)

    hits.sort(key=lambda x: x.intent_score, reverse=True)
    if max_results > 0:
        hits = hits[:max_results]

    output_csv = cfg.get("output_csv_path")
    if output_csv:
        append_csv(Path(output_csv), hits)

    webhook_url = cfg.get("webhook_url", "")
    if webhook_url:
        try:
            send_webhook(webhook_url, hits)
        except Exception as e:
            print(f"[WARN] webhook failed: {e}")

    return hits


def print_leads(leads: List[Lead]) -> None:
    print("\n=== Matched buyer candidates sorted by intent ===")
    if not leads:
        print("No new candidates matched the threshold.")
        return
    for idx, lead in enumerate(leads, 1):
        print(f"{idx:02d}. [{lead.platform}] score={lead.intent_score} | {lead.account_name}")
        print(f"    account_url: {lead.account_url}")
        print(f"    company/job: {lead.company_name} / {lead.job_title}")
        print(f"    matched_keywords: {lead.matched_keywords}")
        print(f"    matched_signals: {lead.matched_signals}")
        print(f"    content: {lead.content_summary}")
        print(f"    content_url: {lead.content_url}")
        print(f"    reason: {lead.reason}\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Public social buyer intent listener")
    parser.add_argument("--config", default="assets/config.auto.json")
    parser.add_argument("--once", action="store_true", help="run once")
    parser.add_argument("--loop", action="store_true", help="run repeatedly")
    parser.add_argument("--interval", type=int, default=None, help="loop interval in minutes")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cfg = read_config(Path(args.config))
    interval = args.interval
    if interval is None:
        interval = int(cfg.get("loop", {}).get("interval_minutes", 30))

    loop_enabled = bool(args.loop or cfg.get("loop", {}).get("enabled", False))
    if args.once or not loop_enabled:
        print_leads(run_once(cfg))
        return

    while True:
        print_leads(run_once(cfg))
        print(f"Waiting {interval} minutes...")
        time.sleep(max(1, interval) * 60)


if __name__ == "__main__":
    main()
