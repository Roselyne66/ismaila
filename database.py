"""
database.py — Base auto-apprenante Cashvolt (SQLite).

Principe (décrit par Roselyne) : chaque test en boutique enrichit la base.
Plus il y a de mesures, plus les seuils s'affinent sur le parc réel.

La base alimente deux choses :
  • P97 global  — seuil d'élimination dynamique : une batterie au-dessus du
    97e percentile de toutes les mesures fait partie des 3 % les plus résistives.
  • P5 par modèle — référence "batterie neuve" terrain (5e percentile des
    mesures d'un modèle), plus fiable que les datasheets constructeur.

GARDE-FOU anti-divergence (demande explicite de Roselyne) :
  Une mesure entre dans la base avec valide=0 (en attente). Les percentiles ne
  sont calculés QUE sur les mesures validées (valide=1). Un humain (le CEO)
  valide périodiquement les nouvelles mesures via valider_mesures(), ce qui
  agit comme une relecture avant intégration — "comme une mise à jour logicielle".

Remarque importante : ce module est volontairement isolé. Si demain on remplace
SQLite par Postgres (pour la persistance en production), seules les fonctions
ci-dessous changent — diagnostic.py n'a pas à être modifié.
"""

import os
import sqlite3
from datetime import datetime

# ── Paramètres (repris du README / config) ──────────────────────────────────
DB_PATH = os.environ.get("CASHVOLT_DB", "cashvolt.db")

MIN_MESURES_POUR_P97 = 30      # mesures validées min avant d'utiliser un P97 dynamique
MIN_MESURES_POUR_P5  = 50      # mesures validées min (par modèle) avant P5 terrain
SEUIL_FALLBACK_P97   = 350.0   # mΩ — seuil si la base est insuffisante

# Plage de plausibilité : au-delà, on ignore la valeur dans les calculs
# (filet de sécurité même si une aberration a été validée par erreur).
R_MIN_VALIDE = 5.0     # mΩ
R_MAX_VALIDE = 1000.0  # mΩ


# ── Initialisation ──────────────────────────────────────────────────────────

def _connexion():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Crée les tables si elles n'existent pas. Appelée automatiquement au besoin."""
    with _connexion() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS mesures (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                date            TEXT,
                imei            TEXT,   -- identifiant unique du téléphone (relie au passeport)
                model           TEXT,
                r_batterie      REAL,   -- résistance batterie isolée, corrigée à 25°C
                soh_resistance  REAL,
                grade           TEXT,
                valide          INTEGER DEFAULT 0   -- 0 = en attente, 1 = validée
            )
        """)
        # Migration : ajoute la colonne imei si une ancienne base ne l'a pas.
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(mesures)").fetchall()]
        if "imei" not in cols:
            conn.execute("ALTER TABLE mesures ADD COLUMN imei TEXT")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS references_admin (
                model   TEXT PRIMARY KEY,
                r_ref   REAL
            )
        """)


# ── Écriture ────────────────────────────────────────────────────────────────

def archiver_mesure(model, r_batterie, soh_resistance, grade, valide=0, imei=None):
    """
    Enregistre une mesure. Par défaut valide=0 (en attente de relecture).
    L'imei relie la mesure au téléphone (pour l'historique / passeport santé).
    Ignore silencieusement les valeurs non exploitables (None ou hors plage).
    """
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


def valider_mesures(ids=None):
    """
    Garde-fou humain : promeut des mesures en attente (valide=0 → valide=1).
    • ids=None  → valide TOUTES les mesures en attente (relecture globale).
    • ids=[...] → ne valide que les identifiants donnés.
    Renvoie le nombre de mesures validées.
    """
    init_db()
    with _connexion() as conn:
        if ids is None:
            cur = conn.execute("UPDATE mesures SET valide=1 WHERE valide=0")
        else:
            marques = ",".join("?" * len(ids))
            cur = conn.execute(
                f"UPDATE mesures SET valide=1 WHERE id IN ({marques})", ids
            )
        return cur.rowcount


