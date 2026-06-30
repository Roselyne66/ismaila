"""
diagnostic.py — Cashvolt Battery Diagnostic
Algorithme complet de diagnostic batterie en un seul fichier.
Utilisé par generate_test_report.py avant la génération du certificat PDF.

Flux : parse_all(payload) → lancer_diagnostic(data) → ResultatDiagnostic
"""

import re
from typing import Optional, Tuple, List

from metrology import appliquer_metrologie


# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION — Seuils et paramètres métier
# ─────────────────────────────────────────────────────────────────────────────

SEUIL_TENSION_MIN    = 2.8      # V   — seuil minimum post-réveil JCID
SEUIL_CAPACITE_MIN   = 85.0     # %   — ratio capacité mesurée/nominale minimum
TEMP_MIN             = 15.0     # °C  — limite basse de mesure fiable
TEMP_MAX             = 40.0     # °C  — limite haute de mesure fiable
T_REF                = 25.0     # °C  — température de référence standard
ALPHA_THERMIQUE      = 0.008    # /°C — coefficient Li-Ion pour correction thermique
SEUIL_FALLBACK_P97   = 350.0    # mΩ  — seuil résistance si base de données vide
SEUIL_FALLBACK_R_REF = 90.0     # mΩ  — R_ref par défaut si modèle inconnu
R_MIN_PLAUSIBLE      = 10.0     # mΩ  — en-dessous : valeur non physique
R_MAX_PLAUSIBLE      = 1000.0   # mΩ  — au-dessus  : valeur non physique
PENALITE_NON_OEM     = 1.0      # %   — pénalité SoH si batterie compatible (non-OEM)
POIDS_CAPACITE       = 0.50
POIDS_RESISTANCE     = 0.50

# Table de références R_ref neuve (mΩ) par modèle — sources : datasheets + terrain
REFERENCE_R_PAR_MODELE = {
    # Samsung
    "SM-A145R":   88,   # Galaxy A14 5G — 5000mAh
    "SM-A546B":   75,   # Galaxy A54 5G — 5000mAh
    "SM-S918B":   60,   # Galaxy S23 Ultra — 5000mAh
    "SM-S911B":   65,   # Galaxy S23 — 3900mAh
    "SM-A325F":   80,   # Galaxy A32 — 5000mAh
    "SM-A528B":   78,   # Galaxy A52s 5G — 4500mAh
    "SM-G991B":   62,   # Galaxy S21 — 4000mAh
    # Apple
    "iPhone14,2": 55,   # iPhone 13 Pro — 3095mAh
    "iPhone14,5": 58,   # iPhone 13 — 3227mAh
    "iPhone15,2": 52,   # iPhone 14 Pro — 3200mAh
    "iPhone15,4": 55,   # iPhone 14 — 3279mAh
    # Xiaomi
    "2201123G":   82,   # Xiaomi 12 — 4500mAh
    "22071212AG": 85,   # Redmi Note 11 — 5000mAh
}


# ─────────────────────────────────────────────────────────────────────────────
# VERDICTS
# ─────────────────────────────────────────────────────────────────────────────

VALIDE      = "VALIDE"
A_REMPLACER = "À REMPLACER"
ERREUR      = "ERREUR"


# ─────────────────────────────────────────────────────────────────────────────
# PARSERS — Conversion des champs string vers types Python
# ─────────────────────────────────────────────────────────────────────────────

def _parse_float(value, field_name: str = "") -> Optional[float]:
    """Extrait un float depuis une string comme '4.21 V', '148 mOhm', '31 C'."""
    if value is None:
        return None
    cleaned = re.sub(r"[^\d.,-]", "", str(value).replace(",", "."))
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_capacity(value) -> Tuple[Optional[float], Optional[float]]:
    """'4860 / 5000mAh' → (4860.0, 5000.0)"""
    if value is None:
        return None, None
    numbers = re.findall(r"[\d]+(?:[.,]\d+)?", str(value).replace(",", "."))
    if len(numbers) >= 2:
        try:
            return float(numbers[0]), float(numbers[1])
        except ValueError:
            pass
    elif len(numbers) == 1:
        try:
            val = float(numbers[0])
            return val, val
        except ValueError:
            pass
    return None, None


def _parse_bool(value) -> bool:
    """Normalise true/false/1/0/oui/non → bool."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    s = str(value).strip().lower()
    return s in ("true", "1", "oui", "yes", "o")


def _parse_inspection(value) -> str:
    """Normalise la valeur d'inspection visuelle."""
    valid = {"ok", "gonflee", "corrosion", "choc_mecanique"}
    v = str(value).strip().lower().replace(" ", "_") if value else "ok"
    return v if v in valid else "ok"


