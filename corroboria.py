"""CorroborIA - modèle v1 : détection des écarts Système A (RH) -> Système B (Temps).

Pour chaque champ mappé :  valeur attendue (règles métier) vs valeur réelle en B
  -> OK | ECART_JUSTIFIE (règle métier / artefact connu) | ERREUR (à investiguer)
Chaque décision est accompagnée d'une explication.

Usage : python corroboria.py   ->  rapport_corroboration.xlsx
"""
import re
import unicodedata
from pathlib import Path


import pandas as pd

import ia

BASE = Path(__file__).parent
DATA = BASE / "data"        # extractions fournies + mapping (lecture seule)
OUT = BASE / "outputs"      # rapports générés
OK, JUSTIFIE, ERREUR = "OK", "ECART_JUSTIFIE", "ERREUR"

CONTRACT = {"T": "KELH", "O": "WHX", "M": "CEGQ", "R": "CNZC", "J": "RMQ", "Z": "JAW", "Q": "TRSY"}


# ---------------------------------------------------------------- chargement
def load(files=None):
    """files : dict optionnel {source, destination, motif, detail} -> chemin ou fichier téléversé."""
    f = {"source": DATA / "Employe_Source_Anonymise_VF.xlsx",
         "destination": DATA / "Employe_Destination_Anonymise_VF.xlsx",
         "motif": DATA / "Motif de la situation d'emploi.xlsx",
         "detail": DATA / "détail_du_poste.xlsx", **(files or {})}
    src = pd.read_excel(f["source"])
    dst = pd.read_excel(f["destination"]).dropna(axis=1, how="all")
    for col in ("statusReasonCode", "expectedReturnDate"):  # colonnes vides si personne n'est absent
        if col not in dst:
            dst[col] = pd.NA
    dst["expectedReturnDate"] = pd.to_datetime(dst["expectedReturnDate"])
    motif = pd.read_excel(f["motif"])
    raw = pd.read_excel(f["detail"])
    col = raw.columns[0]
    names = col.split(",")
    det = pd.DataFrame([str(v).split(",") for v in raw[col]], columns=names)
    det = det.apply(pd.to_numeric, errors="coerce")
    det["Date"] = pd.to_datetime(det["DateEffetAffectation"], unit="D", origin="1899-12-30")
    return src, dst, motif, det


# ---------------------------------------------------------------- règles
# La règle « min(DateEntréePoste, date d'effet de l'unité adm.) » du mapping donne, sur l'échantillon, des
# dates antérieures pour 100 % des lignes (dates du détail du poste incohérentes) : désactivée par défaut,
# on compare à DateEntréePoste et on journalise la valeur de la règle pour revue.
USE_DETAIL_MIN = False


def same(e, a):
    try:
        return float(e) == float(a)
    except (TypeError, ValueError):
        return str(e) == str(a)

def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", str(s)) if unicodedata.category(c) != "Mn")


def fix_mojibake(s):
    try:
        return str(s).encode("cp1252").decode("utf-8")
    except Exception:
        return str(s)


def type_flags(t):
    return {"P": (True, False), "A": (False, True), "S": (False, False)}[t]


def contract_code(r):
    c = r.CatégorieEmploi
    if c == "V":
        perm, ft = r.EstPermanent == "Oui", r.EstTempsPlein == "Oui"
        if perm and ft:
            return "JWN"
        if perm and not ft:
            return "XFLR"
        return None
    return CONTRACT.get(c)


def unit_effective_date(det, poste, direction):
    """Date à laquelle l'unité administrative courante est devenue applicable pour ce poste."""
    h = det[det.IdentifiantPoste == poste].sort_values("Date")
    if h.empty:
        return None
    cur = h[h.CodeDirectionAffectee == direction] if "CodeDirectionAffectee" in h else h
    col = "CodeDirectionAffectée"
    changes = h[h[col] != h[col].shift()]
    hit = changes[changes[col] == direction]
    if hit.empty:
        return h.Date.min()
    return hit.Date.iloc[-1] if len(changes) > 1 else h.Date.min()


