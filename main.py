"""
main.py — API CashVolt.

Endpoints :
  GET  /            -> statut de l'API
  POST /diagnostic   -> calcule grade, décision, durée de vie à partir des mesures
  POST /rapport       -> génère un PDF simple du test
  GET  /stats         -> suivi interne de la base d'apprentissage (facultatif)

Rappel d'architecture : cette API est un pur CALCULATEUR, sans mémoire
côté certificats/historique — c'est Bubble qui stocke tout (voir
contrat_api_cashvolt.md). La base locale (database.py) ne sert qu'à affiner
les seuils de grading en interne.
"""

from fastapi import FastAPI
from fastapi.responses import Response
import uvicorn

import database
from diagnostic import parse_all, lancer_diagnostic
from grading import attribuer_grade
from generate_test_report import generer_pdf

app = FastAPI(title="Cashvolt API", version="1.0")


@app.get("/")
def accueil():
    return {"status": "ok"}


@app.post("/diagnostic")
def diagnostic(payload: dict):
    data = parse_all(payload)
    resultat = lancer_diagnostic(data)
    grade = attribuer_grade(resultat, data)

    # Décision claire pour le technicien (au lieu d'un simple true/false)
    if grade.lettre == "À RETESTER":
        decision = "À RETESTER — mesure non fiable, refaire le test"
    elif grade.vendable:
        decision = "VENDABLE — le téléphone peut être vendu tel quel"
    else:
        decision = "À REMPLACER — changer la batterie avant de revendre le téléphone"

    # Archivage optionnel (apprentissage des seuils uniquement — pas l'historique client)
    database.archiver_mesure(
        model=data.get("model", ""),
        r_batterie=resultat.r_corrigee,
        soh_resistance=resultat.soh_resistance,
        grade=grade.lettre,
        valide=0,
        imei=data.get("imei"),
    )

    return {
        "grade": grade.lettre,
        "vendable": grade.vendable,
        "decision": decision,
        "duree_estimee": grade.duree_estimee,
        "verdict": resultat.verdict,
        "soh_resistance": resultat.soh_resistance,
        "r_batterie_seule": resultat.r_batterie_seule,
        "r_offset_metrologie": resultat.r_offset_metrologie,
        "r_corrigee": resultat.r_corrigee,
        "ratio_capacite": resultat.ratio_capacite,
        "avertissements": resultat.avertissements,
        "motifs_refus": resultat.motifs_refus,
    }


@app.post("/rapport")
def rapport(payload: dict):
    data = parse_all(payload)
    resultat = lancer_diagnostic(data)
    grade = attribuer_grade(resultat, data)
    pdf_bytes = generer_pdf(data, resultat, grade)
    return Response(content=pdf_bytes, media_type="application/pdf")


@app.get("/stats")
def stats():
    """Suivi de la base d'apprentissage : mesures totales, validées, en attente."""
    return database.statistiques()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
