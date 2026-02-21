# -*- coding: utf-8 -*-
"""
KnowledgeDigest -- Skill-Datenbank mit FTS5-Suche.

Indexiert BACH-Skills, chunked den Content und macht ihn
durchsuchbar via FTS5-Volltextsuche.

Usage:
    from KnowledgeDigest import KnowledgeDigest

    kd = KnowledgeDigest()
    kd.index_skills("/path/to/bach.db")
    results = kd.search("agent entwickler")

Author: Lukas Geiger
License: MIT
"""

from .digest import KnowledgeDigest

__version__ = "0.1.0"
__all__ = ["KnowledgeDigest"]
