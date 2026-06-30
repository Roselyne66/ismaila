# Importation des modules nécessaires
from datetime import datetime, timedelta
import pytz
from os.path import exists
from pathlib import Path

from diagnostic import parse_all, lancer_diagnostic, VALIDE, A_REMPLACER, ERREUR
from grading import attribuer_grade


import uuid
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPDF

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def draw_label_value(pdf, x, y, label, value, label_width=55 * mm):
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(x, y, label)

    pdf.setFont("Helvetica", 10)
    pdf.drawString(x + label_width, y, str(value))


DEFAULT_REPORT_DATA = {
    "customer_name": "Sophie Martin",
    "customer_location": "Lyon, France",

    "erasure_provider": "Cashvolt Reconditionnement",
    "erasure_technician": "Nicolas Dujan",

    "abd_blanco_model": "Galaxy A14",
    "dossier_number": "DOS-2026-03-1048",
    "num_interne": "0092615",

    "start_time": "2026/03/10 13:05:12",
    "end_time": "2026/03/10 13:41:57",
    "statut": "batterie remplacee, tests OK, appareil certifie",

    "recharge_cycle": "12",
    "charge_level": "96%",
    "capacity": "4860 / 5000mAh",
    "temperature": "31 C",
    "tension": "4.21 V",
    "mesure_resistance": "148 mOhm",

    "manufacturer": "samsung",
    "chassis_type": "mobile device",
    "model": "SM-A145R",
    "market_name": "Galaxy A14 5G",
    "ram": "4GB",
    "imei_1": "356789102345678",
    "imei_2": "356789102345686",

    "report_uuid": "f326bd45-7d20-4a3b-96a5-41df0c3a9e52",
    "software_version": "cashvolt certification 1.1",
    "operator_name": "Nicolas Dujan",
}

from datetime import datetime
DEFAULT_REPORT_DATE = None  # Sera défini dynamiquement


