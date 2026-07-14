"""
database.py — auto-apprentissage des seuils CashVolt.

Décision d'architecture retenue avec Bubble : Bubble stocke tout (les
certificats, l'historique par IMEI, le passeport santé). Cette base SQLite
locale ne sert qu'à un usage interne optionnel : affiner les seuils de
grading (percentiles P97/P5) à partir des mesures passées. Elle n'est PAS
la source de vérité de l'historique client — Render peut l'effacer au
redémarrage sans que ça n'affecte le service.
"""

import sqlite3
from datetime import datetime
from contextlib import contextmanager

DB_PATH = "cashvolt.db"
R_MIN_VALIDE = 5.0
R_MAX_VALIDE = 500.0


@contextmanager
def _connexion():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with _connexion() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS mesures (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                date            TEXT,
                imei            TEXT,
                model           TEXT,
                r_batterie      REAL,
                soh_resistance  REAL,
                grade           TEXT,
                valide          INTEGER DEFAULT 0
            )
        """)
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(mesures)").fetchall()]
        if "imei" not in cols:
            conn.execute("ALTER TABLE mesures ADD COLUMN imei TEXT")


def archiver_mesure(model, r_batterie, soh_resistance, grade, valide=0, imei=None):
    """Enregistre une mesure pour l'apprentissage interne des seuils (optionnel)."""
    if r_batterie is None or not (R_MIN_VALIDE <= r_batterie <= R_MAX_VALIDE):
        return False
    init_db()
    with _connexion() as conn:
        conn.execute(
            "INSERT INTO mesures (date, imei, model, r_batterie, soh_resistance, grade, valide) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (datetime.now().isoformat(timespec="seconds"),
             imei, model, r_batterie, soh_resistance, grade, valide),
        )
    return True


def statistiques():
    """Suivi de la base : nombre de mesures, validées, en attente."""
    init_db()
    with _connexion() as conn:
        total = conn.execute("SELECT COUNT(*) AS n FROM mesures").fetchone()["n"]
        validees = conn.execute("SELECT COUNT(*) AS n FROM mesures WHERE valide=1").fetchone()["n"]
    return {"mesures_totales": total, "mesures_validees": validees, "en_attente": total - validees}