# ---------------------------------------------------------------- moteur
def run(files=None):
    src, dst, motif, det = load(files)
    mot = motif.set_index("CodeCatégorieStatut")
    findings = []

    def add(pid, emploi, typ, champ, a, b, statut, regle, expl, ref=None):
        # écarts que les règles seules ne tranchent pas : confiés à la composante IA (ia.py)
        heur = champ in ("contactEmail", "positionName") or (champ.endswith("HoursOverride") and a == "(vide)")
        findings.append(dict(Matricule=pid, CodeEmploi=emploi, TypeAffectation=typ, Champ=champ,
                             ValeurSourceA=a, ValeurDestB=b, Statut=statut, Règle=regle, Explication=expl, RefAlt=ref,
                             Nature="heuristique" if heur else "règle"))

    def cmp(r, d, champ, exp, act, regle, ok_expl="Valeurs conformes", justify=None):
        e, a = ("" if pd.isna(x) else x for x in (exp, act))
        if same(e, a):
            statut, expl = OK, ok_expl
        elif justify and justify(e, a):
            statut, expl = JUSTIFIE, justify(e, a)
        else:
            statut, expl = ERREUR, f"Valeur attendue « {e} », trouvée « {a} »"
        add(r.Matricule, r.CodeEmploi, r.TypeAffectation, champ, e, a, statut, regle, expl)

    used = set()
    for _, r in src.iterrows():
        isP, isT = type_flags(r.TypeAffectation)
        cand = dst[(dst.personId == r.Matricule) & (dst.positionId == r.CodeEmploi) & ~dst.index.isin(used)]
        exact = cand[(cand.isPrimaryAssignment == isP) & (cand.isTemporaryAssignment == isT)]
        if exact.empty:
            exact = cand[cand.assignmentStartDate == r.DateEntréePoste]  # type erroné mais même affectation
        if exact.empty:
            add(r.Matricule, r.CodeEmploi, r.TypeAffectation, "Enregistrement", "présent", "absent", ERREUR,
                "Complétude", f"Affectation {r.TypeAffectation} (poste {r.CodePoste}) absente du système B")
            continue
        d = exact.iloc[0]
        used.add(exact.index[0])

        # identité
        cmp(r, d, "personId", r.Matricule, d.personId, "Matricule = personId")
        cmp(r, d, "givenName", strip_accents(r.PrénomUsuel), d.givenName, "Prénom sans accents")
        cmp(r, d, "surname", strip_accents(r.NomFamille), d.surname, "Nom sans accents")

        # courriel : 1re lettre prénom + nom + 3 derniers chiffres du code + @loto-quebec.com
        m = re.match(r"^(dev-[\w-]+_)?([A-Za-z]+)(\d+)@loto-quebec\.com$", str(d.contactEmail))
        theo = f"{strip_accents(r.PrénomUsuel)[0]}{strip_accents(r.NomFamille)}{str(r.Matricule)[-3:]}@loto-quebec.com"
        if str(d.contactEmail) == theo:
            st, ex = OK, "Courriel conforme à la règle"
        elif m and m.group(3)[-3:] == m.group(3)[-6:-3] and m.group(2)[0] == str(r.PrénomUsuel)[0]:
            st, ex = JUSTIFIE, ("Gabarit respecté (initiale + nom + 3 derniers chiffres) mais préfixe "
                                "d'environnement de dév. et nom anonymisé différent : artefact de non-production")
        else:
            st, ex = ERREUR, f"Courriel ne respecte pas le gabarit attendu ({theo})"
        add(r.Matricule, r.CodeEmploi, r.TypeAffectation, "contactEmail", theo, d.contactEmail, st, "Gabarit courriel", ex)

        cmp(r, d, "onboardDate", r.DateEmbaucheRécente.date(), pd.to_datetime(d.onboardDate).date(), "Date d'embauche")

        # emplacement / structure
        cmp(r, d, "siteCode", r.CodeSite, d.siteCode, "CodeSite")
        cmp(r, d, "siteName", r.LibelléSite, d.siteName, "LibelléSite")
        cmp(r, d, "divisionId", r.CodeDirection, d.divisionId, "CodeDirection = divisionId")
        cmp(r, d, "divisionCode", r.CodeImputation, d.divisionCode, "CodeImputation = divisionCode")
        cmp(r, d, "divisionName", f"{r.CodeDirection:05d}-{r.LibelléDirection}", d.divisionName,
            "Concaténation unité adm. + '-' + description")
        cmp(r, d, "positionId", r.CodeEmploi, d.positionId, "CodeEmploi = positionId")
        cmp(r, d, "positionCode", r.CodeEmploi, d.positionCode, "CodeEmploi = positionCode")
        cmp(r, d, "payGradeId", r.ÉchelleSalariale, d.payGradeId, "ÉchelleSalariale = payGradeId")

        # nom du rôle (anonymisation : on tolère si la correspondance emploi->nom est stable en B)
        exp_name = f"{r.CodeEmploi}-{r.IntituléEmploi}"
        stable = dst[dst.positionId == r.CodeEmploi].positionName.nunique() == 1
        cmp(r, d, "positionName", exp_name, d.positionName, "Concaténation emploi + '-' + description",
            justify=lambda e, a: ("Libellé différent mais correspondance emploi→nom stable dans tout B : "
                                  "probable artefact d'anonymisation, à confirmer") if stable else None)

        # type de contrat
        cmp(r, d, "contractTypeCode", contract_code(r), d.contractTypeCode, "Règle type d'employé (PERM/FT/EMPTP)")

        # affectation
        cmp(r, d, "isPrimaryAssignment", isP, d.isPrimaryAssignment, "P = primaire")
        cmp(r, d, "isTemporaryAssignment", isT, d.isTemporaryAssignment, "A = temporaire ; S = ni l'un ni l'autre")

        # dates d'affectation : min(DateEntréePoste, date d'effet de l'unité administrative)
        ud = unit_effective_date(det, r.CodePoste, r.CodeDirection)
        exp_start = min(r.DateEntréePoste, ud) if (USE_DETAIL_MIN and ud is not None) else r.DateEntréePoste
        note = "" if USE_DETAIL_MIN else f" (règle min du détail du poste désactivée ; valeur règle = {ud.date() if ud is not None else 'n/a'})"
        cmp(r, d, "assignmentStartDate", exp_start.date(), pd.to_datetime(d.assignmentStartDate).date(),
            "Date la plus ancienne entre DateEntréePoste et date d'effet de l'unité adm." + note)
        cmp(r, d, "termStartDate", exp_start.date(), pd.to_datetime(d.termStartDate).date(),
            "Date d'effet du détail du poste" + note)

        # heures : source, sinon repli sur détail du poste
        hw, hd = r.HeuresNormeHebdo, r.HeuresNormeQuotidienne
        for champ, v, dv, dcol in (("weeklyHoursOverride", hw, d.weeklyHoursOverride, "HeuresSemaineContrat"),
                                   ("dailyHoursOverride", hd, d.dailyHoursOverride, "HeuresJourContrat")):
            if pd.isna(v):
                alt = det[det.IdentifiantPoste == r.CodePoste][dcol].dropna()
                alt = alt.iloc[-1] if len(alt) else None
                add(r.Matricule, r.CodeEmploi, r.TypeAffectation, champ, "(vide)", dv,
                    JUSTIFIE if alt is not None and alt == dv else ERREUR, "Heures norme poste",
                    f"Source vide ; détail du poste = {alt}" + (" : valeur reprise du détail" if alt == dv else ""),
                    ref=alt)
            else:
                cmp(r, d, champ, v, dv, "Heures norme poste")

        # situation d'emploi
        absent = r.CodeSuspensionAccès in (2, 3, 6, 7)
        exp_status = "Absence complète" if absent else "Actif"
        cmp(r, d, "detailedStatus", exp_status, fix_mojibake(d.detailedStatus), "Règle situation d'emploi (accès)")
        if fix_mojibake(d.detailedStatus) != d.detailedStatus:
            add(r.Matricule, r.CodeEmploi, r.TypeAffectation, "detailedStatus (encodage)", exp_status, d.detailedStatus,
                JUSTIFIE, "Encodage", "Libellé en UTF-8 mal décodé (Ã¨ = è) : valeur correcte, défaut d'encodage")
        if r.CodeRaisonStatut in mot.index:
            ext = mot.loc[r.CodeRaisonStatut, "CodeStatutSystèmeExterne"]
            gest = mot.loc[r.CodeRaisonStatut, "CodeGestionAccès"]
            if gest != r.CodeSuspensionAccès:
                add(r.Matricule, r.CodeEmploi, r.TypeAffectation, "CodeSuspensionAccès", gest, r.CodeSuspensionAccès,
                    ERREUR, "Cohérence motif", "Code de gestion des accès du motif ≠ code dans l'extraction source")
        else:
            ext = None
        cmp(r, d, "statusReasonCode", ext if absent else None, d.statusReasonCode,
            "Code Remphor via motif, seulement si absence complète")
        cmp(r, d, "expectedReturnDate", r.DateRetourAnticipée.date() if absent and pd.notna(r.DateRetourAnticipée) else None,
            d.expectedReturnDate.date() if pd.notna(d.expectedReturnDate) else None,
            "DateRetourAnticipée seulement si absence complète")

    # enregistrements en trop dans B
    for i, d in dst[~dst.index.isin(used)].iterrows():
        add(d.personId, d.positionId, "?", "Enregistrement", "absent", "présent", ERREUR, "Complétude",
            "Enregistrement présent en B sans équivalent en source A")

    return pd.DataFrame(findings)


