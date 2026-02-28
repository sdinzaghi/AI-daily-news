import feedparser
import requests
import importlib
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def fetch_articles(source):
    if source["type"] == "rss":
        return fetch_from_rss(source)
    elif source["type"] == "html":
        parser_module = importlib.import_module(f"utils.parser_{source['parser']}")
        return parser_module.fetch_articles()
    else:
        print(f"❌ Unknown source type: {source['type']}")
        return []

# --- RSS parser ---
def fetch_from_rss(source):
    feed = feedparser.parse(source["url"])
    articles = []

    for entry in feed.entries[:5]:
        article_id = entry.get("id", entry.link)
        title = entry.title
        link = entry.link

        raw_summary = entry.get("summary", "")
        clean_summary = cleaning_summary(raw_summary)
        image_url = fetch_main_image(link)

        if not raw_summary or len(raw_summary) < 50:
            clean_summary = fetch_fallback_summary(link)
        
        articles.append({
            "id": article_id,
            "title": title,
            "summary": clean_summary,
            "link": link,
            "source": source["name"],
            "image": image_url,
        })

    return articles

def cleaning_summary(raw_summary: str) -> str:
    if "<" in raw_summary and ">" in raw_summary:
        soup = BeautifulSoup(raw_summary, "html.parser")

        for tag in soup(["script", "style", "img", "footer", "nav"]):
            tag.decompose()

        paragraphs = [p.get_text(strip=True) for p in soup.find_all("p") if p.get_text(strip=True)]
        text = paragraphs[0] if paragraphs else soup.get_text(separator=" ", strip=True)
    else:
        text = raw_summary.strip()

    text = re.sub(r"^arXiv:[\d\.]+v\d+\s+Announce Type:\s*\w+\s*", "", text)
    text = re.sub(r"^[【\[].*?[】\]]\s*", "", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text

UNWANTED_KEYWORDS = [
    "avatar", "logo", "icon", "favicon", "thumbnail",
    "profile", "menu", "nav", "header", "footer", "sidebar", "widget",
    "loading", "spinner", "placeholder", "empty", "no-image",
    "background", "banner", "decorative", "watermark",
    "sponsor", "ads", "advertisement", "promotion",
    "brand", "partner", "badge", "certification", 
    "arrow", "dropdown", "search","expand", "collapse",
]

CONTENT_KEYWORDS = [
    "model", "chart", "figure", "result", "example", "demo", "case", "experiment",
    "plot", "graph", "table", "visualization", 
    "architecture", "diagram", "pipeline", "framework",
    "output", "input", "prediction", "inference",
    "comparison", "ablation", "benchmark", "evaluation",
    "dataset", "data", "training", "testing",
    "demo", "sample", "case study", "application",
    "experiment", "analysis", "study", "research",
    "reconstruction", "generation", "segmentation", "translation",
    "classification", "detection", "recognition",
    "heatmap", "attention", "embedding", "feature",
    "loss", "accuracy", "precision", "recall",
    "training", "loss", "accuracy",  "performance",
    "evaluation", "metric", "score", "result",
]

def contains_any(text: str, keywords: list) -> bool:
    return any(k in text for k in keywords)

def score_image(src, alt):
    score = 0
    if contains_any(alt, CONTENT_KEYWORDS):
        score += 3
    if "cdn" not in src and "gravatar" not in src:
        score += 1
    return score

def fetch_main_image(url):
    if "arxiv.org" in url:
        return fetch_arxiv_figure(url)
    else:
        try:
            resp = requests.get(url, timeout=5)
            soup = BeautifulSoup(resp.text, "html.parser")

            candidates = soup.find_all("img")

            scored_images = []
            for img in candidates:
                src = img.get("src", "").strip()
                alt = img.get("alt", "").lower().strip()

                if not src:
                    continue
                if contains_any(src, UNWANTED_KEYWORDS + ["cdn", "gravatar"]) or contains_any(alt, UNWANTED_KEYWORDS):
                    continue
                if not src.startswith("http"):
                    src = urljoin(url, src)
                src = src.lower()

                score = score_image(src, alt)
                if score > 0:
                    scored_images.append((score, src))

            if scored_images:
                return sorted(scored_images, reverse=True)[0][1]

            return None
        except Exception as e:
            print(f"⚠️ Extract image failed: {url} -> {e}")
            return None

def fetch_fallback_summary(url):
    try:
        resp = requests.get(url, timeout=5)
        soup = BeautifulSoup(resp.text, "html.parser")

        # Try to find the main content container
        container = (
            soup.find("div", class_="prose") or
            soup.find("article") or
            soup.find("section") or
            soup.find("div", class_="content")
        )

        paragraphs = container.find_all("p") if container else soup.find_all("p")

        body_text = ""
        for p in paragraphs:
            text = p.get_text(strip=True)
            if len(text) > 30 and "cookie" not in text.lower() and "table of contents" not in text.lower():
                body_text += text + "\n\n"
                if len(body_text) > 500:
                    break
        return body_text.strip()

    except Exception as e:
        print(f"⚠️ Fallback summary failed: {url} -> {e}")
        return ""

def fetch_arxiv_figure(paper_url):
    try:
        resp = requests.get(paper_url, timeout=5)
        soup = BeautifulSoup(resp.text, "html.parser")

        match = re.search(r'arxiv\.org/abs/([\d\.]+)', paper_url)
        if not match:
            return None
        paper_id = match.group(1)

        version_tag = soup.find("b", string=re.compile(r"v\d+"))
        version = version_tag.text.strip() if version_tag else "v1"  # fallback to v1

        html_url = f"https://arxiv.org/html/{paper_id}{version}/"

        resp = requests.get(html_url, timeout=5)
        soup = BeautifulSoup(resp.text, "html.parser")
        fig = soup.find("figure", class_="ltx_figure")
        if fig:
            img = fig.find("img")
            if img and img.get("src"):
                return urljoin(html_url, img["src"])

    except Exception as e:
        print(f"⚠️ Failed to fetch arXiv figure: {paper_url} -> {e}")
    
    return None
