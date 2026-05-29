import sqlite3
from config import DB_PATH


def init():
    con = sqlite3.connect(DB_PATH)
    con.executescript("""
        PRAGMA journal_mode = WAL;

        CREATE TABLE IF NOT EXISTS analyses (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at   TEXT    NOT NULL,
            crop         TEXT    NOT NULL,
            location     TEXT    DEFAULT '',
            image_path   TEXT    DEFAULT '',
            visual_diag  TEXT    DEFAULT '',
            result_json  TEXT    NOT NULL,
            modules_json TEXT    DEFAULT '[]'
        );

        CREATE TABLE IF NOT EXISTS weather_cache (
            location   TEXT PRIMARY KEY,
            fetched_at TEXT NOT NULL,
            data_json  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS crop_plots (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at  TEXT    NOT NULL,
            crop        TEXT    NOT NULL,
            location    TEXT    NOT NULL,
            planted_at  TEXT    NOT NULL,
            lat         REAL,
            lon         REAL,
            notes       TEXT    DEFAULT '',
            history_json TEXT   DEFAULT NULL
        );
    """)
    con.commit()
    con.close()
