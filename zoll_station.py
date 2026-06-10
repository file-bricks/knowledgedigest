# -*- coding: utf-8 -*-
"""
Zoll-Station -- Der zentrale Hub zur Entrichtung des "Zolls" für KI-Agenten.
Jeder Agent, der an diesem Repo arbeitet, sollte diese Station passieren, um Dokumenten-Chunks zu summarisieren.

Usage:
    python zoll_station.py --agent <agent_name> [--limit <anzahl>]

Agenten:
    - claude: Gibt einen dedizierten Prompt für Claude/Haiku-Schwärme zurück.
    - gemini: Nutzt die superschnelle Flash-API (falls Key vorhanden) oder den Offline-Bypass.
    - flash: Wie Claude, nur mit optimiertem Flash-Prompt für manuelle Verarbeitung.
"""

import argparse
import os
import sys
import subprocess
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Wissensdatenbank Zoll-Station")
    parser.add_argument("--agent", required=True, choices=["claude", "gemini", "flash"],
                        help="Dein Agenten-Identifier (z.B. claude, gemini, flash)")
    parser.add_argument("--limit", type=int, default=0,
                        help="Anzahl der Chunks, die verarbeitet werden sollen. 0 = Auto-Skalierung.")
    
    args = parser.parse_args()
    
    script_dir = Path(__file__).parent
    wissensdb_script = script_dir / "digest.py"
    haiku_script = script_dir / "haiku_batch.py"
    gemini_offline_script = script_dir / "gemini_summary.py"

    print(f"=== 🛑 WILLKOMMEN AN DER ZOLL-STATION, AGENT '{args.agent.upper()}' ===")
    
    if args.agent == "gemini":
        limit = args.limit or 100
        print(f"Agent Gemini identifiziert. Lade {limit} Chunks auf...")
        
        # Check für API Key
        if os.environ.get("GEMINI_API_KEY"):
            print("Status: GEMINI_API_KEY gefunden. Initiierung des Hyper-Flash-Modes (API).")
            print("Führe API-Summarizer aus...\n")
            subprocess.run([sys.executable, str(wissensdb_script), "summarize", "--flash", "--limit", str(limit)])
        else:
            print("Status: Kein GEMINI_API_KEY gefunden. Keine Abkürzungen erlaubt. Manueller Übersetzungs-Zoll fällig!\n")
            print("Generiere Schwarm-Prompt für manuelle Verarbeitung:\n")
            subprocess.run([sys.executable, str(haiku_script), "prep", "--limit", str(limit), "--format", "prompt"])
            print("\n✅ (Der Agent muss den Text lesen und die JSON-Resultate eigenständig einpflegen)")

    elif args.agent == "claude":
        limit = args.limit or 20
        print(f"Agent Claude identifiziert. Leite an den Haiku-Schwarm-Verteiler weiter für {limit} Dokumente...")
        print("Generiere Schwarm-Prompt:\n")
        subprocess.run([sys.executable, str(haiku_script), "prep", "--limit", str(limit), "--format", "prompt"])
        print("\n✅ (Der Agent muss den Prompt abarbeiten und via .db/haiku_batch.py ingest einspielen)")
        
    elif args.agent == "flash":
        limit = args.limit or 15
        print(f"Agent Flash (Standalone) identifiziert. Erstelle spezialisierten Prompt für {limit} Dokumente...")
        # Flash nutzt vorerst den gleichen Prompt-Mechanismus wie Claude, aber wir könnten ihn optimieren.
        subprocess.run([sys.executable, str(haiku_script), "prep", "--limit", str(limit), "--format", "prompt"])
        print("\n✅ (Verwende system_instruction für den Prompt und spiele das JSON Resultat ein)")

if __name__ == "__main__":
    main()