GLOSSARY_CODES = [
    ("OK", "Valeurs conformes à la règle du mapping"),
    ("ECART_JUSTIFIE", "Valeurs différentes mais expliquées par une règle métier ou un artefact connu"),
    ("ERREUR", "Vraie anomalie à investiguer"),
    ("A_REVUE_HUMAINE", "Cas ambigu : le modèle n'est pas assez sûr, un humain tranche"),
    ("règle / IA / expert", "Origine du verdict : règle déterministe, modèle scikit-learn local, ou correction d'un expert"),
    ("P / A / S", "Type d'affectation : Primaire / temporAire / Secondaire"),
    ("JWN", "Permanent temps plein (PERM_IND=1, FT_IND=1, EMPTP_CD=V)"),
    ("XFLR", "Permanent temps partiel (PERM_IND=1, FT_IND=0, EMPTP_CD=V)"),
    ("KELH", "Surnuméraire avec vacances (T)"), ("WHX", "Occasionnel – surnuméraire (O)"),
    ("CEGQ", "Occasionnel avec avantages (M)"), ("CNZC", "Surnuméraire avec avantages (R)"),
    ("RMQ", "Saisonnier (J)"), ("JAW", "Aspirant croupier (Z)"), ("TRSY", "Stagiaire (Q)"),
    ("Actif", "Code de traitement des accès 00 ou 01"),
    ("Absence complète", "Codes 02, 03, 06, 07 : le code Remphor du motif et la date de retour sont alors transmis"),
]


