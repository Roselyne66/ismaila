"""
metrology.py — Isolation de la résistance de la batterie seule.

Quand on mesure avec le téléphone, le résistimètre voit tout ce qui est EN SÉRIE :
    R_total = R_batterie + R_board + R_câble

Les résistances en série s'additionnent ; pour noter la batterie il faut donc
soustraire le board et le câble. Ce module fait cette soustraction.

Deux points clés (expliqués par Roselyne) :
  • Le board dépend de la POSITION de branchement (haut / milieu / bas).
    C'est linéaire : R_board(milieu) = moyenne de R_board(haut) et R_board(bas).
  • Le câble est quasi-constant (calibré ~1 fois par mois en métrologie).

Les valeurs R_board_haut, R_board_bas, R_câble et la position viennent de la
brique métrologie de Mohamed (côté Bubble) ; ce module ne fait que les consommer.
"""

# Seuil de plausibilité APRÈS soustraction : une batterie seule descend
# rarement sous ~5 mΩ. En dessous, c'est que la métrologie est fausse ou que
# la mesure est mauvaise → on signale une erreur plutôt que de noter à tort.
R_BATTERIE_MIN_PLAUSIBLE = 5.0   # mΩ

# Correspondance position texte → ratio 0..1 (0 = bas, 1 = haut)
POSITIONS = {"bas": 0.0, "milieu": 0.5, "haut": 1.0}


def position_vers_ratio(position) -> float:
    """
    Convertit une position en ratio entre 0 (bas) et 1 (haut).
    Accepte soit un texte ('haut'/'milieu'/'bas'), soit un nombre déjà entre 0 et 1.
    Valeur inconnue → 0.5 (milieu), choix neutre par défaut.
    """
    if isinstance(position, (int, float)):
        return max(0.0, min(1.0, float(position)))
    return POSITIONS.get(str(position).strip().lower(), 0.5)


def calculer_r_board(r_board_bas: float, r_board_haut: float, position) -> float:
    """
    Interpolation linéaire du board selon la position de branchement.
    Exemple : bas=8 mΩ, haut=13 mΩ, position=milieu → 10,5 mΩ.
    """
    ratio = position_vers_ratio(position)
    return r_board_bas + ratio * (r_board_haut - r_board_bas)


def appliquer_metrologie(r_total, r_board_bas, r_board_haut, r_cable, position):
    """
    Renvoie un tuple (r_resultante, r_offset, message, ok).

    • Si la métrologie est complète :
        r_resultante = R_batterie seule = R_total − R_board(position) − R_câble
        ok = True  (sauf si le résultat est non physique → ok = False + erreur)
    • Si la métrologie est absente (phase de démarrage) :
        r_resultante = R_total (mesure brute, non corrigée)
        ok = True, mais message d'avertissement pour signaler la calibration manquante.
    """
    # Câble manquant → on le considère négligeable (0) plutôt que de bloquer.
    if r_cable is None:
        r_cable = 0.0

    metrologie_complete = (r_board_bas is not None and r_board_haut is not None)

    # ── Cas démarrage : pas encore de métrologie pour ce board ──────────────
    if not metrologie_complete:
        return (
            r_total,
            None,
            "Métrologie board absente — mesure brute utilisée "
            "(à calibrer pour ce modèle de board)",
            True,
        )

    # ── Cas normal : on isole la batterie ───────────────────────────────────
    r_board = calculer_r_board(r_board_bas, r_board_haut, position)
    r_offset = r_board + r_cable
    r_batterie = round(r_total - r_offset, 2)

    if r_batterie < R_BATTERIE_MIN_PLAUSIBLE:
        return (
            r_total,
            round(r_offset, 2),
            f"Résistance batterie isolée non physique ({r_batterie} mΩ) — "
            f"vérifier la métrologie du board ou refaire la mesure",
            False,
        )

    return (r_batterie, round(r_offset, 2), "", True)
