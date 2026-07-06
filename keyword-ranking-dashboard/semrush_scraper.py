"""
semrush_scraper.py

Fetches the organic ranking of one or more keywords for a given domain
using the official SEMrush Analytics API (domain_organic report).

Output record format (one per keyword):
{
    "fetch_date": "2026-07-06T00:00:00Z",
    "domain": "yourclient.com",
    "keyword": "grey suede penny loafers",
    "position": 5,
    "search_volume": 170,
    "traffic": 0.71,
    "vi": 1.2,
    "keyword_difficulty": 45,
    "search_intent": "Transactional"
}

Results are stored in MongoDB (database "seo", collection "keyword_rankings"
by default — see .env.example to change).

Usage:
    python semrush_scraper.py --domain yourclient.com --keyword "grey suede penny loafers"
    python semrush_scraper.py --domain yourclient.com --keywords-file keywords.txt --database in
    python semrush_scraper.py --domain yourclient.com --keyword "..." --json backup.json

The API key is read from the SEMRUSH_API_KEY environment variable
(put it in a .env file next to this script — see .env.example).
"""

import argparse
import csv
import io
import json
import os
import sys
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

API_ENDPOINT = "https://api.semrush.com/"

# SEMrush returns intent as numeric codes in the "In" column.
# https://developer.semrush.com/api/v3/analytics/basic-docs/
INTENT_MAP = {
    "0": "Commercial",
    "1": "Informational",
    "2": "Navigational",
    "3": "Transactional",
}

# Approximate organic CTR by SERP position, used to estimate a per-keyword
# visibility index. SEMrush's own "Visibility" metric is only exposed via
# Position Tracking campaigns (Projects API), not the Analytics API.
# Adjust this curve (or replace estimate_visibility entirely) to match
# however your existing "vi" values were calculated.
CTR_CURVE = {
    1: 0.317, 2: 0.247, 3: 0.187, 4: 0.133, 5: 0.095,
    6: 0.068, 7: 0.049, 8: 0.037, 9: 0.029, 10: 0.023,
}


class SemrushApiError(Exception):
    """Raised when the SEMrush API returns an ERROR response."""


def estimate_visibility(position):
    """Estimate a visibility index (0-100) from an organic position."""
    if position is None:
        return None
    if position <= 10:
        ctr = CTR_CURVE[position]
    elif position <= 20:
        ctr = 0.015
    elif position <= 50:
        ctr = 0.005
    else:
        ctr = 0.001
    return round(ctr * 100, 2)


def parse_intents(raw):
    """Convert SEMrush's numeric intent codes (e.g. "3" or "1,3") to labels."""
    if not raw:
        return None
    labels = [INTENT_MAP.get(code.strip(), code.strip()) for code in raw.split(",")]
    return labels[0] if len(labels) == 1 else labels


def parse_number(raw, cast=float):
    """Parse a numeric field, returning None for empty values.

    Integers are returned as int (e.g. keyword_difficulty 45.00 -> 45).
    """
    if raw is None or raw == "":
        return None
    value = cast(raw)
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def fetch_keyword_ranking(api_key, domain, keyword, database="in"):
    """Query the domain_organic report for a single keyword.

    Returns the raw parsed row as a dict, or None if the domain does not
    rank for the keyword in that database.
    """
    params = {
        "type": "domain_organic",
        "key": api_key,
        "domain": domain,
        "database": database,
        # Ph=keyword, Po=position, Nq=search volume,
        # Tr=traffic share (%), Kd=keyword difficulty, In=intent
        "export_columns": "Ph,Po,Nq,Tr,Kd,In",
        "display_filter": f"+|Ph|Eq|{keyword}",
        "display_limit": 1,
    }
    response = requests.get(API_ENDPOINT, params=params, timeout=30)
    response.raise_for_status()
    body = response.text.strip()

    if body.startswith("ERROR"):
        # "ERROR 50 :: NOTHING FOUND" means the domain has no ranking
        # for this keyword — not a failure.
        if "NOTHING FOUND" in body:
            return None
        raise SemrushApiError(body)

    reader = csv.DictReader(io.StringIO(body), delimiter=";")
    rows = list(reader)
    return rows[0] if rows else None


