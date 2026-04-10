import json
import os
from copy import deepcopy

SETTINGS_PATH = "settings.json"

DEFAULT_SETTINGS = {
    "path": r"C:\\Users\\Admin\\Documents\\05-No_Mans_Sky\\Database\\",
    "db": "fotosammlung_db.db",
    "fs": "fotosammlung",
    "raw": "rohmaterial",
    "backup": "backups"
}

def load_settings():
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)

            merged = deepcopy(DEFAULT_SETTINGS)
            merged.update(data)
            return merged

        except (json.JSONDecodeError, OSError, ValueError):
            pass

    return deepcopy(DEFAULT_SETTINGS)

def save_settings(new_settings):
    merged = deepcopy(DEFAULT_SETTINGS)
    merged.update(new_settings)

    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2)

    return merged