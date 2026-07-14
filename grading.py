"""
Grading CashVolt — attribution du grade, de la décision et de la durée de vie.

Échelle à 5 niveaux, validée par Roselyne (remplace un ancien système erroné
A/B/C/D) :
    A++ : origine constructeur, état excellent
    A+  : origine constructeur, bon état
    A   : compatible / neuve, correcte
    B   : sous le seuil de revente (NON vendue)
    C   : à remplacer (NON vendue)

Règle importante : A++ et A+ supposent une batterie d'ORIGINE (batterie_oem).
Une batterie compatible / de remplacement ne peut pas dépasser le grade A,
même si sa résistance est excellente — cette distinction est ce qui différencie
"origine constructeur" de "compatible" dans la légende du certificat.
"""

from dataclasses import dataclass

# Seuils de SoH (résistance), en pourcentage — à affiner avec les retours terrain
SEUIL_SOH_APP = 90   # A++
SEUIL_SOH_AP = 80    # A+
SEUIL_SOH_A = 65     # A
SEUIL_SOH_B = 40     # en dessous de B -> C

DUREE_APP = "3 ans"
DUREE_AP = "2,5 ans"
DUREE_A = "2 ans"
DUREE_NON_VENDUE = "—"


@dataclass
class Grade:
    lettre: str
    vendable: bool
    duree_estimee: str


def attribuer_grade(resultat, data):
    """
    resultat : objet renvoyé par diagnostic.lancer_diagnostic (avec .verdict, .soh_resistance)
    data     : dict des mesures parsées (parse_all), utilisé pour la règle "origine constructeur"
    """
    # Mesure non fiable / données manquantes -> à retester, aucune vente possible
    if getattr(resultat, "verdict", None) == "ERREUR":
        return Grade(lettre="À RETESTER", vendable=False, duree_estimee=DUREE_NON_VENDUE)

    soh = resultat.soh_resistance
    origine_constructeur = str(data.get("batterie_oem", "")).strip().lower() in ("oui", "yes", "true", "1")

    if soh >= SEUIL_SOH_APP and origine_constructeur:
        return Grade("A++", True, DUREE_APP)
    if soh >= SEUIL_SOH_AP and origine_constructeur:
        return Grade("A+", True, DUREE_AP)
    if soh >= SEUIL_SOH_A:
        # Batterie correcte : grade A, que ce soit d'origine ou compatible/neuve.
        # (Une batterie d'origine excellente mais sans confirmation OEM plafonne ici aussi.)
        return Grade("A", True, DUREE_A)
    if soh >= SEUIL_SOH_B:
        return Grade("B", False, DUREE_NON_VENDUE)
    return Grade("C", False, DUREE_NON_VENDUE)
