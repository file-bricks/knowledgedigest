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


def _require_script(path: Path) -> None:
    """Abort with a clear error if an internal helper script is missing.

    haiku_batch.py and gemini_summary.py are personal operational scripts
    that are excluded from the public repo via .gitignore. Without them the
    corresponding agent modes cannot run.
    """
    if not path.exists():
        print(f"FEHLER: Benoetigtes Script fehlt: {path.name}")
        print("Dieses Script ist ein internes Hilfsscript und nicht Teil des")
        print("oeffentlichen Repos (siehe .gitignore). Ohne dieses Script ist")
        print("dieser Agenten-Modus in diesem Checkout nicht verfuegbar.")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Wissensdatenbank Zoll-Station")
    parser.add_argument("--agent", required=True, choices=["claude", "gemini", "flash"],
                        help="Dein Agenten-Identifier (z.B. claude, gemini, flash)")
    parser.add_argument("--limit", type=int, default=0,
                        help="Anzahl der Chunks, die verarbeitet werden sollen. 0 = Auto-Skalierung.")
    
    args = parser.parse_args()
    
    script_dir = Path(__file__).parent
    wissensdb_script = script_dir / "digest.py"
    haiku_script = script_dir / "haiku_batch.py"  # internal, gitignored

    # ASCII-only output: avoids UnicodeEncodeError on Windows consoles
    # (cp1252) when PYTHONIOENCODING=utf-8 is not set.
    print(f"=== [ZOLL] WILLKOMMEN AN DER ZOLL-STATION, AGENT '{args.agent.upper()}' ===")

    if args.agent == "gemini":
        limit = args.limit or 100
        print(f"Agent Gemini identifiziert. Lade {limit} Chunks auf...")

        # Check fuer API Key
        if os.environ.get("GEMINI_API_KEY"):
            print("Status: GEMINI_API_KEY gefunden. Initiierung des Hyper-Flash-Modes (API).")
            print("Fuehre API-Summarizer aus...\n")
            subprocess.run([sys.executable, str(wissensdb_script), "summarize", "--flash", "--limit", str(limit)])
        else:
            print("Status: Kein GEMINI_API_KEY gefunden. Keine Abkuerzungen erlaubt. Manueller Uebersetzungs-Zoll faellig!\n")
            print("Generiere Schwarm-Prompt fuer manuelle Verarbeitung:\n")
            _require_script(haiku_script)
            subprocess.run([sys.executable, str(haiku_script), "prep", "--limit", str(limit), "--format", "prompt"])
            print("\n[OK] (Der Agent muss den Text lesen und die JSON-Resultate eigenstaendig einpflegen)")

    elif args.agent == "claude":
        limit = args.limit or 20
        print(f"Agent Claude identifiziert. Leite an den Haiku-Schwarm-Verteiler weiter fuer {limit} Dokumente...")
        print("Generiere Schwarm-Prompt:\n")
        _require_script(haiku_script)
        subprocess.run([sys.executable, str(haiku_script), "prep", "--limit", str(limit), "--format", "prompt"])
        print("\n[OK] (Der Agent muss den Prompt abarbeiten und via .db/haiku_batch.py ingest einspielen)")

    elif args.agent == "flash":
        limit = args.limit or 15
        print(f"Agent Flash (Standalone) identifiziert. Erstelle spezialisierten Prompt fuer {limit} Dokumente...")
        # Flash uses the same prompt mechanism as Claude for now.
        _require_script(haiku_script)
        subprocess.run([sys.executable, str(haiku_script), "prep", "--limit", str(limit), "--format", "prompt"])
        print("\n[OK] (Verwende system_instruction fuer den Prompt und spiele das JSON Resultat ein)")

if __name__ == "__main__":
    main()
