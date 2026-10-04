"""Retours d'experts : journal des corrections de verdict et règles apprises.

Un expert fonctionnel corrige un verdict (statut) ; la correction est gardée dans un journal (`corrections.csv`) avec son
motif, son commentaire, son auteur et sa date. Elle sert de trois façons :
  1. elle remplace le verdict de la ligne corrigée (origine « expert ») ;
  2. elle enrichit l'entraînement du modèle local (poids élevé) ;
  3. quand SEUIL_REGLE corrections concordantes (même champ, même « forme » de valeurs A et B, même verdict, aucun
     contre-exemple) existent, une **règle est proposée** à l'expert, qui la valide ou la rejette. Une règle validée est
     stockée dans `regles_apprises.json` et appliquée par le moteur (origine « règle apprise »), distincte des règles
     du mapping. Rien n'est jamais appliqué automatiquement sans validation.
"""
import json
import re
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent   # racine du projet
JOURNAL = BASE / "corrections.csv"
REGLES = BASE / "regles_apprises.json"
SEUIL_REGLE = 3  # nombre minimal de corrections concordantes pour proposer une règle
COLS = ["Matricule", "Champ", "Verdict", "Motif", "Commentaire", "Auteur", "Date", "ValeurA", "ValeurB", "Regle",
        "AncienVerdict"]
MOTIFS = ["artefact_anonymisation", "donnee_source_erronee", "regle_trop_stricte", "erreur_confirmee", "autre"]
VERDICTS = ("ERREUR", "ECART_JUSTIFIE")


# ---------------------------------------------------------------- journal des corrections
def lire_journal():
    """Journal complet (toutes les lignes, y compris les annulations) ; compatible avec l'ancien format à 3 colonnes."""
    if JOURNAL.exists() and JOURNAL.stat().st_size > 0:
        d = pd.read_csv(JOURNAL, dtype=str, keep_default_na=False)
    else:
        d = pd.DataFrame(columns=COLS)
    for c in COLS:
        if c not in d.columns:
            d[c] = ""
    return d[COLS]


def ajouter(matricule, champ, verdict, motif="", commentaire="", auteur="", valeur_a="", valeur_b="", regle="", ancien=""):
    """Ajoute une correction au journal (historique conservé : on n'efface jamais une ligne)."""
    ligne = {"Matricule": str(matricule), "Champ": champ, "Verdict": verdict, "Motif": motif, "Commentaire": commentaire,
             "Auteur": auteur, "Date": datetime.now().strftime("%Y-%m-%d %H:%M"), "ValeurA": str(valeur_a),
             "ValeurB": str(valeur_b), "Regle": regle, "AncienVerdict": ancien}
    pd.concat([lire_journal(), pd.DataFrame([ligne])], ignore_index=True).to_csv(JOURNAL, index=False, encoding="utf-8")


def annuler(matricule, champ, auteur=""):
    """Annule la dernière correction d'une ligne (ajoute une ligne « ANNULE », l'historique reste)."""
    ajouter(matricule, champ, "ANNULE", commentaire="correction annulée", auteur=auteur)


def corrections_effectives():
    """Dernière correction par (Matricule, Champ), annulations retirées : c'est ce que le moteur applique."""
    d = lire_journal()
    d = d.drop_duplicates(["Matricule", "Champ"], keep="last")
    return d[d.Verdict.isin(VERDICTS)].reset_index(drop=True)


# ---------------------------------------------------------------- règles apprises
def forme(valeur):
    """« Forme » d'une valeur : les suites de chiffres deviennent # (« dev-08-v2_PNom123@x.com » -> « dev-#-v#_PNom#@x.com »)."""
    return re.sub(r"\d+", "#", str(valeur).strip())


def signature(champ, a, b):
    return (str(champ), forme(a), forme(b))


def regles():
    try:
        return json.loads(REGLES.read_text(encoding="utf-8"))
    except Exception:
        return []


def _ecrire_regles(liste):
    REGLES.write_text(json.dumps(liste, ensure_ascii=False, indent=1), encoding="utf-8")


def regles_actives():
    return [r for r in regles() if r["statut"] == "active"]


def propositions():
    """Règles proposées : au moins SEUIL_REGLE corrections concordantes, aucun contre-exemple, pas déjà traitées."""
    corr = corrections_effectives()
    corr = corr[(corr.ValeurA != "") | (corr.ValeurB != "")]
    if corr.empty:
        return []
    corr = corr.assign(sig=[signature(c, a, b) for c, a, b in zip(corr.Champ, corr.ValeurA, corr.ValeurB)])
    deja = {(r["champ"], r["forme_a"], r["forme_b"]) for r in regles()}  # active, rejetée ou désactivée
    sortie = []
    for sig, g in corr.groupby("sig"):
        verdicts = set(g.Verdict)
        if len(verdicts) != 1 or len(g) < SEUIL_REGLE or sig in deja:
            continue  # verdicts contradictoires = pas de règle
        sortie.append({"champ": sig[0], "forme_a": sig[1], "forme_b": sig[2], "verdict": verdicts.pop(), "n": len(g),
                       "exemples": list(g.Matricule.head(5))})
    return sorted(sortie, key=lambda p: -p["n"])


def _enregistrer(prop, statut, auteur):
    liste = regles()
    liste.append({"id": uuid.uuid4().hex[:8], "champ": prop["champ"], "forme_a": prop["forme_a"], "forme_b": prop["forme_b"],
                  "verdict": prop["verdict"], "n": prop["n"], "exemples": prop.get("exemples", []), "statut": statut,
                  "date": datetime.now().strftime("%Y-%m-%d %H:%M"), "auteur": auteur})
    _ecrire_regles(liste)


def valider(prop, auteur=""):
    _enregistrer(prop, "active", auteur)


def rejeter(prop, auteur=""):
    _enregistrer(prop, "rejetee", auteur)


def desactiver(id_regle, auteur=""):
    liste = regles()
    for r in liste:
        if r["id"] == id_regle:
            r["statut"], r["auteur"], r["date"] = "desactivee", auteur, datetime.now().strftime("%Y-%m-%d %H:%M")
    _ecrire_regles(liste)


def appliquer_regles(df):
    """Applique les règles apprises actives aux écarts (jamais aux conformes). Les corrections d'expert passent ensuite par-dessus."""
    fa, fb = df.ValeurSourceA.map(forme), df.ValeurDestB.map(forme)
    for r in regles_actives():
        m = (df.Champ == r["champ"]) & (fa == r["forme_a"]) & (fb == r["forme_b"]) & (df.Statut != "OK")
        df.loc[m, ["Statut", "Source_verdict", "Confiance"]] = [r["verdict"], "règle apprise", 1.0]
        df.loc[m, "Explication"] += f" | Règle apprise ({r['n']} corrections d'experts concordantes)."
    return df