def generate_report_pdf(output_path="rapport_test.pdf", report_data=None, report_date=None, logo_path=None):

    if report_data is None:
        report_data = DEFAULT_REPORT_DATA.copy()
    else:
        data = DEFAULT_REPORT_DATA.copy()
        data.update(report_data)
        # Toujours forcer software_version à 'cashvolt certification 1.1'
        data["software_version"] = "cashvolt certification 1.1"
        report_data = data

    # Générer dynamiquement un nouvel UUID pour chaque rapport
    report_data["report_uuid"] = str(uuid.uuid4())

    if report_date is None:
        # Utilise la date actuelle en France (Europe/Paris)
        paris_tz = pytz.timezone('Europe/Paris')
        report_date = datetime.now(paris_tz)

    if logo_path is None:
        default_logo = Path(__file__).with_name("CashVoltLogo.png")
        if default_logo.exists():
            logo_path = str(default_logo)

    # Date limite = date actuelle + 12 mois
    date_limit = report_date.replace(year=report_date.year + 1)
    data = report_data

    # Lancer le diagnostic batterie avant de générer le certificat
    parsed = parse_all(data)
    resultat = lancer_diagnostic(parsed)
    # Traduire le résultat technique en grade lettre (A++ / A+ / A / B / C)
    grade = attribuer_grade(resultat, parsed)

    pdf = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4

    margin_x = 18 * mm
    margin = 15 * mm

    y = height - 30 * mm

    logo_size = 40

    logo_svg_path = Path("CashVoltLogo.svg")

    # =========================
    # LOGO EN HAUT A DROITE
    # =========================

    if logo_svg_path.exists():
        drawing = svg2rlg(str(logo_svg_path))

        scale = logo_size / drawing.height
        drawing.scale(scale, scale)

        logo_width = drawing.width * scale

        logo_x = width - logo_width - margin
        logo_y = height - logo_size - margin

        renderPDF.draw(drawing, pdf, logo_x, logo_y)

    elif logo_path and exists(logo_path):

        logo_x = width - logo_size - margin
        logo_y = height - logo_size - margin

        pdf.drawImage(
            logo_path,
            logo_x,
            logo_y,
            width=logo_size,
            height=logo_size
        )

    # =========================
    # TITRE
    # =========================

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(margin_x, y, "Rapport de test")

    y -= 10 * mm

    # =========================
    # CUSTOMER DETAILS
    # =========================

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(margin_x, y, "Informations client")

    y -= 6 * mm

    draw_label_value(pdf, margin_x, y, "Nom du client :", data["customer_name"])
    y -= 5 * mm

    draw_label_value(pdf, margin_x, y, "Localisation client :", data["customer_location"])
    y -= 10 * mm

    # =========================
    # OPERATOR DETAILS
    # =========================

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(margin_x, y, "Informations opérateur")

    y -= 6 * mm

    draw_label_value(pdf, margin_x, y, "Prestataire :", data["erasure_provider"])
    y -= 5 * mm

    draw_label_value(pdf, margin_x, y, "Technicien :", data["erasure_technician"])
    y -= 10 * mm

    # =========================
    # CUSTOM FIELDS
    # =========================

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(margin_x, y, "Champs personnalisés")

    y -= 6 * mm

    draw_label_value(pdf, margin_x, y, "Modèle déclaré :", data["abd_blanco_model"])
    y -= 5 * mm

    draw_label_value(pdf, margin_x, y, "Numéro de dossier :", data["dossier_number"])
    y -= 5 * mm

    draw_label_value(pdf, margin_x, y, "Numéro interne :", data["num_interne"])
    y -= 10 * mm

    # =========================
    # PROCESS RESULTS
    # =========================

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(margin_x, y, "Résultats du processus")

    y -= 6 * mm

    draw_label_value(
        pdf,
        margin_x,
        y,
        "Début / Fin :",
        f"{data['start_time']} / {data['end_time']}"
    )

    y -= 5 * mm

    draw_label_value(pdf, margin_x, y, "Statut :", data["statut"])
    y -= 10 * mm

    # =========================
    # BATTERY CERTIFICATION
    # =========================

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(margin_x, y, "Informations de certification batterie")

    y -= 6 * mm

    draw_label_value(pdf, margin_x, y, "Cycles de charge :", data["recharge_cycle"])
    y -= 5 * mm

    draw_label_value(pdf, margin_x, y, "Niveau de charge :", data["charge_level"])
    y -= 5 * mm

    draw_label_value(pdf, margin_x, y, "Capacité :", data["capacity"])
    y -= 5 * mm

    draw_label_value(pdf, margin_x, y, "Température :", data["temperature"])
    y -= 5 * mm

    draw_label_value(pdf, margin_x, y, "Tension :", data["tension"])
    y -= 5 * mm

    draw_label_value(pdf, margin_x, y, "Résistance mesurée :", data["mesure_resistance"])
    y -= 10 * mm



    # =========================
    # HARDWARE DETAILS
    # =========================

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(margin_x, y, "Détails matériel")

    y -= 6 * mm

    draw_label_value(pdf, margin_x, y, "Fabricant :", data["manufacturer"])
    y -= 5 * mm

    draw_label_value(pdf, margin_x, y, "Type d'appareil :", data["chassis_type"])
    y -= 5 * mm

    draw_label_value(pdf, margin_x, y, "Modèle :", data["model"])
    y -= 5 * mm

    draw_label_value(pdf, margin_x, y, "Nom commercial :", data["market_name"])
    y -= 5 * mm

    draw_label_value(pdf, margin_x, y, "RAM :", data["ram"])
    y -= 5 * mm

    draw_label_value(pdf, margin_x, y, "IMEI :", data["imei_1"])
    y -= 5 * mm

    draw_label_value(pdf, margin_x, y, "IMEI 2 :", data["imei_2"])
    y -= 12 * mm

    # =========================
    # REPORT DETAILS
    # =========================

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(margin_x, y, "Détails du rapport")

    y -= 6 * mm

    draw_label_value(pdf, margin_x, y, "UUID du rapport :", data["report_uuid"])
    y -= 5 * mm

    draw_label_value(pdf, margin_x, y, "Date du rapport :", report_date.strftime("%Y-%m-%d %H:%M:%S"))
    y -= 5 * mm

    draw_label_value(pdf, margin_x, y, "Date limite :", date_limit.strftime("%Y-%m-%d %H:%M:%S"))
    y -= 5 * mm

    draw_label_value(pdf, margin_x, y, "Version logicielle :", data["software_version"])
    y -= 10 * mm

    # =========================
    # DIAGNOSTIC CASHVOLT (en bas, style simple)
    # =========================
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(margin_x, y, "Diagnostic Cashvolt")
    y -= 6 * mm
    pdf.setFont("Helvetica", 10)
    # Rapport client : on n'affiche QUE la lettre (pas le score sur 10),
    # pour ne pas embrouiller le consommateur.
    draw_label_value(pdf, margin_x, y, "Grade Cashvolt :", grade.lettre)
    y -= 5 * mm
    draw_label_value(pdf, margin_x, y, "Durée de vie estimée :", grade.duree_estimee)
    y -= 10 * mm

    # =========================
    # SIGNATURE
    # =========================

    pdf.line(margin_x, y, margin_x + 70 * mm, y)
    pdf.line(margin_x + 95 * mm, y, margin_x + 165 * mm, y)

    y -= 5 * mm

    pdf.setFont("Helvetica", 10)

    pdf.drawString(margin_x, y, "Opérateur (nom prénom)")
    pdf.drawString(margin_x + 95 * mm, y, "Tampon boutique")

    y -= 5 * mm

    pdf.drawString(margin_x, y, data["operator_name"])

    pdf.save()

    print(f"PDF genere: {output_path}")


if __name__ == "__main__":
    import sys, json
    if len(sys.argv) > 1:
        # Argument 1: chemin du fichier JSON
        with open(sys.argv[1], 'r', encoding='utf-8') as f:
            report_data = json.load(f)
        generate_report_pdf(report_data=report_data)
    else:
        generate_report_pdf()
