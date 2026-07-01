"""
main.py — API Cashvolt (à appeler depuis Bubble)

Deux points d'entrée :
  • POST /diagnostic  → renvoie le résultat en JSON (grade, durée, verdict, détails).
                        C'est CE QUE BUBBLE APPELLE pour afficher la note A++/A+/A.
  • POST /rapport     → renvoie le certificat PDF prêt à imprimer/envoyer.

Le corps de la requête (body) est le même dans les deux cas : le JSON des mesures
(model, tension, mesure_resistance, temperature, capacity, r_board_bas, etc.).

Lancement local :  uvicorn main:app --reload
"""

import tempfile
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from diagnostic import parse_all, lancer_diagnostic
from grading import attribuer_grade
from generate_test_report import generate_report_pdf
import database

app = FastAPI(title="Cashvolt API", version="1.0")

# Autorise Bubble (et tout client) à appeler l'API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def accueil():
    """Petit point de contrôle : permet de vérifier que l'API est en ligne."""
    return {"status": "ok", "service": "Cashvolt API"}


@app.post("/diagnostic")
async def diagnostic(request: Request):
    """
    Reçoit les mesures, renvoie le diagnostic complet en JSON.
    C'est l'appel principal pour Bubble (affichage du grade dans l'app).
    """
    payload = await request.json()

    data = parse_all(payload)
    resultat = lancer_diagnostic(data)
    grade = attribuer_grade(resultat, data)

    # Décision claire pour le technicien (au lieu d'un simple true/false).
    if grade.lettre == "À RETESTER":
        decision = "À RETESTER — mesure non fiable, refaire le test"
    elif grade.vendable:
        decision = "VENDABLE — le téléphone peut être vendu tel quel"
    else:
        decision = "À REMPLACER — changer la batterie avant de revendre le téléphone"

    # Enrichir la base : la mesure entre EN ATTENTE de validation (valide=0).
    # Elle ne sera prise en compte dans les seuils qu'après relecture du CEO.
    database.archiver_mesure(
        model=data.get("model", ""),
        r_batterie=resultat.r_corrigee,
        soh_resistance=resultat.soh_resistance,
        grade=grade.lettre,
        valide=0,
    )

    return JSONResponse({
        # Ce que la boutique affiche au client
        "grade": grade.lettre,
        "vendable": grade.vendable,
        "decision": decision,
        "duree_estimee": grade.duree_estimee,
        # Détails techniques (usage interne / debug)
        "verdict": resultat.verdict,
        "score_client": resultat.score_client,
        "soh_resistance": resultat.soh_resistance,
        "r_batterie_seule": resultat.r_batterie_seule,
        "r_offset_metrologie": resultat.r_offset_metrologie,
        "r_corrigee": resultat.r_corrigee,
        "ratio_capacite": resultat.ratio_capacite,
        "avertissements": resultat.avertissements,
        "motifs_refus": resultat.motifs_refus,
    })


@app.post("/rapport")
async def rapport(request: Request):
    """
    Reçoit les mesures, génère le certificat PDF et le renvoie.
    """
    payload = await request.json()

    # Fichier temporaire pour le PDF (nettoyé par l'OS).
    pdf_path = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
    generate_report_pdf(output_path=pdf_path, report_data=payload)

    nom_fichier = f"rapport_{payload.get('dossier_number', 'cashvolt')}.pdf"
    return FileResponse(pdf_path, filename=nom_fichier, media_type="application/pdf")


@app.get("/stats")
def stats():
    """Suivi de la base : mesures totales, validées, en attente."""
    return database.statistiques()


@app.post("/valider")
def valider():
    """
    Relecture du CEO : valide toutes les mesures en attente.
    À déclencher périodiquement (hebdomadaire puis quotidien) une fois les
    nouvelles mesures vérifiées. C'est le garde-fou anti-divergence.
    """
    n = database.valider_mesures()
    return {"mesures_validees": n, "stats": database.statistiques()}
