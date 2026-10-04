"""Composante IA locale de CorroborIA (scikit-learn, aucune donnée ne quitte la machine).

Rôle : trancher les écarts *ambigus* (Nature == 'heuristique') que les règles du mapping ne peuvent pas
décider seules, attribuer une confiance, prioriser les erreurs, regrouper les causes probables et
rédiger une explication à partir des facteurs réellement utilisés par le modèle.
Les verdicts des règles déterministes ne sont jamais modifiés (sauf correction d'un expert).
"""
import difflib
import re
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

BASE = Path(__file__).parent
OK, JUSTIFIE, ERREUR, REVUE = "OK", "ECART_JUSTIFIE", "ERREUR", "A_REVUE_HUMAINE"
LOW, HIGH = 0.35, 0.65  # zone d'incertitude -> revue humaine

# gravité métier par champ (0-1) pour la priorisation
SEVERITY = {"contractTypeCode": .9, "weeklyHoursOverride": .85, "dailyHoursOverride": .85, "detailedStatus": .9,
            "statusReasonCode": .8, "expectedReturnDate": .7, "Enregistrement": 1.0, "personId": 1.0,
            "divisionId": .8, "divisionCode": .7, "positionId": .8, "payGradeId": .75, "siteCode": .6,
            "siteName": .6, "assignmentStartDate": .55, "termStartDate": .5, "isPrimaryAssignment": .8,
            "isTemporaryAssignment": .8, "onboardDate": .5, "givenName": .4, "surname": .4,
            "positionName": .3, "divisionName": .3, "contactEmail": .3}

# poids du score de priorité (somme normalisée à 1 au calcul) : gravité du champ, confiance, récurrence du champ
WEIGHTS = {"gravite": .60, "confiance": .25, "recurrence": .15}


def priorite(df, weights=None, severity=None):
    """Score de priorité 0-100 des lignes ERREUR / A_REVUE_HUMAINE (0 ailleurs). Paramétrable sans réentraîner."""
    w = {**WEIGHTS, **(weights or {})}
    s = sum(w.values()) or 1.0
    sv = {**SEVERITY, **(severity or {})}
    n_same = df.groupby("Champ").Champ.transform("size")
    sev = df.Champ.map(sv).fillna(.5)
    score = 100 * (w["gravite"] * sev + w["confiance"] * df.Confiance.astype(float)
                   + w["recurrence"] * np.minimum(n_same, 5) / 5) / s
    out = pd.Series(0, index=df.index)
    mask = df.Statut.isin([ERREUR, REVUE])
    out[mask] = score[mask].round().clip(0, 100).astype(int)
    return out


FEATURES = ["sim", "len_ratio", "is_num", "rel_diff", "day_diff", "one_empty", "stable_map",
            "contains", "same_shape", "same_rep", "has_ref", "ref_match", "sev"]
LABELS = {"sim": "similarité des textes", "len_ratio": "ratio de longueur", "is_num": "valeur numérique",
          "rel_diff": "écart relatif", "day_diff": "écart en jours", "one_empty": "valeur vide d'un côté",
          "stable_map": "correspondance A→B stable dans tout le fichier", "contains": "une valeur contient l'autre",
          "same_shape": "même structure (lettres/chiffres)",
          "same_rep": "même motif interne de chiffres répétés (ex. code répété dans le libellé/courriel)",
          "has_ref": "valeur de référence secondaire disponible (détail du poste)",
          "ref_match": "B égale à la valeur de référence secondaire", "sev": "gravité du champ"}


# ---------------------------------------------------------------- features
def _shape(s):
    return re.sub(r"[A-Za-z]+", "a", re.sub(r"\d+", "9", str(s)))


def _eq(x, y):
    try:
        return float(x) == float(y)
    except (TypeError, ValueError):
        return str(x) == str(y)


def _rep(s):
    """1 si la valeur répète un code numérique en interne (ex. 3649-Empl3649, ...370370@)."""
    d = "".join(re.findall(r"\d", str(s)))
    tok = re.findall(r"\d{3,}", str(s))
    return int((len(d) >= 6 and d[-3:] == d[-6:-3]) or (len(tok) >= 2 and tok[0] == tok[-1]))


