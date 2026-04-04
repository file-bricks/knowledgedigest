import sqlite3

conn = sqlite3.connect(r"C:\_Local_DEV\DATA_STORE\wissensdb.db", timeout=30)

docs = [
    (7063, 
     "KOMPASS Therapiematerial für Jugendliche mit Autismus-Spektrum-Störung (ASS). Enthält Kommentar-Karten zu Small Talk, designed von Jenny et al. für strukturierte Gesprächstraining und soziale Interaktionsfähigkeiten. Kohlhammer 2021.",
     "Small Talk, ASS, Autismus, Jugendliche, Soziale Kommunikation, KOMPASS, Therapiematerial, Gesprächstraining",
     "Therapie/Rehabilitation"),
    
    (7327,
     "PECS Kommunikationsprotokoll mit Fokus auf Tagesplanung. Unterstützt Kommunikationsziele durch visuelle Planung und Symbole. Von Pyramid Educational Products entwickelt für AAC-Systeme und Kommunikation im Tagesablauf.",
     "PECS, Kommunikation, Tagesplanung, AAC, Visuelle Unterstützung, Kommunikationsziele, Pyramid Educational",
     "Logopädie/Kommunikation"),
    
    (7629,
     "Interaktive Klettmappe zur Erarbeitung von Präpositionen (auf, unter, im, über, vor, hinter) mit Fussball- und Tor-Motiven. Haptisches Lernmaterial für Sprachtherapie, geeignet für Grundschule und frühe Sprachentwicklung.",
     "Präpositionen, Lagebeziehungen, Klettmappe, Fussball, Motorik, Sprachtherapie, Haptisches Lernen",
     "Sprachförderung"),
    
    (7883,
     "Bingo-Würfelspiel Vorlage für zwei Spieler. Verbindet Wort-Bild-Zuordnungen mit Spielmechaniken. Flexibles Arbeitsblatt für Wortschatzerweiterung und Leseverständnis im Zweipersonen-Format.",
     "Bingo, Spiel, Wort-Bild-Zuordnung, Wortschatz, Lesen, Zweipersonen-Spiel, Würfelspiel",
     "Sprachförderung"),
    
    (8071,
     "Handlungsplan 'Tee kochen' in 8 sequenziellen Schritten mit Fokus auf alltägliche Aktivitäten des täglichen Lebens (ADL). Unterstützt Verständnis von Handlungsabläufen, geeignet für Kognitives Training und Selbstständigkeitsentwicklung.",
     "Tee kochen, Handlungsplan, ADL, Sequenzplanung, Alltagsfähigkeiten, Selbstständigkeit, 8 Schritte",
     "Lebenspraktisches Training"),
    
    (8349,
     "MetaTalkDE Bilderbuch mit METACOM Symbolen. Vergleicht Hunde und Schafe anhand von visuellen Darstellungen und Symbolen. Unterstützt Sprachentwicklung und Kategorienbildung durch symbolische Kommunikation. Layout 5x9.",
     "MetaTalkDE, METACOM Symbole, Bilderbuch, Hunde, Schafe, Kategorien, Symbolische Kommunikation, Sprachentwicklung",
     "Sprachförderung"),
    
    (8350,
     "Gleicher Inhalt wie doc_id 8349 'Von Hunden und Schafen', aber in 6x11 Layout-Format für alternative Darstellung und Nutzung je nach Feldgröße und Bildschirmauflösung.",
     "MetaTalkDE, METACOM Symbole, Bilderbuch, Hunde, Schafe, Layout-Variante, 6x11, Symbolische Kommunikation",
     "Sprachförderung"),
    
    (8419,
     "Arbeitsblatt zur Buchstabenerkennung mit Fokus auf J, Q, X, Z. Schüler lesen Wörter mit diesen Buchstaben und ordnen sie korrekten Bildern zu. Grundschulmaterial zur Lese-Schreib-Förderung und Graphem-Erkennung.",
     "Buchstaben J Q X Z, Lesen, Wort-Bild-Zuordnung, Graphem-Erkennung, Grundschule, Arbeitsblatt, Lese-Förderung",
     "Lesenlernen"),
    
    (8492,
     "Ganzheitliches Leseverständnis-Training mit CID-Encoding. Grundschul-Material von vs-material.wegerer.at. Fokus auf sinnerfassendes Lesen und Textverständnis durch ganzheitliche Methode.",
     "Ganzheitliches Lesen, CID-Encoding, Leseverständnis, Sinnerfassung, Grundschule, vs-material.wegerer.at, Deutsch",
     "Lesenlernen"),
    
    (7893,
     "Brettspiel 'Immer zehn' kreiert von Lukas Geiger 2025. Rechenspiel zur Förderung von Zahlverständnis und Kombinatorik. Spielerisches Trainingsmaterial für mathematische Grundlagen.",
     "Brettspiel, Rechenspiel, Zahlverständnis, Arithmetik, Immer zehn, Lukas Geiger, Mathematik, Kombinatorik",
     "Mathematik"),
]

for doc_id, summary, keywords, domain in docs:
    conn.execute("""
        INSERT INTO summaries (source_type, source_id, chunk_index, summary, keywords, domain, model)
        VALUES ('document', ?, 0, ?, ?, ?, 'claude-haiku-4-5')
        ON CONFLICT(source_type, source_id, chunk_index) DO UPDATE SET
            summary=excluded.summary, keywords=excluded.keywords,
            domain=excluded.domain, model=excluded.model,
            created_at=CURRENT_TIMESTAMP
    """, (doc_id, summary, keywords, domain))
    conn.execute("""
        UPDATE digest_queue SET status='done', finished_at=CURRENT_TIMESTAMP
        WHERE source_type='document' AND source_id=? AND status='pending'
    """, (doc_id,))

conn.commit()
conn.close()
print("Done: 10 summaries written")
