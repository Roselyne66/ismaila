# Contrat d'API CashVolt — Algo (Python) ⇄ Bubble

Décision d'architecture : **Bubble stocke tout, l'API Python calcule seulement.**
- L'API est le **cerveau** : elle reçoit des mesures, renvoie un diagnostic. Elle ne mémorise rien.
- Bubble est la **mémoire** : il stocke chaque contrôle par IMEI, garde l'historique, génère les documents (certificat, rapport, passeport).

L'**IMEI** est la clé qui relie tout : un téléphone = un IMEI = un historique de contrôles.

---

## 1. Bubble → API : lancer un diagnostic

**Appel :** `POST https://ismaila-w8ys.onrender.com/diagnostic`
**En-tête :** `Content-Type: application/json`

**Corps (ce que Bubble envoie) :**

| Champ | Exemple | Obligatoire |
|---|---|---|
| `imei` | "355468981234567" | oui (clé de suivi) |
| `model` | "iPhone15,4" | oui |
| `tension` | "4.21" | oui |
| `mesure_resistance` | "56" (mΩ, résistance totale mesurée) | oui |
| `temperature` | "25" (°C) | oui |
| `capacity` | "3200 / 3279mAh" (mesurée / nominale) | recommandé |
| `batterie_oem` | "oui" / "non" | recommandé |
| `soh_constructeur` | "95" (%) | optionnel (pour A++) |
| `r_board_bas` | "8" (mΩ) | optionnel (métrologie) |
| `r_board_haut` | "13" (mΩ) | optionnel (métrologie) |
| `r_cable` | "4" (mΩ) | optionnel (métrologie) |
| `position_board` | "haut" / "milieu" / "bas" | optionnel (métrologie) |

---

## 2. API → Bubble : le résultat

**Réponse JSON (ce que Bubble reçoit et STOCKE, rattaché à l'IMEI) :**

| Champ | Exemple | Usage |
|---|---|---|
| `grade` | "A+" | affiché au client |
| `decision` | "VENDABLE — le téléphone peut être vendu tel quel" | guide le technicien |
| `vendable` | true / false | logique boutique |
| `duree_estimee` | "2,5 ans" | affiché au client |
| `verdict` | "VALIDE" | interne |
| `soh_resistance` | 98.2 | interne |
| `r_batterie_seule` | 55.5 | interne (métrologie) |
| `r_offset_metrologie` | 14.5 | interne |
| `r_corrigee` | 55.5 | interne |
| `ratio_capacite` | 97.6 | interne |
| `motifs_refus` | [ ... ] | raisons d'un refus |

**Action Bubble après réception :** créer un enregistrement « Contrôle » lié à l'IMEI,
avec la date, le grade, la décision, la durée, et les détails. C'est cet enregistrement
qui alimente l'historique et le passeport.

---

## 3. Les documents (générés par Bubble à partir de ses données)

Les 3 gabarits HTML sont fournis (charte CashVolt, police Poppins, logo intégré) :

- **certificate_template_light.html** — le certificat (façade). Bubble injecte : grade, IMEI, modèle, capacité, durée, décision, N° certificat, + le lien du bouton « rapport détaillé ».
- **rapport_detaille.html** — le rapport détaillé (cible du bouton). Bubble injecte toutes les mesures du contrôle.
- **passeport_sante.html** — le passeport (suivi). Bubble le remplit à partir de **tous les contrôles de l'IMEI** stockés dans sa base : dernier contrôle, prochain conseillé, et l'historique année par année.

Bubble remplace les valeurs via les `id` présents dans chaque gabarit
(ex. `id="val-grade"`, `id="d-imei"`, `id="p-grade"`, etc.).

---

## 4. Point à décider ensemble : l'auto-apprentissage (P97 / P5)

La base auto-apprenante de Roselyne (« ça s'auto-apprend ») a besoin de l'historique
des mesures pour affiner ses seuils. Comme l'API ne stocke plus rien :

- **Option courte (v1)** : l'API utilise des seuils fixes (P97 = 350 mΩ, références constructeur).
  Simple, fonctionne tout de suite.
- **Option complète (plus tard)** : Bubble renvoie à l'API les statistiques (percentiles) calculées
  sur sa base, ou l'API interroge la Data API de Bubble.

À trancher — non bloquant pour démarrer.

---

## 5. Récap des actions

**Mohamed (Bubble) :**
1. Ajouter `imei` dans l'appel `/diagnostic`.
2. Stocker le résultat comme un « Contrôle » lié à l'IMEI.
3. Générer les 3 documents à partir des données stockées.
4. Page passeport : afficher tous les contrôles d'un IMEI.

**Ismaila (API) :**
1. L'API `/diagnostic` est prête (calcul stateless).
2. Fournir les 3 gabarits HTML.
3. (Plus tard) brancher l'auto-apprentissage si on choisit l'option complète.
