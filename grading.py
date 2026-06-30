"""
grading.py — Système de notation par lettres Cashvolt (A++ / A+ / A / B / C)

Ce module se branche PAR-DESSUS le diagnostic existant (diagnostic.py).
Il ne recalcule rien : il traduit les sorties de ResultatDiagnostic
en une note commerciale lisible par le client.

Flux : lancer_diagnostic(data) → ResultatDiagnostic → attribuer_grade(resultat, data) → Grade

Version 1 (brouillon) — TOUS les seuils et durées ci-dessous sont à valider
avec Roselyne. Ils sont volontairement centralisés en haut du fichier pour
pouvoir être ajustés sans toucher à la logique.
"""

from diagnostic import VALIDE, A_REMPLACER, ERREUR


# ─────────────────────────────────────────────────────────────────────────────
# SEUILS D'ATTRIBUTION — à ajuster avec Roselyne
# ─────────────────────────────────────────────────────────────────────────────

SEUIL_SOH_CONSTRUCTEUR_A2P = 90.0   # % SOH constructeur minimum pour viser A++
SEUIL_SOH_R_A2P            = 90.0   # % SoH résistance minimum pour A++
SEUIL_SOH_R_AP             = 85.0   # % SoH résistance minimum pour A+
SEUIL_SOH_R_A              = 80.0   # % SoH résistance minimum pour A (batterie non d'origine)


# ─────────────────────────────────────────────────────────────────────────────
# DURÉES DE VIE PAR GRADE — Roselyne a proposé 2 jeux de valeurs en réunion.
# On bascule de l'un à l'autre en changeant la ligne DUREE_PAR_GRADE plus bas.
# ─────────────────────────────────────────────────────────────────────────────

DUREE_OPTIMISTE = {"A++": "3 ans",  "A+": "2,5 ans", "A": "2 ans"}
DUREE_PRUDENTE  = {"A++": "2 ans",  "A+": "1,5 an",  "A": "1 an"}

# ← Choisir ici le jeu de durées actif :
DUREE_PAR_GRADE = DUREE_OPTIMISTE


# ─────────────────────────────────────────────────────────────────────────────
# OBJET RETOURNÉ
# ─────────────────────────────────────────────────────────────────────────────

class Grade:
    def __init__(self, lettre, vendable, duree_estimee, explication):
        self.lettre = lettre              # "A++", "A+", "A", "B", "C", "À RETESTER"
        self.vendable = vendable          # True si la boutique peut revendre
        self.duree_estimee = duree_estimee
        self.explication = explication    # phrase courte (usage interne / formation)

    def __repr__(self):
        return f"<Grade {self.lettre} vendable={self.vendable} duree={self.duree_estimee}>"


# ─────────────────────────────────────────────────────────────────────────────
# FONCTION PRINCIPALE
# ─────────────────────────────────────────────────────────────────────────────

def attribuer_grade(resultat, data: dict) -> Grade:
    """
    Traduit un ResultatDiagnostic en grade lettre.
    `resultat` : objet renvoyé par lancer_diagnostic()
    `data`     : dict renvoyé par parse_all() (pour batterie_oem et soh_constructeur)
    Les conditions sont testées dans l'ordre : la première vraie l'emporte.
    """

    # 1. Mesure non fiable → on ne note pas, on demande un nouveau test.
    if resultat.verdict == ERREUR:
        return Grade("À RETESTER", False, "—",
                     "Mesure non fiable — refaire le test")

    # 2. Batterie à remplacer (capacité/tension KO, dépasse le seuil P97,
    #    BMS incohérent...) → C, jamais revendue.
    if resultat.verdict == A_REMPLACER:
        return Grade("C", False, "—",
                     "Batterie à remplacer avant toute revente")

    # ── À partir d'ici, le verdict est VALIDE ───────────────────────────────
    soh_r            = resultat.soh_resistance or 0.0
    oem              = data.get("batterie_oem", True)      # True = batterie d'origine
    soh_constructeur = data.get("soh_constructeur")        # peut être None si non lu

    # 3. A++ — le haut du panier : d'origine, excellente résistance,
    #    ET SOH constructeur confirmé ≥ 90 %.
    if (oem
            and soh_r >= SEUIL_SOH_R_A2P
            and soh_constructeur is not None
            and soh_constructeur >= SEUIL_SOH_CONSTRUCTEUR_A2P):
        return Grade("A++", True, DUREE_PAR_GRADE["A++"],
                     "Batterie d'origine, état excellent, SOH constructeur confirmé")

    # 4. A+ — d'origine, très bon état résistance.
    #    (cas où le SOH constructeur n'est pas lisible : on plafonne ici.)
    if oem and soh_r >= SEUIL_SOH_R_AP:
        return Grade("A+", True, DUREE_PAR_GRADE["A+"],
                     "Batterie d'origine, bon état")

    # 5. A — batterie non d'origine (neuve ou compatible) mais résistance correcte.
    if soh_r >= SEUIL_SOH_R_A:
        return Grade("A", True, DUREE_PAR_GRADE["A"],
                     "Batterie compatible ou neuve, résistance correcte")

    # 6. B — valide mais sous les seuils de revente : gardé en interne, pas vendu.
    return Grade("B", False, "—",
                 "État correct mais sous le seuil de revente Cashvolt")
