"""Demo assistant: picks a pre-written answer by keywords. There is no AI here."""
import re
import unicodedata

from app.config_loader import ChatConfig, ChatTopic


def normalize(text: str) -> list[str]:
    """Lowercase words without accents or punctuation."""
    plain = unicodedata.normalize("NFKD", text.lower())
    plain = "".join(c for c in plain if not unicodedata.combining(c))
    return re.findall(r"[a-z0-9]+", plain)


def _has(words: list[str], keyword: str) -> bool:
    """Whole word; prefix when the keyword ends in *; word sequence when it has spaces."""
    parts = keyword.split()
    for start in range(len(words) - len(parts) + 1):
        if all(words[start + i].startswith(p[:-1]) if p.endswith("*") else words[start + i] == p
               for i, p in enumerate(parts)):
            return True
    return False


def match(message: str, cfg: ChatConfig) -> ChatTopic | None:
    """Topic with the most keywords in the message; ties go to the first listed; None if none."""
    words = normalize(message)
    best, best_score = None, 0
    for topic in cfg.topics:
        score = sum(_has(words, keyword) for keyword in topic.keywords)
        if score > best_score:
            best, best_score = topic, score
    return best


def suggestions(cfg: ChatConfig, after: str | None, n: int = 3) -> list[str]:
    """Suggested questions from the topics that follow `after` in file order (wrapping)."""
    ids = [t.id for t in cfg.topics]
    start = ids.index(after) + 1 if after in ids else 0
    ordered = cfg.topics[start:] + cfg.topics[:start]
    return [t.question for t in ordered if t.question and t.id != after][:n]
