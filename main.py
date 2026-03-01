import yaml, json, os
from datetime import date
from utils.fetcher import fetch_articles
from utils.generator import render_page
from utils.summarizer import simple_summarize

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    with open(config_path) as f:
        return yaml.safe_load(f)

def load_state():
    path = os.path.join(os.path.dirname(__file__), "state.json")
    return json.load(open(path)) if os.path.exists(path) else {}

def save_state(state):
    path = os.path.join(os.path.dirname(__file__), "state.json")
    with open(path, "w") as f:
        json.dump(state, f)

def score_article(article):
    score = 0
    title = article["title"].lower()
    summary = article["summary"].lower()

    for kw in KEYWORDS:
        if kw in title:
            score += 2
        if kw in summary:
            score += 1

    if article.get("image"):
        score += 2
    if summary.count("\n") >= 2 or len(summary) > 300:
        score += 1
    if 10 <= len(title) <= 100:
        score += 1

    return score

KEYWORDS = [
    # LLM / Language Models
    "llm", "gpt", "chatgpt", "openai", "bard", "claude", "mistral", "mixtral", "gemini",
    "transformer", "attention", "autoregressive", "language model", "tokenizer",
    "pretraining", "finetuning", "instruction tuning", "rlhf", "deepseek",

    # Multimodal
    "multimodal", "vision-language", "vlm", "clip", "blip", "llava", "flamingo", "dalle",
    "image captioning", "audio-language", "text-to-audio",

    # RL / RLHF
    "reinforcement learning", "rl", "actor-critic", "ppo", "td3", "q-learning", "policy gradient",
    "self-play", "reward shaping", "exploration",

    # ML General
    "machine learning", "deep learning", "classifier", "classification", "decision tree",
    "random forest", "xgboost", "svm", "ensemble", "supervised learning", "unsupervised learning",
    "semi-supervised", "self-supervised", "transfer learning", "meta-learning", "active learning",
    "few-shot", "zero-shot", "learning algorithm",

    # CV / Vision
    "computer vision", "object detection", "segmentation", "image classification", "resnet", "cnn", "vision transformer", "vit",
    "image generation", "style transfer", "3d reconstruction", "depth estimation", "pose estimation",

    # Diffusion
    "diffusion model", "ddpm", "score-based", "latent diffusion", "text-to-image", "stable diffusion",
    "denoising", "noise schedule",

    # Funding / Launch / Industry
    "funding", "investment", "acquisition", "launch", "release", "series a", "seed round",
    "startup", "partnership", "collaboration",

    # Benchmark / Evaluation
    "benchmark", "leaderboard", "evaluation", "mmlu", "hellaswag", "gsm8k", "truthfulqa",
    "performance", "accuracy", "score", "precision", "recall",

    # Infra / Scaling
    "scaling law", "gpu", "moe", "sparse model", "quantization", "distillation", "inference acceleration",
    "training compute", "deployment", "efficiency", "latency",

    # Open Source & Frameworks
    "huggingface", "pytorch", "tensorflow", "jax", "open source", "model card", "dataset",
    "weights", "github", "colab", "api",

    # Siganal Processing
    "signal processing", "audio", "speech", "voice", "ultrasound", "acoustic", "fft", "wavelet",
    "filtering", "sampling", "modulation", "demodulation", "beamforming", "source separation",
    "speech enhancement", "noise reduction", "echo cancellation",
]


if __name__ == "__main__":
    # for debugging to remove the state.json file
    # state_path = os.path.join(os.path.dirname(__file__), "state.json")
    # if os.path.exists(state_path):
    #     os.remove(state_path)

    config = load_config()
    state = load_state()
    pushed_ids = set(state.get("pushed_ids", []))
    date_str = date.today().strftime("%Y-%m-%d")

    # Load articles already selected earlier today
    prev_date = state.get("today_date")
    if prev_date == date_str:
        prev_news = state.get("today_news", [])
        prev_tech = state.get("today_tech", [])
    else:
        prev_news = []
        prev_tech = []

    all_articles = []
    for source in config["sources"]:
        print(f"🔍 Fetching from: {source['name']}")
        articles = fetch_articles(source)
        for article in articles:
            if article["id"] not in pushed_ids:
                article["summary"] = simple_summarize(article["summary"])
                article["score"] = score_article(article)
                all_articles.append(article)

    news_sources = [s["name"] for s in config["sources"] if s.get("category") == "news"]
    tech_sources = [s["name"] for s in config["sources"] if s.get("category") == "tech"]

    new_news = [a for a in all_articles if a["source"] in news_sources]
    new_tech = [a for a in all_articles if a["source"] in tech_sources]

    # Merge with previously selected articles from earlier runs today
    merged_news = prev_news + new_news
    merged_tech = prev_tech + new_tech

    # Deduplicate by article id, keeping the first occurrence
    seen_ids = set()
    def dedup(articles):
        result = []
        for a in articles:
            if a["id"] not in seen_ids:
                seen_ids.add(a["id"])
                result.append(a)
        return result

    merged_news = dedup(merged_news)
    merged_tech = dedup(merged_tech)

    top_news = sorted(merged_news, key=lambda x: x["score"], reverse=True)[:8]
    top_tech = sorted(merged_tech, key=lambda x: x["score"], reverse=True)[:5]

    if not top_news and not top_tech:
        print("No new articles found. Skipping page generation.")
    else:
        for article in top_news + top_tech:
            print(f"📰 Selected: {article['title']} (Score: {article['score']})")
            pushed_ids.add(article["id"])

        page_html = render_page(date_str, top_news, top_tech)

        docs_dir = os.path.join(os.path.dirname(__file__), "docs")
        os.makedirs(docs_dir, exist_ok=True)
        with open(os.path.join(docs_dir, "index.html"), "w") as f:
            f.write(page_html)
        print(f"✅ Generated docs/index.html for {date_str}")

    save_state({
        "pushed_ids": list(pushed_ids),
        "today_date": date_str,
        "today_news": top_news,
        "today_tech": top_tech,
    })