def definir_reference_admin(model, r_ref):
    """Saisie manuelle CEO d'une référence pour un modèle (table admin)."""
    init_db()
    with _connexion() as conn:
        conn.execute(
            "INSERT INTO references_admin (model, r_ref) VALUES (?, ?) "
            "ON CONFLICT(model) DO UPDATE SET r_ref=excluded.r_ref",
            (model, r_ref),
        )


# ── Lecture / calculs ───────────────────────────────────────────────────────

def _percentile(valeurs, p):
    """Percentile p (0-100) par interpolation linéaire. Liste vide → None."""
    if not valeurs:
        return None
    s = sorted(valeurs)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * (p / 100.0)
    bas = int(k)
    haut = min(bas + 1, len(s) - 1)
    if bas == haut:
        return s[bas]
    return s[bas] + (k - bas) * (s[haut] - s[bas])


def _mesures_valides(model=None):
    """Liste des r_batterie validées et plausibles (optionnellement pour un modèle)."""
    init_db()
    with _connexion() as conn:
        if model:
            rows = conn.execute(
                "SELECT r_batterie FROM mesures "
                "WHERE valide=1 AND model=? AND r_batterie BETWEEN ? AND ?",
                (model, R_MIN_VALIDE, R_MAX_VALIDE),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT r_batterie FROM mesures "
                "WHERE valide=1 AND r_batterie BETWEEN ? AND ?",
                (R_MIN_VALIDE, R_MAX_VALIDE),
            ).fetchall()
    return [r["r_batterie"] for r in rows]


def obtenir_p97():
    """
    Seuil d'élimination des 3 % les plus résistifs.
    Renvoie (valeur, source) :
      • ("dynamique") si ≥ MIN_MESURES_POUR_P97 mesures validées,
      • ("fallback")  sinon → SEUIL_FALLBACK_P97 (350 mΩ).
    """
    valeurs = _mesures_valides()
    if len(valeurs) >= MIN_MESURES_POUR_P97:
        return round(_percentile(valeurs, 97), 1), "dynamique"
    return SEUIL_FALLBACK_P97, "fallback"


def obtenir_r_ref_terrain(model):
    """
    Référence "batterie neuve" issue du terrain, par ordre de priorité :
      1. P5 du modèle si ≥ MIN_MESURES_POUR_P5 mesures validées,
      2. valeur saisie manuellement par le CEO (table admin),
      3. None → diagnostic.py prendra alors sa table constructeur, puis 90 mΩ.
    """
    valeurs = _mesures_valides(model)
    if len(valeurs) >= MIN_MESURES_POUR_P5:
        return round(_percentile(valeurs, 5), 1)

    init_db()
    with _connexion() as conn:
        row = conn.execute(
            "SELECT r_ref FROM references_admin WHERE model=?", (model,)
        ).fetchone()
    return row["r_ref"] if row else None


def obtenir_historique(imei):
    """
    Renvoie tous les contrôles d'un téléphone (par IMEI), du plus récent au plus ancien.
    C'est ce qui alimente le Passeport Santé : la vie complète du téléphone.
    """
    if not imei:
        return []
    init_db()
    with _connexion() as conn:
        rows = conn.execute(
            "SELECT date, model, grade, soh_resistance, valide "
            "FROM mesures WHERE imei=? ORDER BY date DESC",
            (imei,),
        ).fetchall()
    return [
        {
            "date": r["date"],
            "model": r["model"],
            "grade": r["grade"],
            "soh_resistance": r["soh_resistance"],
            "valide": bool(r["valide"]),
        }
        for r in rows
    ]


def statistiques():
    """Petit résumé pour le suivi (mesures totales, validées, en attente)."""
    init_db()
    with _connexion() as conn:
        total = conn.execute("SELECT COUNT(*) c FROM mesures").fetchone()["c"]
        valides = conn.execute("SELECT COUNT(*) c FROM mesures WHERE valide=1").fetchone()["c"]
    return {"total": total, "validees": valides, "en_attente": total - valides}
