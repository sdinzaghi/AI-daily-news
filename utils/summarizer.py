def simple_summarize(text, max_len=300):
    clean = text.replace("\n", " ").strip()
    return clean[:max_len] + "..." if len(clean) > max_len else clean
