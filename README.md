# CashVolt — Diagnostic batterie

Système de diagnostic de batteries de smartphones reconditionnés.
Attribue un **grade** (A++ / A+ / A / B / C), une **décision** (vendable / à remplacer)
et une **durée de vie estimée**, puis génère les documents client.

**Architecture :** l'API Python **calcule** (cerveau, sans mémoire).
Bubble **stocke et affiche** (mémoire). L'**IMEI** relie tous les documents d'un téléphone.

---

## Fichiers du projet

### Algorithme + API (le cerveau — déployé sur Render)
| Fichier | Rôle |
|---|---|
| `main.py` | L'API (FastAPI) : endpoints `/diagnostic`, `/rapport`, `/stats` |
| `diagnostic.py` | Cœur du calcul : mesures, correction thermique, SoH, verdict |
| `grading.py` | Attribution du grade A++ / A+ / A / B / C |
| `metrology.py` | Isolation de la batterie : R_batterie = R_total − R_board − R_câble |
| `database.py` | Base auto-apprenante (P97 / P5) — optionnelle selon l'architecture |
| `generate_test_report.py` | Génération du rapport PDF (reportlab) |
| `requirements.txt` | Dépendances Python |
| `runtime.txt` | Force Python 3.12.7 (sinon Render échoue) |

### Documents client (gabarits HTML — charte CashVolt)
| Fichier | Rôle |
|---|---|
| `certificate_template_light.html` | Le certificat (façade) — grade, IMEI, bouton rapport |
| `rapport_detaille.html` | Le rapport détaillé (cible du bouton / lien) |
| `passeport_sante.html` | Le passeport santé (suivi annuel du téléphone) |
| `cashvolt_logo.jpg` | Logo carré CashVolt (déjà intégré en base64 dans les HTML) |

### Documentation
| Fichier | Rôle |
|---|---|
| `contrat_api_cashvolt.md` | Contrat d'échange entre l'API et Bubble (pour Mohamed) |
| `README.md` | Ce fichier |

---

## Déploiement (Render)

- **Build command :** `pip install -r requirements.txt`
- **Start command :** `uvicorn main:app --host 0.0.0.0 --port $PORT`
- **URL en ligne :** https://ismaila-w8ys.onrender.com
- Vérifier que c'est en ligne : ouvrir l'URL → doit afficher `{"status":"ok"}`

⚠️ Les noms de fichiers doivent être exacts (pas de ` (1)`, ` (2)` ajoutés par le navigateur).

---

## État d'avancement

- [x] Algorithme complet, déployé et en ligne
- [x] Bubble connecté à l'API (test → grade → décision → durée)
- [x] Certificat, rapport détaillé, passeport santé (gabarits HTML)
- [ ] Métrologie branchée avec les vraies données board (grades exacts)
- [ ] Les 3 documents reliés par IMEI dans Bubble
- [ ] Enrichissement marketing du certificat