def parse_all(payload: dict) -> dict:
    """
    Parse l'ensemble du payload Bubble et retourne un dict de valeurs typées.
    Les 3 champs optionnels (inspection_visuelle, batterie_oem, reveil_jcid)
    ont une valeur par défaut si absents.
    """
    cap_mesuree, cap_nominale = _parse_capacity(payload.get("capacity", ""))
    if payload.get("capacity_nominal"):
        cap_nominale = _parse_float(payload.get("capacity_nominal"))
    if payload.get("capacity_measured"):
        cap_mesuree = _parse_float(payload.get("capacity_measured"))

    return {
        "customer_name":      payload.get("customer_name", ""),
        "customer_location":  payload.get("customer_location", ""),
        "operator_name":      payload.get("operator_name", ""),
        "dossier_number":     payload.get("dossier_number", ""),
        "num_interne":        payload.get("num_interne", ""),
        "imei_1":             payload.get("imei_1", ""),
        "imei_2":             payload.get("imei_2", ""),
        "model":              payload.get("model", "").strip(),
        "market_name":        payload.get("market_name", ""),
        "manufacturer":       payload.get("manufacturer", ""),
        "tension":            _parse_float(payload.get("tension")),
        "resistance_brute":   _parse_float(payload.get("mesure_resistance")),
        "temperature":        _parse_float(payload.get("temperature")),
        "charge_level":       _parse_float(payload.get("charge_level")),
        "capacite_mesuree":   cap_mesuree,
        "capacite_nominale":  cap_nominale,
        "recharge_cycle":     (int(str(payload.get("recharge_cycle")).strip())
                               if payload.get("recharge_cycle") is not None else None),
        # Champs optionnels — valeur par défaut si absent du payload Bubble
        "inspection_visuelle": _parse_inspection(payload.get("inspection_visuelle", "ok")),
        "reveil_jcid":        _parse_bool(payload.get("reveil_jcid", False)),
        "batterie_oem":       _parse_bool(payload.get("batterie_oem", True)),
        # SOH constructeur (% lu sur le téléphone) — utilisé pour le grade A++.
        # Optionnel : None si le modèle ne l'affiche pas → le grade plafonne à A+.
        "soh_constructeur":   _parse_float(payload.get("soh_constructeur")),
        # Métrologie (vient de la brique de Mohamed) — pour isoler la batterie seule.
        # Optionnels : si absents, l'algo utilise la mesure brute avec un avertissement.
        "r_board_bas":        _parse_float(payload.get("r_board_bas")),
        "r_board_haut":       _parse_float(payload.get("r_board_haut")),
        "r_cable":            _parse_float(payload.get("r_cable")),
        "position_board":     payload.get("position_board", "milieu"),
        "start_time":         payload.get("start_time", ""),
        "end_time":           payload.get("end_time", ""),
        "statut":             payload.get("statut", ""),
    }


# ─────────────────────────────────────────────────────────────────────────────
# CORRECTIONS — Correction thermique + contrôles de cohérence
# ─────────────────────────────────────────────────────────────────────────────

def _corriger_resistance_thermique(r_mesuree: float, temperature: float) -> float:
    """
    Normalise la résistance à T_REF (25°C).
    Formule standard Li-Ion : R_corrigée = R_mesurée / (1 + α × (T - 25))
    """
    facteur = 1 + ALPHA_THERMIQUE * (temperature - T_REF)
    if facteur <= 0:
        facteur = 0.01
    return round(r_mesuree / facteur, 2)


def _verifier_plausibilite(r_mesuree: float) -> Tuple[bool, str]:
    if r_mesuree < R_MIN_PLAUSIBLE:
        return False, f"Résistance trop basse ({r_mesuree} mΩ) — vérifier le contact des sondes"
    if r_mesuree > R_MAX_PLAUSIBLE:
        return False, f"Résistance trop haute ({r_mesuree} mΩ) — vérifier le contact des sondes"
    return True, ""


def _verifier_coherence(
    ratio_capacite: float,
    r_corrigee: float,
    r_ref: float,
    cycles: Optional[int]
) -> Tuple[str, str]:
    """Détecte un BMS potentiellement réécrit (compteur de cycles falsifié)."""
    if cycles is None:
        return "ok", ""
    soh_r = (r_ref / r_corrigee * 100) if r_corrigee > 0 else 0
    if cycles < 5 and soh_r < 60 and ratio_capacite < 85:
        return "incoherent", (
            f"Incohérence : {cycles} cycles déclarés mais état dégradé "
            f"(SoH-R : {soh_r:.0f}%, capacité : {ratio_capacite:.0f}%) — BMS potentiellement réécrit"
        )
    if cycles < 20 and soh_r < 75:
        return "suspect", (
            f"Attention : seulement {cycles} cycles déclarés mais résistance élevée "
            f"(SoH-R : {soh_r:.0f}%) — compteur potentiellement modifié"
        )
    return "ok", ""