def feats(champ, a, b, stable, ref=None):
    has_ref = ref is not None and not pd.isna(ref)
    a, b = ("" if pd.isna(x) else str(x) for x in (a, b))
    f = dict(sim=difflib.SequenceMatcher(None, a, b).ratio(),
             len_ratio=min(len(a), len(b)) / max(len(a), len(b), 1),
             is_num=0, rel_diff=0.0, day_diff=0.0, one_empty=int(bool(a) != bool(b)),
             stable_map=int(stable), contains=int(bool(a and b) and (a in b or b in a)),
             same_shape=int(_shape(a) == _shape(b)), same_rep=int(_rep(a) == _rep(b) == 1),
             has_ref=int(has_ref), ref_match=int(has_ref and _eq(ref, b)), sev=SEVERITY.get(champ, .5))
    try:
        fa, fb = float(a), float(b)
        f["is_num"], f["rel_diff"] = 1, abs(fa - fb) / max(abs(fa), abs(fb), 1e-9)
    except ValueError:
        pass
    try:
        da, db = pd.Timestamp(a), pd.Timestamp(b)
        f["day_diff"] = abs((da - db).days)
    except (ValueError, TypeError):
        pass
    return f


def stable_map(df):
    """(champ, valeur A) -> True si la valeur A donne toujours la même valeur B (>=2 occurrences)."""
    g = df.groupby(["Champ", "ValeurSourceA"]).ValeurDestB.agg(["nunique", "size"])
    return {k: bool(r["nunique"] == 1 and r["size"] >= 2) for k, r in g.iterrows()}


# ---------------------------------------------------------------- entraînement
def synthetic(n=400, seed=0):
    """Cas synthétiques par perturbation, pour compléter un jeu réel très petit."""
    rng = np.random.default_rng(seed)
    r3 = lambda: str(int(rng.integers(100, 999)))
    rows = []
    for _ in range(n):
        c, c2, id1, id2 = (str(int(rng.integers(1000, 9999))) for _ in range(4))
        st = int(rng.random() < .3)
        ok = rng.random() < .5
        kind = rng.choice(["label", "email", "hours", "other"])
        ref = None
        if kind == "label":
            champ, a = "positionName", f"{c}-Empl{c}"
            b = f"{c2}-Empl{c2}" if ok else rng.choice([f"{c2}-Empl{c}", f"Empl{c2}", f"{c2}-Poste{r3()}"])
        elif kind == "email":
            champ, a = "contactEmail", f"PNom{id1}{id1[-3:]}@x.com"
            b = f"dev-08_PNom{id2}{id2[-3:]}@x.com" if ok else rng.choice(
                [f"dev-08_PNom{id2}{r3()}@x.com", f"Nom{id2}@x.com", f"dev-08_XNom{id2}{id2[-3:]}@y.org"])
        elif kind == "hours":
            champ, a = "weeklyHoursOverride", "(vide)"
            b = "40"
            ref = "40" if ok else str(rng.choice([35, 36, 37.5]))
        else:  # champs à règle nette (stables ou non) pour que le modèle voie aussi des vrais écarts
            champ = str(rng.choice(["siteName", "assignmentStartDate", "weeklyHoursOverride"]))
            if ok:
                a, b = ("2009-03-30", "2009-03-31") if champ == "assignmentStartDate" else ("40.0", "40")
            else:
                a, b = (("Emplacement48", "Emplacement35") if champ == "siteName" else
                        ("2009-03-30", "2022-10-05") if champ == "assignmentStartDate" else ("36.0", "40"))
        rows.append(dict(feats(champ, a, b, st, ref), y=JUSTIFIE if ok else ERREUR))
    return pd.DataFrame(rows)


def load_corrections():
    p = BASE / "corrections.csv"
    if p.exists() and p.stat().st_size > 0:
        return pd.read_csv(p, dtype={"Matricule": str})
    return pd.DataFrame(columns=["Matricule", "Champ", "Verdict"])


