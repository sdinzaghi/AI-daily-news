import feedparser
import requests
import importlib
import ipaddress
import re
import socket
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

# --- SSRF protection ---
_ALLOWED_SCHEMES = {"http", "https"}
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]
_MAX_RESPONSE_BYTES = 2 * 1024 * 1024  # 2 MB


def _is_safe_url(url):
    try:
        parsed = urlparse(url)
        if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        for addr in socket.getaddrinfo(hostname, None):
            ip = ipaddress.ip_address(addr[4][0])
            for net in _BLOCKED_NETWORKS:
                if ip in net:
                    return False
        return True
    except Exception:
        return False


def _safe_get(url, timeout=5):
    """requests.get with SSRF protection and response size limit."""
    if not _is_safe_url(url):
        raise ValueError(f"Blocked URL: {url}")
    resp = requests.get(url, timeout=timeout, stream=True)
    if resp.is_redirect or resp.is_permanent_redirect:
        target = resp.headers.get("Location", "")
        if not _is_safe_url(target):
            raise ValueError(f"Blocked redirect: {target}")
    chunks = []
    size = 0
    for chunk in resp.iter_content(chunk_size=8192):
        chunks.append(chunk)
        size += len(chunk)
        if size > _MAX_RESPONSE_BYTES:
            resp.close()
            raise ValueError(f"Response too large from {url}")
    return b"".join(chunks).decode(resp.encoding or "utf-8", errors="replace")


# --- Allowed HTML parsers (explicit registry) ---
_ALLOWED_PARSERS = {}  # e.g. {"example_site": "utils.parser_example_site"}


def fetch_articles(source):
    if source["type"] == "rss":
        return fetch_from_rss(source)
    elif source["type"] == "html":
        parser_name = source.get("parser", "")
        if parser_name not in _ALLOWED_PARSERS:
            print(f"❌ Unknown parser: {parser_name}")
            return []
        parser_module = importlib.import_module(_ALLOWED_PARSERS[parser_name])
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
            body = _safe_get(url)
            soup = BeautifulSoup(body, "html.parser")

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
        body = _safe_get(url)
        soup = BeautifulSoup(body, "html.parser")

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
        body = _safe_get(paper_url)
        soup = BeautifulSoup(body, "html.parser")

        match = re.search(r'arxiv\.org/abs/([\d\.]+)', paper_url)
        if not match:
            return None
        paper_id = match.group(1)

        version_tag = soup.find("b", string=re.compile(r"v\d+"))
        if version_tag:
            vmatch = re.search(r'v\d+', version_tag.text)
            version = vmatch.group(0) if vmatch else "v1"
        else:
            version = "v1"

        html_url = f"https://arxiv.org/html/{paper_id}{version}/"

        body = _safe_get(html_url)
        soup = BeautifulSoup(body, "html.parser")
        fig = soup.find("figure", class_="ltx_figure")
        if fig:
            img = fig.find("img")
            if img and img.get("src"):
                return urljoin(html_url, img["src"])

    except Exception as e:
        print(f"⚠️ Failed to fetch arXiv figure: {paper_url} -> {e}")
    
    return None