# ─────────────────────────────────────────────────────────────────────────────
# SCORING — Score client 1–10 et durée de vie estimée
# ─────────────────────────────────────────────────────────────────────────────

DUREE_VIE = {
    1:  "6 mois à 1 an",
    2:  "6 mois à 1 an",
    3:  "1 à 2 ans",
    4:  "1 à 2 ans",
    5:  "2 à 3 ans",
    6:  "2 à 3 ans",
    7:  "3 à 4 ans",
    8:  "3 à 4 ans",
    9:  "4 à 5 ans",
    10: "5 ans",
}


def _soh_r_vers_score(soh_r: float) -> int:
    """Grille discrète SoH_R (%) → score résistance (1–10)."""
    if soh_r >= 100: return 10
    elif soh_r >= 95: return 9
    elif soh_r >= 90: return 8
    elif soh_r >= 85: return 7
    elif soh_r >= 80: return 6
    elif soh_r >= 75: return 5
    elif soh_r >= 70: return 4
    elif soh_r >= 65: return 3
    elif soh_r >= 60: return 2
    else: return 1


def _calculer_score(
    ratio_capacite: Optional[float],
    soh_r_affiche: Optional[float],
    verdict: str
) -> Tuple[int, str]:
    if verdict == A_REMPLACER:
        score = 1 if (ratio_capacite is not None and ratio_capacite < 70) else 2
        return score, DUREE_VIE[score]
    if verdict == ERREUR:
        return 3, DUREE_VIE[3]
    score_cap = (
        (ratio_capacite - SEUIL_CAPACITE_MIN) / (100.0 - SEUIL_CAPACITE_MIN) * 10.0
        if ratio_capacite is not None else 5.0
    )
    score_cap = max(0.0, min(10.0, score_cap))
    score_r = float(_soh_r_vers_score(soh_r_affiche)) if soh_r_affiche is not None else 5.0
    score_final = max(1, min(10, round(score_cap * POIDS_CAPACITE + score_r * POIDS_RESISTANCE)))
    return score_final, DUREE_VIE[score_final]


# ─────────────────────────────────────────────────────────────────────────────
# RÉSULTAT — Objet retourné par lancer_diagnostic()
# ─────────────────────────────────────────────────────────────────────────────

class ResultatDiagnostic:
    def __init__(self):
        self.verdict: str = VALIDE
        self.motifs_refus: List[str] = []
        self.avertissements: List[str] = []
        self.score_client: int = 0
        self.duree_vie_estimee: str = ""
        self.r_corrigee: Optional[float] = None
        self.r_batterie_seule: Optional[float] = None   # après soustraction métrologie
        self.r_offset_metrologie: Optional[float] = None # board + câble soustraits
        self.r_ref: Optional[float] = None
        self.soh_resistance: Optional[float] = None
        self.ratio_capacite: Optional[float] = None

    def _refuser(self, motif: str):
        self.motifs_refus.append(motif)
        if self.verdict == VALIDE:
            self.verdict = A_REMPLACER

    def _erreur(self, motif: str):
        self.motifs_refus.append("[ERREUR] " + motif)
        if self.verdict == VALIDE:
            self.verdict = ERREUR

    def __repr__(self):
        return f"<Diagnostic verdict={self.verdict} score={self.score_client}>"


