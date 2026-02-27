# -*- coding: utf-8 -*-
"""
KnowledgeDigest -- Shared Utilities.

Gemeinsame Funktionen fuer alle Module:
    - sha256_hash(): Content-Hashing fuer Aenderungserkennung
    - extract_keywords(): Keyword-Extraktion mit Stoppwort-Filterung
    - STOP_WORDS: DE/EN Stoppwoerter
"""

__all__ = ["sha256_hash", "extract_keywords", "STOP_WORDS"]

import hashlib
import re
from typing import List, Dict


# Stoppwoerter (DE/EN gemischt, fuer Keyword-Extraktion)
STOP_WORDS = frozenset({
    # Deutsch
    'der', 'die', 'das', 'ein', 'eine', 'und', 'oder', 'aber', 'ist', 'sind',
    'wird', 'werden', 'hat', 'haben', 'mit', 'von', 'auf', 'fuer', 'zur',
    'zum', 'den', 'dem', 'des', 'als', 'auch', 'nicht', 'nur', 'wenn',
    'bei', 'aus', 'nach', 'ueber', 'unter', 'vor', 'durch', 'wie', 'noch',
    'kann', 'soll', 'muss', 'alle', 'diese', 'dieser', 'dieses', 'sich',
    'dann', 'denn', 'was', 'wer', 'wo', 'hier', 'dort', 'sein', 'seine',
    'seinem', 'seinen', 'seiner', 'einer', 'eines', 'einem', 'einen',
    # Englisch
    'the', 'a', 'an', 'and', 'or', 'but', 'is', 'are', 'was', 'were',
    'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
    'will', 'would', 'could', 'should', 'may', 'might', 'must', 'shall',
    'can', 'not', 'no', 'nor', 'so', 'if', 'for', 'of', 'in', 'on', 'at',
    'to', 'from', 'by', 'with', 'as', 'into', 'it', 'its', 'this', 'that',
    'these', 'those', 'which', 'what', 'who', 'how', 'all', 'each', 'any',
    # YAML/Code
    'true', 'false', 'null', 'none', 'yes', 'default', 'type', 'name',
    'value', 'version', 'status', 'active', 'description',
})

# Minimum-Wortlaenge fuer Keywords
MIN_KEYWORD_LEN = 3
MAX_KEYWORDS_PER_ITEM = 30


def sha256_hash(text: str) -> str:
    """SHA256-Hash eines Textes."""
    return hashlib.sha256(text.encode('utf-8', errors='ignore')).hexdigest()


def extract_keywords(text: str, max_count: int = MAX_KEYWORDS_PER_ITEM) -> List[str]:
    """Extrahiert relevante Keywords aus Text.

    Strategie:
        - Alle Woerter tokenisieren
        - Stoppwoerter und zu kurze Woerter filtern
        - Nach Haeufigkeit sortieren
        - Top-N zurueckgeben
    """
    if not text:
        return []

    # Woerter extrahieren (alphanumerisch + Umlaute + Bindestriche)
    words = re.findall(
        r'[a-zA-Z\u00e4\u00f6\u00fc\u00c4\u00d6\u00dc\u00df_-]{3,}',
        text.lower()
    )

    # Stoppwoerter filtern
    words = [w for w in words if w not in STOP_WORDS and len(w) >= MIN_KEYWORD_LEN]

    # Haeufigkeit zaehlen
    freq: Dict[str, int] = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1

    # Nach Haeufigkeit sortieren, Top-N
    sorted_kw = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    return [kw for kw, _ in sorted_kw[:max_count]]
