"""Arabic/English text normalisation used for indexing, keyword search and the mock embedder."""
from __future__ import annotations

import re
import unicodedata

_DIACRITICS = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭ]")
_TATWEEL = "ـ"
_ARABIC_CHARS = re.compile(r"[؀-ۿ]")
_LATIN_CHARS = re.compile(r"[A-Za-z]")
_TOKEN = re.compile(r"[\w؀-ۿ]+", re.UNICODE)
_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

AR_STOPWORDS = {
    "في", "من", "على", "الى", "إلى", "عن", "ان", "أن", "إن", "او", "أو", "و", "ثم", "التي", "الذي", "الذين", "هذه",
    "هذا", "ذلك", "تلك", "مع", "كل", "اي", "أي", "ما", "لا", "لم", "لن", "قد", "كان", "كانت", "يكون", "تكون", "به",
    "بها", "له", "لها", "هو", "هي", "وفق", "حيث", "عند", "بين", "كما", "غير", "ضمن", "اذا", "إذا", "يجب", "هل",
}
EN_STOPWORDS = {
    "the", "a", "an", "of", "to", "and", "or", "in", "on", "for", "with", "by", "is", "are", "be", "as", "at", "that",
    "this", "it", "from", "shall", "must", "should", "which", "what", "any", "all", "its", "their", "not", "do", "does",
}


def normalize(text: str) -> str:
    """NFKC, strip diacritics/tatweel, unify alef/yaa/taa-marbuta forms, Arabic-Indic digits, lowercase."""
    text = unicodedata.normalize("NFKC", text or "")
    text = _DIACRITICS.sub("", text).replace(_TATWEEL, "")
    text = re.sub("[إأآٱ]", "ا", text)
    text = text.replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي")
    text = text.translate(_ARABIC_DIGITS)
    text = re.sub(r"[ \t ]+", " ", text)
    return text.lower().strip()


def strip_prefix(token: str) -> str:
    """Light Arabic stemming: remove the definite article and common clitics (keeps short words intact)."""
    for p in ("وال", "بال", "كال", "فال", "لل", "ال"):
        if token.startswith(p) and len(token) - len(p) >= 3:
            return token[len(p):]
    if len(token) > 4 and token[0] in "وفب":
        return token[1:]
    return token


def tokenize(text: str, *, stem: bool = True) -> list[str]:
    out = []
    for t in _TOKEN.findall(normalize(text)):
        if t in AR_STOPWORDS or t in EN_STOPWORDS or len(t) < 2:
            continue
        out.append(strip_prefix(t) if stem else t)
    return out


def detect_language(text: str) -> str:
    ar = len(_ARABIC_CHARS.findall(text or ""))
    en = len(_LATIN_CHARS.findall(text or ""))
    if ar == 0 and en == 0:
        return "unknown"
    if ar and en and min(ar, en) / max(ar, en) > 0.25:
        return "mixed"
    return "ar" if ar >= en else "en"
