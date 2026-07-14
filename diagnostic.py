"""
diagnostic.py — cœur du calcul CashVolt.

Pipeline :
  1. parse_all()        : lit et nettoie les mesures brutes envoyées par Bubble
  2. lancer_diagnostic() : corrige la température, applique la métrologie,
                            calcule le SoH (State of Health) et le verdict

Rien n'est mémorisé ici : l'API est un pur calculateur (voir contrat_api_cashvolt.md).
"""

import re
from dataclasses import dataclass, field
from typing import Optional, List

from metrology import appliquer_metrologie

TEMPERATURE_REFERENCE = 25.0   # °C — température à laquelle les seuils sont calibrés
COEFF_THERMIQUE = 0.006        # correction empirique ~0.6%/°C — à affiner avec les retours terrain

R_EXCELLENT = 40.0   # mΩ — résistance batterie isolée à partir de laquelle SoH ≈ 100%
R_LIMITE = 200.0     # mΩ — résistance à partir de laquelle SoH ≈ 0%


def _parse_float(valeur):
    """Convertit une valeur (str/num/None) en float, sans lever d'exception."""
    if valeur is None or valeur == "":
        return None
    try:
        return float(str(valeur).replace(",", ".").strip())
    except (ValueError, TypeError):
        return None


def _parse_capacite(valeur):
    """
    Lit un champ capacité du type "3200 / 3279mAh" (mesurée / nominale)
    ou une simple valeur numérique. Renvoie (mesuree, nominale) ou (valeur, None).
    """
    if valeur is None:
        return None, None
    texte = str(valeur)
    match = re.search(r"([\d.,]+)\s*/\s*([\d.,]+)", texte)
    if match:
        mesuree = _parse_float(match.group(1))
        nominale = _parse_float(match.group(2))
        return mesuree, nominale
    seule = re.search(r"([\d.,]+)", texte)
    if seule:
        return _parse_float(seule.group(1)), None
    return None, None


def parse_all(payload: dict) -> dict:
    """Lit et normalise toutes les mesures envoyées par Bubble."""
    capacite_mesuree, capacite_nominale = _parse_capacite(payload.get("capacity"))

    return {
        "imei": payload.get("imei"),
        "model": payload.get("model", ""),
        "tension": _parse_float(payload.get("tension")),
        "mesure_resistance": _parse_float(payload.get("mesure_resistance")),
        "temperature": _parse_float(payload.get("temperature")),
        "capacite_mesuree": capacite_mesuree,
        "capacite_nominale": capacite_nominale,
        "batterie_oem": payload.get("batterie_oem"),
        "soh_constructeur": _parse_float(payload.get("soh_constructeur")),
        "nombre_cycles": _parse_float(payload.get("nombre_cycles") or payload.get("cycles")),
        # Métrologie : r_board = résistance du board déjà calculée côté Bubble (cas nominal).
        "r_board": _parse_float(payload.get("r_board")),
        "r_board_bas": _parse_float(payload.get("r_board_bas")),
        "r_board_haut": _parse_float(payload.get("r_board_haut")),
        "r_cable": _parse_float(payload.get("r_cable")),
        "position_board": payload.get("position_board", "milieu"),
    }


@dataclass
class ResultatDiagnostic:
    verdict: str = "VALIDE"
    r_brute: Optional[float] = None
    r_corrigee: Optional[float] = None          # après correction thermique + métrologie (= batterie isolée)
    r_batterie_seule: Optional[float] = None     # alias explicite du même résultat
    r_offset_metrologie: float = 0.0
    soh_resistance: Optional[float] = None
    ratio_capacite: Optional[float] = None
    avertissements: List[str] = field(default_factory=list)
    motifs_refus: List[str] = field(default_factory=list)


def _corriger_temperature(r_mesuree, temperature):
    """Ramène la résistance mesurée à la température de référence (25°C).
    Une batterie froide affiche une résistance plus haute qu'en réalité."""
    if temperature is None:
        return r_mesuree
    ecart = temperature - TEMPERATURE_REFERENCE
    facteur = 1 + COEFF_THERMIQUE * ecart
    if facteur <= 0:
        return r_mesuree
    return r_mesuree / facteur


def lancer_diagnostic(data: dict) -> ResultatDiagnostic:
    """Exécute le pipeline complet et renvoie un ResultatDiagnostic."""
    resultat = ResultatDiagnostic()

    # ---- Étape 1 : vérifier les données indispensables ----
    if data.get("tension") is None or data.get("mesure_resistance") is None:
        resultat.verdict = "ERREUR"
        resultat.motifs_refus.append(
            "Aucune tension ou résistance lue — effectuer le réveil (10s en charge) puis ressaisir"
        )
        return resultat

    resultat.r_brute = data["mesure_resistance"]

    # ---- Étape 2 : correction thermique ----
    r_thermo = _corriger_temperature(data["mesure_resistance"], data.get("temperature"))

    # ---- Étape 3 : métrologie (isolation de la batterie) ----
    r_isolee, offset, message_metro, metro_ok = appliquer_metrologie(
        r_thermo,
        data.get("r_board_bas"),
        data.get("r_board_haut"),
        data.get("r_cable"),
        data.get("position_board", "milieu"),
        r_board=data.get("r_board"),
    )
    resultat.r_offset_metrologie = offset
    if message_metro:
        resultat.avertissements.append(message_metro)
    if not metro_ok:
        resultat.verdict = "ERREUR"
        resultat.motifs_refus.append(message_metro)
        return resultat

    resultat.r_corrigee = round(r_isolee, 2)
    resultat.r_batterie_seule = resultat.r_corrigee

    # ---- Étape 4 : SoH basé sur la résistance isolée ----
    soh = 100 * (1 - (resultat.r_corrigee - R_EXCELLENT) / (R_LIMITE - R_EXCELLENT))
    resultat.soh_resistance = round(max(0.0, min(100.0, soh)), 1)

    # ---- Étape 5 : ratio de capacité (information complémentaire) ----
    if data.get("capacite_mesuree") is not None and data.get("capacite_nominale"):
        resultat.ratio_capacite = round(
            100 * data["capacite_mesuree"] / data["capacite_nominale"], 1
        )
        # Avertissement si la capacité mesurée diverge fortement du SoH résistance
        if abs(resultat.ratio_capacite - resultat.soh_resistance) > 20:
            resultat.avertissements.append(
                "Écart important entre le SoH (résistance) et le ratio de capacité — vérifier la mesure"
            )

    return resultat
