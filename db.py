from models import embeddingModel
from logger import log

import os, shutil, sqlite3
from datetime import datetime

def createBackupOfDB(appSettings):
    dbPath = appSettings["db-path"]
    backup_folder = appSettings["backup-path"]

    os.makedirs(backup_folder, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_path = os.path.join(backup_folder, f"backup_{timestamp}.db")

    shutil.copy2(dbPath, backup_path)
    log("Backup erstellt: ", backup_path)

def addToDB(values, clip, claudeData, appSettings, epoch):
    dbPath = appSettings["db-path"]

    try:
        correctedValues = [v for v in values if v is not None]
        allTags = list({tag for sublist in correctedValues for tag in sublist})

        conn = sqlite3.connect(dbPath)
        database = conn.cursor()

        database.execute(
            "SELECT MAX(clip_id) "
            "FROM Clips"
        )
        result = database.fetchone()

        maxID = result[0] if result[0] is not None else -1  # wenn db leer, dann wird nächste id=0, wegen +1
        clipID = maxID +1

        createBackupOfDB(appSettings)

        description = None
        if claudeData and clip["name"] in claudeData:
            description = claudeData[clip["name"]].get("description")

        embedding = None
        if description:
            vector = embeddingModel.encode(description)
            embedding = vector.tobytes()

        database.execute("""
                       INSERT INTO Clips (clip_id, extension, description, embedding, epoch)
                       VALUES (?, ?, ?, ?, ?)
                       """, (clipID, clip["extension"], description, embedding, epoch))

        log("DB: Neu in Clips: ", clipID, clip["extension"])

        for tagName in allTags:
            database.execute("SELECT tag_id FROM Tags WHERE tag_name = ?", (tagName,))
            row = database.fetchone()

            if row is None:
                log("FEHLER: Tag nicht in DB gefunden:", tagName, color="red")
                continue

            tagId = row[0]

            database.execute("""
                INSERT INTO ClipTag (clip_id, tag_id)
                VALUES (?, ?)
            """, (clipID, tagId))
            log("Db: Neu in ClipTag: ", clipID, tagId, tagName)

        conn.commit()
        conn.close()

        return clipID

    except Exception as e:
        log("FEHLER: DB-Eintrag fehlgeschlagen:", e, color="red")
        return None


def readTagsFromDB(appSettings):
    dbPath = appSettings["db-path"]

    conn = sqlite3.connect(dbPath)
    database = conn.cursor()
    database.execute("SELECT category, tag_name FROM Tags ORDER BY tag_name")
    rows = database.fetchall()
    conn.close()

    data = {}
    for category, tag_name in rows:
        if category not in data:
            data[category] = []
        data[category].append(tag_name)
    return data

def fillDropdownsFromDB(clipId, tagList, appSettings):
    """Lädt bestehende Tags eines Clips aus der DB"""
    conn = sqlite3.connect(appSettings["db-path"])
    cursor = conn.cursor()
    cursor.execute("""
        SELECT t.tag_name, t.category 
        FROM Tags t
        JOIN ClipTag ct ON ct.tag_id = t.tag_id
        WHERE ct.clip_id = ?
    """, (clipId,))
    rows = cursor.fetchall()
    conn.close()

    categoryMap = {}
    for tag_name, category in rows:
        if category not in categoryMap:
            categoryMap[category] = []
        categoryMap[category].append(tag_name)

    return [categoryMap.get(category, None) for category in tagList.keys()]


def loadDescriptionFromDB(clipId, appSettings):
    """Lädt die gespeicherte Beschreibung eines Clips aus der DB"""
    conn = sqlite3.connect(appSettings["db-path"])
    cursor = conn.cursor()
    cursor.execute("SELECT description FROM Clips WHERE clip_id = ?", (clipId,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row and row[0] else ""

def loadEpochFromDB(clipId, appSettings):
    conn = sqlite3.connect(appSettings["db-path"])
    cursor = conn.cursor()
    cursor.execute("SELECT epoch FROM Clips WHERE clip_id = ?", (clipId,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row and row[0] else None


def updateClipInDB(clipId, values, dropdownIds, appSettings, epoch, description):
    if clipId is None:
        print("FEHLER: updateClipInDB – fehlende clipid")
        return False
    if not appSettings:
        print("FEHLER: updateClipInDB – fehlende appsettings")
        return False

    conn = sqlite3.connect(appSettings["db-path"])
    cursor = conn.cursor()

    try:
        print(f"[updateClipInDB] Starte Update für Clip {clipId}, Epoch: {epoch}")

        cursor.execute(
            "UPDATE Clips SET epoch = ?, description = ? WHERE clip_id = ?",
            (epoch, description, clipId)
        )
        print(f"[updateClipInDB] Epoch gesetzt: {epoch}")
        print(f"[updateClipInDB] Description gesetzt: {description}")

        if description:
            vector = embeddingModel.encode(description)
            embedding = vector.tobytes()
            cursor.execute(
                "UPDATE Clips SET embedding = ? WHERE clip_id = ?",
                (embedding, clipId)
            )
            print(f"[updateClipInDB] Embedding aktualisiert")
        else:
            cursor.execute(
                "UPDATE Clips SET embedding = NULL WHERE clip_id = ?",
                (clipId,)
            )
            print(f"[updateClipInDB] Embedding geleert da keine Description")

        cursor.execute("DELETE FROM ClipTag WHERE clip_id = ?", (clipId,))
        print(f"[updateClipInDB] Alte Tags gelöscht")

        for dropdownId, tagValues in zip(dropdownIds, values):
            if not tagValues:
                continue
            if isinstance(tagValues, str):
                tagValues = [tagValues]
            for tag in tagValues:
                cursor.execute("SELECT tag_id FROM Tags WHERE tag_name = ?", (tag,))
                row = cursor.fetchone()
                if row:
                    cursor.execute(
                        "INSERT INTO ClipTag (clip_id, tag_id) VALUES (?, ?)",
                        (clipId, row[0])
                    )
                    print(f"[updateClipInDB] Tag eingefügt: {tag} (id={row[0]})")
                else:
                    print(f"[updateClipInDB] Tag nicht gefunden: {tag}")
                    log(f"Tag nicht gefunden: {tag}", color="orange")

        conn.commit()
        print(f"[updateClipInDB] Commit erfolgreich")
        log(f"Clip {clipId} erfolgreich aktualisiert")
        return True

    except Exception as e:
        conn.rollback()
        print(f"[updateClipInDB] FEHLER: {e}")
        log(f"FEHLER beim Update von Clip {clipId}: {e}", color="red")
        return False

    finally:
        conn.close()
        print(f"[updateClipInDB] Verbindung geschlossen")