def glossary_fields():
    """Table des champs corroborés, lue directement dans Mapping.xlsx."""
    m = pd.read_excel(DATA / "Mapping.xlsx", sheet_name=0)
    m.columns = ["Description", "Champ système A", "Champ système B", "Règle"]
    m = m.dropna(subset=["Champ système B"]).copy()
    m["Règle"] = m["Règle"].fillna("Copie directe").astype(str).str.replace("\n", " ", regex=False)
    return m.reset_index(drop=True)


def to_excel_bytes(df):
    import io
    buf = io.BytesIO()
    write_sheets(df, buf)
    return buf.getvalue()


def report(df):
    OUT.mkdir(exist_ok=True)
    out = OUT / "rapport_corroboration.xlsx"
    try:
        out.open("ab").close()
    except PermissionError:  # fichier ouvert dans Excel
        out = OUT / f"rapport_corroboration_{pd.Timestamp.now():%H%M%S}.xlsx"
        print(f"(rapport habituel verrouillé, écriture dans {out.name})")
    write_sheets(df, out)
    tot = df.Statut.value_counts()
    print(f"{len(df)} contrôles : {tot.get(OK,0)} OK, {tot.get(JUSTIFIE,0)} écarts justifiés, "
          f"{tot.get(ERREUR,0)} erreurs à investiguer, {tot.get('A_REVUE_HUMAINE',0)} à revue humaine")
    print(df[df.Statut == ERREUR].sort_values("Priorité", ascending=False)[
        ["Priorité", "Matricule", "Champ", "ValeurSourceA", "ValeurDestB", "Source_verdict", "Cause_probable"]
    ].to_string(index=False))


def write_sheets(df, out):
    resume = (df.groupby(["Champ", "Statut"]).size().unstack(fill_value=0)
                .reindex(columns=[OK, JUSTIFIE, ERREUR], fill_value=0))
    erreurs = df[df.Statut == ERREUR].sort_values("Priorité", ascending=False)
    revue = df[df.Statut == "A_REVUE_HUMAINE"].sort_values("Priorité", ascending=False)
    with pd.ExcelWriter(out) as xw:
        erreurs.to_excel(xw, sheet_name="Erreurs à investiguer", index=False)
        revue.to_excel(xw, sheet_name="À revue humaine", index=False)
        df[df.Statut == JUSTIFIE].to_excel(xw, sheet_name="Écarts justifiés", index=False)
        resume.to_excel(xw, sheet_name="Résumé par champ")
        df.to_excel(xw, sheet_name="Détail complet", index=False)
        for ws in xw.book.worksheets:
            for c in ws.columns:
                ws.column_dimensions[c[0].column_letter].width = min(60, max(len(str(x.value or "")) for x in c) + 2)


if __name__ == "__main__":
    report(ia.enrich(run()))
