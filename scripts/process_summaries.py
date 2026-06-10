#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cron-Job: Verarbeitet 1 pending Item aus der KnowledgeDigest Queue via Ollama."""
import sys
sys.path.insert(0, '/opt/knowledgedigest/..')
from pathlib import Path
from knowledgedigest.summarizer import Summarizer

DB = Path('/opt/services/knowledgedigest/knowledge.db')

s = Summarizer(
    DB,
    provider="ollama",
    model="qwen3:4b",
    base_url="http://localhost:11434",
)

stats = s.summarize_queue(limit=1, delay=0)
if stats.get('processed', 0) > 0:
    item = stats['items'][0]
    print(f"[OK] {item['source_type']}#{item['source_id']}: "
          f"{item['chunks_summarized']} Chunks, "
          f"{stats['duration_ms']}ms")
elif stats.get('errors', 0) > 0:
    print(f"[ERR] {stats['errors']} Fehler")
# Kein Output wenn Queue leer (stille Cron-Ausfuehrung)
s.close()
