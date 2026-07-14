"""
generate_test_report.py — génère un rapport PDF simple en français.

Utilisé par l'endpoint /rapport de main.py. Reste volontairement sobre :
les documents "riches" (certificat, rapport détaillé, passeport) sont des
gabarits HTML gérés côté Bubble (cf. certificat_bubble.html, rapport_detaille.html).
"""

from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def generer_pdf(data: dict, resultat, grade) -> bytes:
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    largeur, hauteur = A4

    y = hauteur - 30 * mm
    c.setFont("Helvetica-Bold", 16)
    c.drawString(20 * mm, y, "CashVolt — Rapport de test batterie")
    y -= 12 * mm

    c.setFont("Helvetica", 11)
    lignes = [
        f"Modèle : {data.get('model', '—')}",
        f"IMEI : {data.get('imei', '—')}",
        f"Grade : {grade.lettre}",
        f"Décision : {'VENDABLE' if grade.vendable else 'À REMPLACER'}",
        f"Durée de vie estimée : {grade.duree_estimee}",
        "",
        f"Résistance mesurée (brute) : {resultat.r_brute} mΩ",
        f"Résistance batterie isolée : {resultat.r_corrigee} mΩ",
        f"SoH (résistance) : {resultat.soh_resistance} %",
        f"Ratio de capacité : {resultat.ratio_capacite if resultat.ratio_capacite is not None else '—'} %",
        f"Tension : {data.get('tension', '—')} V",
        f"Température : {data.get('temperature', '—')} °C",
    ]
    for ligne in lignes:
        c.drawString(20 * mm, y, ligne)
        y -= 7 * mm

    if resultat.avertissements:
        y -= 4 * mm
        c.setFont("Helvetica-Oblique", 9)
        for avert in resultat.avertissements:
            c.drawString(20 * mm, y, f"⚠ {avert}")
            y -= 5 * mm

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.read()
