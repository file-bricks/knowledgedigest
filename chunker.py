# -*- coding: utf-8 -*-
"""
KnowledgeDigest -- Chunking-Algorithmus.

Teilt Skill-Content in ~400-Token-Chunks auf.
Heuristik: 1 Token ~ 1 Wort (konservativ fuer gemischten DE/EN/YAML-Content).

Strategie:
    1. YAML-Frontmatter wird als eigener Chunk extrahiert
    2. Body wird an Satzgrenzen gesplittet
    3. Chunks von ~300-400 Woertern (Target: 350)
    4. Optional: Overlap von 50-100 Woertern
"""

__all__ = ["chunk_text", "split_frontmatter", "estimate_tokens"]

import re
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

# Chunk-Konfiguration
DEFAULT_CHUNK_SIZE = 350     # Ziel-Woerter pro Chunk (~400 Token)
MAX_CHUNK_SIZE = 500         # Harte Obergrenze
MIN_CHUNK_SIZE = 50          # Minimum (kleinere werden angehaengt)
DEFAULT_OVERLAP = 0          # Standard: kein Overlap


@dataclass
class Chunk:
    """Ein Textabschnitt mit Metadaten."""
    index: int
    content: str
    token_count: int
    is_frontmatter: bool = False

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "content": self.content,
            "token_count": self.token_count,
            "is_frontmatter": self.is_frontmatter,
        }


def estimate_tokens(text: str) -> int:
    """Schaetzt Token-Anzahl ueber Wortanzahl (konservativ)."""
    if not text:
        return 0
    return len(text.split())


def split_frontmatter(text: str) -> Tuple[Optional[str], str]:
    """Trennt YAML-Frontmatter vom Body.

    BACH Skills haben oft das Format:
        ---
        name: ...
        metadata: ...
        ---
        # Body content

    Returns:
        (frontmatter, body) -- frontmatter ist None wenn nicht vorhanden
    """
    if not text:
        return None, ""

    text = text.strip()

    # Frontmatter: beginnt mit --- und endet mit ---
    if text.startswith("---"):
        # Suche das schliessende ---
        end_match = re.search(r'\n---\s*\n', text[3:])
        if end_match:
            end_pos = end_match.end() + 3  # +3 fuer das erste ---
            frontmatter = text[:end_pos].strip()
            body = text[end_pos:].strip()
            return frontmatter, body

    return None, text


def _split_sentences(text: str) -> List[str]:
    """Teilt Text in Saetze/Absaetze auf.

    Splittet an:
    - Leerzeilen (Absaetze)
    - Satzenden (. ! ?) gefolgt von Grossbuchstabe oder Zeilenumbruch
    - Markdown-Ueberschriften (#)
    - Listen-Items (- oder *)
    """
    if not text:
        return []

    # Erst an Leerzeilen splitten (Absaetze)
    paragraphs = re.split(r'\n\s*\n', text)

    segments = []
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # Innerhalb eines Absatzes: an Satzgrenzen splitten
        # Aber nur wenn der Absatz lang genug ist
        if estimate_tokens(para) <= MAX_CHUNK_SIZE:
            segments.append(para)
        else:
            # Langen Absatz an Satzgrenzen splitten
            sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z\u00C4\u00D6\u00DC])', para)
            if len(sentences) <= 1:
                # Fallback: an Zeilenumbruechen splitten
                sentences = para.split('\n')
            segments.extend(s.strip() for s in sentences if s.strip())

    return segments


def chunk_text(text: str, chunk_size: int = DEFAULT_CHUNK_SIZE,
               overlap: int = DEFAULT_OVERLAP,
               separate_frontmatter: bool = True) -> List[Chunk]:
    """Teilt Text in Chunks auf.

    Args:
        text: Volltext des Skills
        chunk_size: Ziel-Woerter pro Chunk (Default: 350)
        overlap: Overlap in Woertern zwischen Chunks (Default: 0)
        separate_frontmatter: Frontmatter als eigenen Chunk extrahieren

    Returns:
        Liste von Chunk-Objekten
    """
    if not text or not text.strip():
        return []

    chunks = []
    chunk_idx = 0

    # Frontmatter separieren
    frontmatter = None
    body = text
    if separate_frontmatter:
        frontmatter, body = split_frontmatter(text)

    if frontmatter:
        chunks.append(Chunk(
            index=chunk_idx,
            content=frontmatter,
            token_count=estimate_tokens(frontmatter),
            is_frontmatter=True,
        ))
        chunk_idx += 1

    # Body in Segmente splitten
    segments = _split_sentences(body)
    if not segments:
        return chunks

    # Segmente zu Chunks zusammenfassen
    current_parts: List[str] = []
    current_tokens = 0

    for segment in segments:
        seg_tokens = estimate_tokens(segment)

        # Wenn einzelnes Segment schon zu gross: forciert eigenen Chunk
        if seg_tokens > MAX_CHUNK_SIZE:
            # Aktuelle Teile erst abschliessen
            if current_parts:
                content = "\n\n".join(current_parts)
                chunks.append(Chunk(
                    index=chunk_idx,
                    content=content,
                    token_count=estimate_tokens(content),
                ))
                chunk_idx += 1
                current_parts = []
                current_tokens = 0

            # Grosses Segment als eigenen Chunk
            chunks.append(Chunk(
                index=chunk_idx,
                content=segment,
                token_count=seg_tokens,
            ))
            chunk_idx += 1
            continue

        # Passt Segment noch in aktuellen Chunk?
        if current_tokens + seg_tokens <= chunk_size:
            current_parts.append(segment)
            current_tokens += seg_tokens
        else:
            # Aktuellen Chunk abschliessen
            if current_parts:
                content = "\n\n".join(current_parts)
                chunks.append(Chunk(
                    index=chunk_idx,
                    content=content,
                    token_count=estimate_tokens(content),
                ))
                chunk_idx += 1

                # Overlap: letzte Teile uebernehmen
                if overlap > 0:
                    overlap_parts = []
                    overlap_tokens = 0
                    for part in reversed(current_parts):
                        pt = estimate_tokens(part)
                        if overlap_tokens + pt > overlap:
                            break
                        overlap_parts.insert(0, part)
                        overlap_tokens += pt
                    current_parts = overlap_parts + [segment]
                    current_tokens = overlap_tokens + seg_tokens
                else:
                    current_parts = [segment]
                    current_tokens = seg_tokens
            else:
                current_parts = [segment]
                current_tokens = seg_tokens

    # Letzten Chunk abschliessen
    if current_parts:
        content = "\n\n".join(current_parts)
        tokens = estimate_tokens(content)

        # Zu kleiner letzter Chunk? An vorherigen anhaengen
        if tokens < MIN_CHUNK_SIZE and len(chunks) > 0 and not chunks[-1].is_frontmatter:
            prev = chunks[-1]
            merged = prev.content + "\n\n" + content
            chunks[-1] = Chunk(
                index=prev.index,
                content=merged,
                token_count=estimate_tokens(merged),
                is_frontmatter=prev.is_frontmatter,
            )
        else:
            chunks.append(Chunk(
                index=chunk_idx,
                content=content,
                token_count=tokens,
            ))

    return chunks
