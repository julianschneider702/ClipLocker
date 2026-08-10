# Clip Tagging & Semantic Matching Pipeline

Ein Tool zur automatisierten Analyse, Verschlagwortung und semantischen Zuordnung von historischem Bild- und Videomaterial für die Produktion von Dokumentarvideos.

## Überblick

Dieses Projekt löst ein zentrales Problem bei der Produktion historischer Dokumentationen: das manuelle Durchsuchen tausender Stock-Footage-Clips nach passenden Bildern für ein Skript ist extrem zeitaufwendig. Die Pipeline automatisiert diesen Prozess in zwei Schritten:

1. **Automatisierte Bildanalyse** – Jeder Clip wird von Claude (Anthropic) analysiert, der eine präzise englische Beschreibung sowie passende Tags aus einer kuratierten Kategorienliste generiert.
2. **Semantisches Matching** – Über Sentence-Embeddings (`sentence-transformers/all-mpnet-base-v2`) werden Skriptsätze mit den generierten Clip-Beschreibungen abgeglichen, um passendes Footage automatisch vorzuschlagen – unabhängig von exakter Wortübereinstimmung.

## Features

- 🎬 **Multi-Format Support** – Verarbeitet sowohl Einzelbilder als auch Videoclips (per Frame-Extraktion an definierten Zeitstempeln)
- 🤖 **KI-gestützte Bildbeschreibung** – Nutzt Claude Haiku 4.5 oder Sonnet 4.6 je nach Qualitäts-/Kostenanforderung
- 🏷️ **Strukturiertes Tagging-System** – Kategorisierte Tags (Personen, Emotionen, Aktivitäten, Orte, Objekte, Zeit, Wetter) für präzise Filterung
- 🖥️ **Web-Interface (Dash)** – Manuelle Review und Korrektur der KI-generierten Tags vor der finalen Speicherung in der Datenbank
- 🔍 **Semantische Suche** – Findet passende Clips zu Skriptsätzen auch bei völlig unterschiedlicher Formulierung
- 🌗 **Robustheit gegen Bildqualität** – Erkennt automatisch dunkle, unscharfe oder schwer interpretierbare Aufnahmen und vermeidet Halluzinationen
- 📐 **Panorama-Handling** – Spezielle Logik für breite Panoramabilder mit mehreren visuellen Zonen

## Architektur

```
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│  Raw Media       │─────▶│  Claude API       │─────▶│  Web-Interface   │
│  (Bilder/Videos) │      │  (Beschreibung +  │      │  (Review & Fix)  │
│                  │      │   Tags)           │      │                  │
└─────────────────┘      └──────────────────┘      └────────┬────────┘
                                                              │
                                                              ▼
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│  Skript-Satz     │─────▶│  Sentence         │◀─────│  SQLite DB       │
│  (Übersetzt EN)  │      │  Embeddings       │      │  (Clips, Tags,   │
│                  │      │  (mpnet)          │      │   Embeddings)    │
└─────────────────┘      └──────────────────┘      └─────────────────┘
                                    │
                                    ▼
                          ┌──────────────────┐
                          │  Best Match Clip  │
                          └──────────────────┘
```

## Datenbankschema

```sql
CREATE TABLE "Tags" (
    "tag_name"  TEXT,
    "category"  TEXT,
    "tag_id"    INTEGER,
    PRIMARY KEY("tag_id" AUTOINCREMENT)
);

CREATE TABLE "Clips" (
    "clip_id"     INTEGER,
    "extension"   TEXT NOT NULL,
    "description" TEXT NOT NULL,
    "embedding"   BLOB NOT NULL,
    PRIMARY KEY("clip_id")
);

CREATE TABLE "ClipTag" (
    "clip_id" INTEGER,
    "tag_id"  INTEGER,
    PRIMARY KEY("clip_id", "tag_id"),
    FOREIGN KEY("clip_id") REFERENCES "Clips"("clip_id") ON DELETE CASCADE,
    FOREIGN KEY("tag_id") REFERENCES "Tags"("tag_id") ON DELETE CASCADE
);
```

Die `ClipTag`-Tabelle bildet eine klassische n:m-Beziehung ab, sodass jeder Clip beliebig viele Tags aus beliebig vielen Kategorien tragen kann.

## Tag-Kategorien

Tags sind in sieben Kategorien organisiert, um gezieltes Filtern und konsistente KI-Auswahl zu ermöglichen:

| Kategorie | Beispiele |
|---|---|
| `people` | peasant, knight, merchant, plague-doctor |
| `emotion/state` | concentrated, fearful, wounded, dead |
| `activity` | cooking, fighting, praying, harvesting |
| `place` | kitchen, castle, battlefield, forest |
| `object` | hearth, sword, herbs, chainmail |
| `time` | sunrise, daytime, nighttime |
| `weather` | snow, rain, fog, thunderstorm |

Tags werden zentral in einer Textdatei gepflegt und per Skript in die Datenbank importiert (siehe [Setup](#setup)).

## KI-Prompt-Strategie

Die Bildanalyse folgt einer strikten Entscheidungshierarchie, um Halluzinationen zu minimieren und konsistente, embeddingfreundliche Beschreibungen zu erzeugen:

1. **Qualitätsprüfung zuerst** – Bei dunklen oder unscharfen Bildern wird nur beschrieben, was eindeutig erkennbar ist; lieber unvollständig als falsch
2. **Panorama-Erkennung** – Bei breiten Szenen mit mehreren Zonen wird nur die detailreichste Zone beschrieben statt oberflächlich alles zu erfassen
3. **Inhaltstyp-Erkennung** – Unterscheidung zwischen Personen-, Objekt- und Ortsszenen mit jeweils angepasstem Beschreibungsfokus
4. **Tag-First-Ansatz** – Tags werden vor der Fließtext-Beschreibung systematisch aus der Kategorienliste ausgewählt, um Untererfassung zu vermeiden
5. **Funktionale statt rein visuelle Sprache** – Beschreibungen nutzen konkretes Vokabular (Materialien, präzise Handlungen, Objektnamen) statt vager Umschreibungen, um die semantische Nähe zu Skriptsätzen zu maximieren

Das Modell (Haiku 4.5 vs. Sonnet 4.6) wird pro Clip konfigurierbar gewählt; Haiku erhält zusätzliche Beispiele und eine Anti-Anker-Instruktion, da es stärker zu Beispiel-Nachahmung neigt als Sonnet.


Privates Projekt – keine öffentliche Lizenz vergeben.