def train(df, X_all):
    """Entraîne sur les verdicts déterministes sûrs + cas synthétiques + corrections d'expert."""
    sure = df[(df.Nature == "règle") & df.Statut.isin([JUSTIFIE, ERREUR])]
    real = X_all.loc[sure.index].assign(y=sure.Statut)
    parts = [real, synthetic()]
    corr = load_corrections()
    if len(corr):
        m = df.assign(Matricule=df.Matricule.astype(str)).merge(corr, on=["Matricule", "Champ"], how="inner")
        for i in m.index:
            idx = df.index[(df.Matricule.astype(str) == m.Matricule[i]) & (df.Champ == m.Champ[i])]
            parts += [X_all.loc[idx].assign(y=m.Verdict[i])] * 20  # poids x20 aux corrections expertes
    data = pd.concat(parts, ignore_index=True)
    clf = RandomForestClassifier(n_estimators=200, max_depth=6, random_state=0, class_weight="balanced")
    clf.fit(data[FEATURES], data.y)
    return clf


# ---------------------------------------------------------------- explication
def explain(clf, x, p_err):
    imp = pd.Series(clf.feature_importances_, index=FEATURES)
    # facteurs les plus influents *et* non neutres pour ce cas
    top = (imp * (x[FEATURES].astype(float).abs() + .1)).sort_values(ascending=False).index[:3]
    fa = ", ".join(f"{LABELS[k]} = {x[k]:.2f}" for k in top)
    verdict = ERREUR if p_err >= HIGH else JUSTIFIE if p_err <= LOW else REVUE
    txt = {ERREUR: "probablement une vraie erreur", JUSTIFIE: "probablement un écart acceptable",
           REVUE: "cas incertain, à valider par un humain"}[verdict]
    return verdict, f"IA : {txt} (P(erreur) = {p_err:.0%}). Facteurs : {fa}."


# ---------------------------------------------------------------- pipeline
def enrich(df):
    df = df.copy().reset_index(drop=True)
    df[["ValeurSourceA", "ValeurDestB"]] = df[["ValeurSourceA", "ValeurDestB"]].astype(str)
    df["RefAlt"] = df.RefAlt.map(lambda v: None if pd.isna(v) else str(v))
    df["Source_verdict"] = "règle"
    df["Confiance"] = np.where(df.Statut == OK, 1.0, 1.0)
    df["Priorité"] = 0
    df["Cause_probable"] = ""
    stable = stable_map(df)
    gap = df[df.Statut != OK]
    X_all = pd.DataFrame([feats(r.Champ, r.ValeurSourceA, r.ValeurDestB,
                                stable.get((r.Champ, r.ValeurSourceA), False),
                                r.RefAlt) for r in gap.itertuples()],
                         index=gap.index)
    clf = train(df, X_all)

    # IA sur les cas ambigus
    amb = df[(df.Nature == "heuristique") & (df.Statut != OK)].index
    for i in amb:
        p_err = clf.predict_proba(X_all.loc[[i], FEATURES])[0][list(clf.classes_).index(ERREUR)]
        verdict, expl = explain(clf, X_all.loc[i], p_err)
        old = df.at[i, "Statut"]
        df.loc[i, ["Statut", "Source_verdict"]] = [verdict, "IA"]
        df.at[i, "Confiance"] = round(max(p_err, 1 - p_err), 2)
        df.at[i, "Explication"] = f"[règle initiale : {old}] {df.at[i,'Explication']} | {expl}"

    # corrections d'expert : priment sur tout
    corr = load_corrections()
    for r in corr.itertuples():
        m = (df.Matricule.astype(str) == str(r.Matricule)) & (df.Champ == r.Champ)
        df.loc[m, ["Statut", "Source_verdict", "Confiance"]] = [r.Verdict, "expert", 1.0]
        df.loc[m, "Explication"] += " | Verdict corrigé par un expert fonctionnel."

    # causes probables (regroupement des erreurs d'un même champ)
    err = df[df.Statut.isin([ERREUR, REVUE])]
    for champ, g in err.groupby("Champ"):
        vals = g.ValeurDestB.astype(str)
        if len(g) > 1 and vals.nunique() == 1:
            cause = f"B contient toujours « {vals.iloc[0]} » ({len(g)} lignes) : valeur par défaut probable"
        elif len(g) > 1:
            cause = f"{len(g)} écarts distincts sur {champ} : propagation incomplète probable"
        else:
            cause = "écart isolé"
        df.loc[g.index, "Cause_probable"] = cause

    df["Priorité"] = priorite(df)

    return df
