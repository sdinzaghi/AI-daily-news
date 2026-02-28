import html
from urllib.parse import urlparse


def _safe_link(raw_link):
    """Return the link only if it uses http or https, else '#'."""
    try:
        parsed = urlparse(raw_link or "")
        if parsed.scheme.lower() in {"http", "https"}:
            return html.escape(raw_link)
    except Exception:
        pass
    return "#"


def render_article_card(article):
    title = html.escape(article.get("title") or "Untitled")
    source = html.escape(article.get("source") or "Unknown")
    summary = html.escape(article.get("summary") or "")
    link = _safe_link(article.get("link") or "#")
    image_url = (article.get("image") or "").strip().replace("\n", "").replace("\r", "")
    score = article.get("score", 0)

    image_html = ""
    if image_url.startswith("http"):
        image_html = (
            f'<img src="{html.escape(image_url)}" alt="" loading="lazy" '
            f'onerror="this.style.display=\'none\'" '
            f'style="width:100%;border-radius:8px;margin-top:12px">'
        )

    return f"""<article style="background:#1e1e2e;border-radius:12px;padding:20px;margin-bottom:16px">
  <span style="background:#313244;color:#cdd6f4;padding:4px 10px;border-radius:6px;font-size:0.8em">{source}</span>
  <h3 style="margin:10px 0 8px"><a href="{link}" target="_blank" rel="noopener" style="color:#89b4fa;text-decoration:none">{title}</a></h3>
  <p style="color:#a6adc8;line-height:1.6;margin:0">{summary}</p>
  {image_html}
</article>"""


def render_page(date_str, news_articles, tech_articles):
    news_cards = "\n".join(render_article_card(a) for a in news_articles)
    tech_cards = "\n".join(render_article_card(a) for a in tech_articles)

    if not news_cards:
        news_cards = '<p style="color:#6c7086">No news articles today.</p>'
    if not tech_cards:
        tech_cards = '<p style="color:#6c7086">No research articles today.</p>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src https:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'">
<meta http-equiv="X-Content-Type-Options" content="nosniff">
<meta name="referrer" content="no-referrer">
<title>AI Daily News — {html.escape(date_str)}</title>
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{background:#11111b;color:#cdd6f4;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;padding:24px;max-width:820px;margin:0 auto}}
  h1{{font-size:1.8em;margin-bottom:4px}}
  h2{{color:#89b4fa;margin:32px 0 16px;font-size:1.3em}}
  .date{{color:#6c7086;margin-bottom:24px}}
  a:hover{{text-decoration:underline}}
</style>
</head>
<body>
<h1>AI Daily News</h1>
<p class="date">{html.escape(date_str)}</p>

<h2>News</h2>
{news_cards}

<h2>Research &amp; Tech</h2>
{tech_cards}

<footer style="text-align:center;color:#6c7086;margin-top:48px;padding:16px;font-size:0.85em">
  Generated automatically from public RSS feeds.
</footer>
</body>
</html>
"""
