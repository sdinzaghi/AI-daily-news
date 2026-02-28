# AI Daily News

Automated daily AI news page published via GitHub Pages. Collects articles from public RSS feeds, ranks them by relevance, and generates a static HTML page.

## How it works

1. Fetches recent entries from RSS feeds defined in `config.yaml`.
2. Scores articles using keyword matching and content signals.
3. Picks top items per category (8 news, 5 research/tech).
4. Generates `docs/index.html` — a dark-themed single-page site.
5. `state.json` tracks posted article IDs to avoid duplicates across runs.

## Project layout

- `main.py` — entry point: fetch, score, generate page.
- `config.yaml` — RSS feed sources.
- `state.json` — deduplication state.
- `docs/index.html` — generated output (served by GitHub Pages).
- `utils/fetcher.py` — RSS fetching, summary cleanup, image extraction.
- `utils/generator.py` — HTML page generation.
- `utils/summarizer.py` — text truncation helper.
- `.github/workflows/daily_news.yml` — GitHub Actions daily schedule.

## Setup

### Prerequisites

- Python 3.10+
- pip

### Install dependencies

```bash
pip install -r requirements.txt
```

### Run locally

```bash
python main.py
open docs/index.html
```

### Enable GitHub Pages

1. Push this repo to GitHub.
2. Go to **Settings > Pages**.
3. Set source to **Deploy from a branch**.
4. Select **main** branch, **/docs** folder.
5. Save — the site will be live at `https://<user>.github.io/<repo>/`.

The GitHub Actions workflow runs daily at 06:00 UTC and can also be triggered manually from the Actions tab.

## Customization

- **Posting volume**: adjust `[:8]` / `[:5]` in `main.py`.
- **Per-feed intake**: change `feed.entries[:5]` in `utils/fetcher.py`.
- **Relevance tuning**: update `KEYWORDS` and `score_article()` in `main.py`.
- **Add feeds**: append entries in `config.yaml`.