# ─────────────────────────────────────────────────────────────────────────────
# MOTEUR PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def lancer_diagnostic(data: dict) -> ResultatDiagnostic:
    """
    Point d'entrée principal.
    data = résultat de parse_all()
    Retourne un ResultatDiagnostic complet.
    """
    r = ResultatDiagnostic()

    # ── Étape 0 : Contrôle de la température ─────────────────────────────────
    temperature = data.get("temperature")
    if temperature is not None and (temperature < TEMP_MIN or temperature > TEMP_MAX):
        r.avertissements.append(
            f"Température hors plage ({temperature}°C) — "
            f"mesures entre {TEMP_MIN}°C et {TEMP_MAX}°C recommandées"
        )

    # ── Étape 1 : Inspection visuelle (éliminatoire) ──────────────────────────
    inspection = data.get("inspection_visuelle", "ok")
    if inspection != "ok":
        labels = {
            "gonflee":        "batterie gonflée (déformation physique visible)",
            "corrosion":      "traces de corrosion sur les connecteurs",
            "choc_mecanique": "choc mécanique ou déformation du boîtier",
        }
        r._refuser(f"Défaut physique : {labels.get(inspection, inspection)}")
        _finaliser(r, data)
        return r

    # ── Étape 2 : Protocole tension (éliminatoire) ────────────────────────────
    tension = data.get("tension")
    reveil_jcid = data.get("reveil_jcid", False)

    if tension is None:
        if not reveil_jcid:
            r._erreur("Aucune tension lue — effectuer le réveil JCID (10s en charge) puis ressaisir")
        else:
            r._refuser("Aucune tension après réveil JCID — batterie morte ou court-circuit interne")
        _finaliser(r, data)
        return r

    if tension < SEUIL_TENSION_MIN:
        if not reveil_jcid:
            r._erreur(
                f"Tension trop basse ({tension}V < {SEUIL_TENSION_MIN}V) — "
                f"effectuer le réveil JCID avant de conclure"
            )
        else:
            r._refuser(
                f"Tension insuffisante après réveil JCID "
                f"({tension}V < {SEUIL_TENSION_MIN}V) — dégradation irréversible"
            )
        _finaliser(r, data)
        return r

    # ── Étape 3 : Contrôle capacité ───────────────────────────────────────────
    cap_mesuree = data.get("capacite_mesuree")
    cap_nominale = data.get("capacite_nominale")

    if cap_mesuree is not None and cap_nominale is not None and cap_nominale > 0:
        ratio = round(cap_mesuree / cap_nominale * 100, 1)
        r.ratio_capacite = ratio
        if ratio < SEUIL_CAPACITE_MIN:
            r._refuser(
                f"Capacité insuffisante : {ratio}% de la nominale "
                f"(seuil : {SEUIL_CAPACITE_MIN}%) — {cap_mesuree:.0f} / {cap_nominale:.0f} mAh"
            )
    else:
        r.avertissements.append("Données de capacité manquantes ou non parsables")
        if r.verdict == VALIDE:
            r.verdict = ERREUR
            r.motifs_refus.append("[ERREUR] Capacité non mesurée — impossible de certifier")

    # ── Étape 4 : Résistance interne ──────────────────────────────────────────
    r_brute = data.get("resistance_brute")

    if r_brute is None:
        r._erreur("Résistance interne non mesurée — vérifier que le BMS est actif")
        _finaliser(r, data)
        return r

    plausible, msg_plausibilite = _verifier_plausibilite(r_brute)
    if not plausible:
        r._erreur(msg_plausibilite)
        _finaliser(r, data)
        return r

    # ── Étape 4.0 : Isolation de la batterie (soustraction métrologie) ───────
    # R_total mesurée = R_batterie + R_board + R_câble  →  on retire board + câble
    # pour ne garder que la batterie. Si la métrologie n'est pas encore
    # disponible pour ce board, on garde la mesure brute (+ avertissement).
    r_mesure, r_offset, msg_metro, metro_ok = appliquer_metrologie(
        r_brute,
        data.get("r_board_bas"),
        data.get("r_board_haut"),
        data.get("r_cable"),
        data.get("position_board", "milieu"),
    )
    r.r_offset_metrologie = r_offset
    if not metro_ok:
        r._erreur(msg_metro)
        _finaliser(r, data)
        return r
    if msg_metro:
        r.avertissements.append(msg_metro)
    if r_offset is not None:
        r.r_batterie_seule = r_mesure

    temp_corr = temperature if temperature is not None else 25.0
    r_corrigee = _corriger_resistance_thermique(r_mesure, temp_corr)
    r.r_corrigee = r_corrigee

    model = data.get("model", "")
    r_ref = float(REFERENCE_R_PAR_MODELE.get(model, SEUIL_FALLBACK_R_REF))
    r.r_ref = r_ref

    soh_r = round((r_ref / r_corrigee) * 100, 1) if r_corrigee > 0 else 0.0
    if not data.get("batterie_oem", True):
        soh_r = max(0.0, soh_r - PENALITE_NON_OEM)
    r.soh_resistance = soh_r

    if r_corrigee > SEUIL_FALLBACK_P97:
        r._refuser(
            f"Résistance interne trop élevée : {r_corrigee} mΩ "
            f"(seuil : {SEUIL_FALLBACK_P97} mΩ) — batterie très dégradée"
        )

    # ── Étape 5 : Cohérence cycles / résistance / capacité ───────────────────
    cycles = data.get("recharge_cycle")
    ratio_cap = r.ratio_capacite or 100.0
    coherence, msg_coherence = _verifier_coherence(ratio_cap, r_corrigee, r_ref, cycles)

    if coherence == "incoherent":
        r._refuser(msg_coherence)
    elif coherence == "suspect":
        r.avertissements.append(msg_coherence)
        if r.verdict == VALIDE:
            r.verdict = ERREUR
            r.motifs_refus.append("[ERREUR] " + msg_coherence)

    # ── Finalisation : score et durée de vie ──────────────────────────────────
    _finaliser(r, data)
    return r


def _finaliser(r: ResultatDiagnostic, data: dict):
    r.score_client, r.duree_vie_estimee = _calculer_score(
        r.ratio_capacite, r.soh_resistance, r.verdict
    )
