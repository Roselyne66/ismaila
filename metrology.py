"""
Métrologie CashVolt.

Principe : la résistance mesurée aux bornes du téléphone (R_total) contient
la résistance de la batterie ELLE-MÊME, plus celle du board électronique,
plus celle du câble de mesure. Pour juger la batterie équitablement, il faut
retirer board + câble :

    R_batterie = R_total − R_board − R_câble

Architecture retenue avec Bubble : la résistance du board (r_board) est déjà
calculée côté Bubble (page de calibration "Étape 3"), à partir de la position
de branchement utilisée. L'API reçoit donc directement r_board tout prêt et
fait l'unique soustraction — pour éviter que l'isolation de la batterie soit
dupliquée à deux endroits (règle explicite de Roselyne).

Un repli (interpolation r_board_bas / r_board_haut) reste disponible si jamais
r_board n'est pas fourni, pour ne pas bloquer un test en cas de données
manquantes — mais ce n'est plus le cas nominal.
"""

R_BATTERIE_MIN_PLAUSIBLE = 5.0   # en dessous, le résultat n'est pas physique (probable erreur de saisie)


def _interpoler_board(r_board_bas, r_board_haut, position):
    """Repli : interpole la résistance du board selon la position de branchement."""
    position = (position or "milieu").lower()
    if position in ("bas", "low"):
        return r_board_bas
    if position in ("haut", "high"):
        return r_board_haut
    # position "milieu" (ou inconnue) : moyenne des deux bornes
    return (r_board_bas + r_board_haut) / 2


def appliquer_metrologie(r_total, r_board_bas, r_board_haut, r_cable, position, r_board=None):
    """
    Renvoie un tuple (r_resultante, r_offset, message, ok).

    Trois cas, par ordre de priorité :
    1. r_board fourni (cas nominal — déjà calculé par Bubble) :
       on l'utilise directement, R_batterie = R_total − r_board − r_cable.
    2. r_board absent mais r_board_bas / r_board_haut fournis :
       repli par interpolation selon la position.
    3. Aucune donnée board : mesure brute utilisée + avertissement (démarrage,
       métrologie pas encore calibrée pour ce board).
    """
    if r_cable is None:
        r_cable = 0.0

    # ---- Cas 1 : résistance du board déjà calculée (cas nominal) ----
    if r_board is not None:
        r_offset = r_board + r_cable
        r_batterie = round(r_total - r_offset, 2)
        if r_batterie < R_BATTERIE_MIN_PLAUSIBLE:
            return (
                r_total, round(r_offset, 2),
                f"Résistance batterie isolée non physique ({r_batterie} mΩ) — "
                f"vérifier la métrologie du board ou refaire la mesure",
                False,
            )
        return (r_batterie, round(r_offset, 2), "", True)

    # ---- Cas 2 : repli par interpolation bas/haut ----
    if r_board_bas is not None and r_board_haut is not None:
        r_board_interp = _interpoler_board(r_board_bas, r_board_haut, position)
        r_offset = r_board_interp + r_cable
        r_batterie = round(r_total - r_offset, 2)
        if r_batterie < R_BATTERIE_MIN_PLAUSIBLE:
            return (
                r_total, round(r_offset, 2),
                f"Résistance batterie isolée non physique ({r_batterie} mΩ) — "
                f"vérifier la métrologie du board ou refaire la mesure",
                False,
            )
        return (r_batterie, round(r_offset, 2), "", True)

    # ---- Cas 3 : aucune métrologie disponible ----
    return (
        r_total, 0.0,
        "Métrologie board absente — mesure brute utilisée (à calibrer pour ce modèle de board)",
        True,
    )
