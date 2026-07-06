# semrush_scraper + dashboard

Architecture:

```
semrush_scraper.py  --->  MongoDB (seo.keyword_rankings)  --->  dashboard.py
```

1. **`semrush_scraper.py`** — fetches organic keyword rankings for a domain
   using the official **SEMrush Analytics API** (`domain_organic` report)
   and inserts the results into MongoDB.
2. **`dashboard.py`** — a client-facing web dashboard (FastAPI + Chart.js)
   that reads MongoDB and shows KPIs, ranking trends, winners/losers,
   distributions, and a sortable keyword table.

Requires a running MongoDB server (localhost:27017 by default). Browse the
raw data anytime with MongoDB Compass or Studio 3T: connect to
`mongodb://localhost:27017`, database `seo`, collection `keyword_rankings`.

## Setup

```powershell
pip install -r requirements.txt
copy .env.example .env
# then edit .env and paste your SEMrush API key
```

Your API key is in SEMrush under **Account > Subscription info > API units**.
No login credentials are needed — the API only uses the key.

## Usage

Single keyword:

```powershell
python semrush_scraper.py --domain yourclient.com --keyword "grey suede penny loafers"
```

Multiple keywords from a file (one per line):

```powershell
python semrush_scraper.py --domain yourclient.com --keywords-file keywords.txt
```

Other options:

| Flag | Meaning | Default |
|---|---|---|
| `--database` | SEMrush regional database (`in`, `us`, `uk`, `ca`, `au`, ...) | `in` |
| `--json PATH` | Also append a JSON backup copy to this file | off |

Results go into MongoDB. If MongoDB is unreachable, the records are saved
to `results_fallback.json` so no fetched data (or API units) is lost.

## Output fields and where they come from

| Field | SEMrush API column | Notes |
|---|---|---|
| `fetch_date` | — | Midnight UTC of the day the script ran |
| `domain` | — | The `--domain` you passed |
| `database` | — | The `--database` the result came from (e.g. `in`) |
| `keyword` | `Ph` | |
| `position` | `Po` | Organic position in the chosen database |
| `search_volume` | `Nq` | Monthly search volume |
| `traffic` | `Tr` | Share (%) of the domain's organic traffic from this keyword |
| `vi` | *computed* | See note below |
| `keyword_difficulty` | `Kd` | 0–100 |
| `search_intent` | `In` | Mapped from codes: 0=Commercial, 1=Informational, 2=Navigational, 3=Transactional. A keyword with multiple intents returns a list. |

If the domain does not rank for a keyword, the record is still saved with
`position` and the other metrics as `null`, so you keep a row for every check.

### About `vi` (visibility)

SEMrush's real **Visibility** metric is only available from **Position
Tracking campaigns** via their Projects API — it is not part of the
Analytics API this script uses. The script therefore *estimates* `vi`
from the position using a standard organic click-through-rate curve
(`CTR_CURVE` at the top of `semrush_scraper.py`). If your existing `vi`
values come from a Position Tracking campaign, the script can be extended
to pull the exact value — you'll need the campaign's project ID.

## Dashboard

```powershell
python dashboard.py                              # serves data from MongoDB
python dashboard.py --data demo_results.json     # demo dataset (JSON file)
```

Then open http://localhost:8017 (opens automatically).

### Logins

The dashboard requires signing in. Create accounts with:

```powershell
python manage_users.py add yourname --admin              # you: sees everything
python manage_users.py add clientname --domains yourclient.com
python manage_users.py list
python manage_users.py password clientname               # reset a password
python manage_users.py remove clientname
```

You'll be prompted to type the password (hidden). A client with `--domains`
only sees those domains — the domain dropdown, data, and CSV export are all
restricted to them. Passwords are stored salted + hashed (PBKDF2) in the
`seo.users` collection; sessions last 7 days.

Note: this auth is appropriate for local use or a trusted network. If you
ever expose the dashboard on the public internet, put it behind HTTPS
(e.g. a reverse proxy like Caddy or nginx) first.

### Report downloads

Signed-in users have two buttons in the header:

- **Download Excel** — the full keyword table (position, change, volume,
  traffic %, KD, intent) as a formatted .xlsx file: styled header,
  sized columns, color-coded changes.
- **Print / PDF** — a print-friendly version of the whole dashboard;
  choose "Save as PDF" in the print dialog to produce a PDF report.

What it shows:

- **KPI cards** — keywords in top 3 / top 10, average position, tracked
  count, total search volume, each with change vs the previous fetch
- **Trend charts** — average position and top-10 counts over time
  (builds up as you run the scraper on more days)
- **Winners / losers** — biggest position changes since the last fetch,
  with newly-ranking keywords flagged as "New"
- **Distributions** — position buckets and search-intent breakdown
- **Keyword table** — sortable and filterable (search, intent, position
  bucket); click any row for that keyword's position history chart

The workflow is: run the scraper (ideally daily, e.g. via Windows Task
Scheduler) -> refresh the dashboard. `demo_results.json` is fake seeded
data for demos/testing — safe to delete once you have real history.

To track a new client, just run the scraper with their `--domain` — the
dashboard picks up every domain in the data file automatically via the
domain dropdown.

## API cost

Each keyword lookup returns one report line from `domain_organic`, which
costs **10 API units** per keyword checked.