def build_record(domain, keyword, row, fetch_date, database):
    """Shape an API row into the output schema. Missing rank -> null metrics."""
    record = {
        "fetch_date": fetch_date,
        "domain": domain,
        "database": database,
        "keyword": keyword,
        "position": None,
        "search_volume": None,
        "traffic": None,
        "vi": None,
        "keyword_difficulty": None,
        "search_intent": None,
    }
    if row is None:
        return record

    position = parse_number(row.get("Position"), int)
    record.update(
        {
            "position": position,
            "search_volume": parse_number(row.get("Search Volume"), int),
            "traffic": parse_number(row.get("Traffic (%)")),
            "vi": estimate_visibility(position),
            "keyword_difficulty": parse_number(row.get("Keyword Difficulty")),
            "search_intent": parse_intents(row.get("Intents")),
        }
    )
    return record


def save_json(records, path):
    """Append records to a JSON array file (created if missing)."""
    existing = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            content = fh.read().strip()
            if content:
                existing = json.loads(content)
    existing.extend(records)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(existing, fh, indent=2, ensure_ascii=False)


def save_mongo(records):
    """Insert records into MongoDB. Connection settings come from .env,
    defaulting to a local server (mongodb://localhost:27017, seo.keyword_rankings)."""
    from pymongo import MongoClient

    uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
    db_name = os.environ.get("MONGO_DB", "seo")
    coll_name = os.environ.get("MONGO_COLLECTION", "keyword_rankings")

    docs = []
    for record in records:
        doc = dict(record)
        # Store fetch_date as a real datetime so Mongo shows ISODate(...)
        doc["fetch_date"] = datetime.strptime(
            record["fetch_date"], "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=timezone.utc)
        docs.append(doc)

    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    client[db_name][coll_name].insert_many(docs)
    client.close()
    return f"{db_name}.{coll_name}"


def main():
    parser = argparse.ArgumentParser(
        description="Fetch keyword rankings for a domain from the SEMrush API."
    )
    parser.add_argument("--domain", required=True, help="Domain to check, e.g. yourclient.com")
    parser.add_argument(
        "--keyword", action="append", default=[],
        help="Keyword to check (repeat the flag for multiple keywords)",
    )
    parser.add_argument(
        "--keywords-file",
        help="Path to a text file with one keyword per line",
    )
    parser.add_argument(
        "--database", default="in",
        help="SEMrush regional database (in, us, uk, ca, au, ...). Default: in",
    )
    parser.add_argument(
        "--json", metavar="PATH",
        help="Also append results to a JSON file (optional backup copy)",
    )
    args = parser.parse_args()

    load_dotenv()
    api_key = os.environ.get("SEMRUSH_API_KEY")
    if not api_key:
        raise SystemExit(
            "SEMRUSH_API_KEY is not set. Copy .env.example to .env and add your key."
        )

    keywords = list(args.keyword)
    if args.keywords_file:
        with open(args.keywords_file, "r", encoding="utf-8") as fh:
            keywords.extend(line.strip() for line in fh if line.strip())
    if not keywords:
        raise SystemExit("No keywords given. Use --keyword or --keywords-file.")

    # Midnight UTC of the day the data was fetched, matching the stored format.
    fetch_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00Z")

    records = []
    for keyword in keywords:
        try:
            row = fetch_keyword_ranking(api_key, args.domain, keyword, args.database)
        except (requests.RequestException, SemrushApiError) as exc:
            print(f"[error] {keyword!r}: {exc}", file=sys.stderr)
            continue

        record = build_record(args.domain, keyword, row, fetch_date, args.database)
        records.append(record)
        if record["position"] is None:
            print(f"[warn] {args.domain} does not rank for {keyword!r} in "
                  f"'{args.database}' — saved with null metrics", file=sys.stderr)
        else:
            print(f"[ok] {keyword!r}: position {record['position']}")

    if not records:
        raise SystemExit("No results retrieved.")

    print(json.dumps(records, indent=2, ensure_ascii=False))

    try:
        target = save_mongo(records)
    except Exception as exc:
        # Don't lose data that already cost API units — dump it to a file.
        fallback = "results_fallback.json"
        save_json(records, fallback)
        raise SystemExit(
            f"Could not write to MongoDB ({exc}).\n"
            f"Is the MongoDB service running? Records were saved to {fallback} "
            f"instead — re-run the migration or restart MongoDB and try again."
        )
    print(f"Inserted {len(records)} record(s) into MongoDB ({target})")

    if args.json:
        save_json(records, args.json)
        print(f"Also saved a JSON copy to {args.json}")


if __name__ == "__main__":
    main()
