"""CorroborIA - modèle v1 : détection des écarts Système A (RH) -> Système B (Temps).

Pour chaque champ mappé :  valeur attendue (règles métier) vs valeur réelle en B
  -> OK | ECART_JUSTIFIE (règle métier / artefact connu) | ERREUR (à investiguer)
Chaque décision est accompagnée d'une explication.

Usage : python source/corroboria.py   ->  rapport_corroboration.xlsx
"""
import re
import unicodedata
from pathlib import Path


import pandas as pd

import ia

BASE = Path(__file__).resolve().parent.parent   # racine du projet
DATA = BASE / "data"        # extractions fournies + mapping (lecture seule)
OUT = BASE / "outputs"      # rapports générés
OK, JUSTIFIE, ERREUR = "OK", "ECART_JUSTIFIE", "ERREUR"

CONTRACT = {"T": "KELH", "O": "WHX", "M": "CEGQ", "R": "CNZC", "J": "RMQ", "Z": "JAW", "Q": "TRSY"}


# ---------------------------------------------------------------- chargement
COLONNES_REQUISES = {
    "source": ["Matricule", "NomFamille", "PrénomUsuel", "DateEmbaucheRécente", "TypeAffectation", "DateEntréePoste", "CodeEmploi",
               "IntituléEmploi", "ÉchelleSalariale", "CodeImputation", "CodeDirection", "LibelléDirection", "CodeSite", "LibelléSite",
               "CatégorieEmploi", "EstPermanent", "EstTempsPlein", "CodeStatutEmploi", "CodeSuspensionAccès", "HeuresNormeHebdo",
               "HeuresNormeQuotidienne"],
    "destination": ["personId", "givenName", "surname", "contactEmail", "onboardDate", "contractTypeCode", "detailedStatus", "siteCode",
                    "siteName", "divisionId", "divisionCode", "divisionName", "positionId", "positionName", "positionCode", "payGradeId",
                    "assignmentStartDate", "weeklyHoursOverride", "dailyHoursOverride"],
    "motif": ["CodeCatégorieStatut", "CodeStatutSystèmeExterne", "CodeGestionAccès"],
}
NOMS_FICHIERS = {"source": "système A - RH (source)", "destination": "système B - Temps (cible)",
                 "motif": "motifs de la situation d'emploi", "detail": "détail du poste"}


COLONNES_DATES_B = ("onboardDate", "assignmentStartDate", "expectedReturnDate", "termStartDate")


def _lire_table(fichier, dates=True):
    """Excel (.xlsx) ou CSV (séparateur détecté, UTF-8 ou Windows-1252) -> DataFrame (dates converties pour un CSV)."""
    if str(getattr(fichier, "name", fichier)).lower().endswith(".csv"):
        for enc in ("utf-8-sig", "cp1252"):
            try:
                if hasattr(fichier, "seek"):
                    fichier.seek(0)
                d = pd.read_csv(fichier, sep=None, engine="python", encoding=enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ValueError("encodage non reconnu")
        if dates:  # un CSV n'a pas de types : on retrouve les colonnes de dates comme dans un classeur Excel
            for col in d.columns:
                if str(col).startswith("Date") or col in COLONNES_DATES_B:
                    d[col] = pd.to_datetime(d[col], errors="coerce")
        return d
    return pd.read_excel(fichier)


def _lire(fichier, cle):
    """Lit un fichier Excel ou CSV ; message clair (en français) si le fichier est illisible ou n'est pas la bonne extraction."""
    try:
        d = _lire_table(fichier, cle != "detail")
    except Exception as e:
        raise ValueError(f"Impossible de lire le fichier « {NOMS_FICHIERS[cle]} » : ce n'est pas un classeur Excel (.xlsx) ni un CSV valide ({e}).") from e
    manque = [x for x in COLONNES_REQUISES.get(cle, []) if x not in d.columns and not (cle == "destination" and d[x].isna().all() if x in d.columns else False)]
    if manque:
        raise ValueError(f"Le fichier « {NOMS_FICHIERS[cle]} » n'a pas les colonnes attendues : {', '.join(manque[:8])}"
                         f"{'…' if len(manque) > 8 else ''}. Vérifie que tu as chargé la bonne extraction à cet emplacement.")
    return d


def load(files=None):
    """files : dict optionnel {source, destination, motif, detail} -> chemin ou fichier téléversé."""
    f = {"source": DATA / "Employe_Source_Anonymise_VF.xlsx",
         "destination": DATA / "Employe_Destination_Anonymise_VF.xlsx",
         "motif": DATA / "Motif de la situation d'emploi.xlsx",
         "detail": DATA / "détail_du_poste.xlsx", **(files or {})}
    src = _lire(f["source"], "source")
    dst = _lire(f["destination"], "destination").dropna(axis=1, how="all")
    for col in ("statusReasonCode", "expectedReturnDate", "assignmentEndDate", "termEndDate"):  # colonnes vides si aucune date de fin / personne absent
        if col not in dst:
            dst[col] = pd.NA
    for col in ("expectedReturnDate", "assignmentEndDate", "termEndDate"):
        dst[col] = pd.to_datetime(dst[col])
    motif = _lire(f["motif"], "motif")
    raw = _lire(f["detail"], "detail")
    col = raw.columns[0]
    names = col.split(",")
    if "DateEffetAffectation" in raw.columns:      # CSV déjà découpé en colonnes
        det = raw.copy()
    elif "DateEffetAffectation" in names:          # Excel : une seule colonne contenant des valeurs séparées par des virgules
        det = pd.DataFrame([str(v).split(",") for v in raw[col]], columns=names)
    else:
        raise ValueError(f"Le fichier « {NOMS_FICHIERS['detail']} » n'a pas la colonne attendue « DateEffetAffectation ». "
                         "Vérifie que tu as chargé la bonne extraction à cet emplacement.")
    det = det.apply(pd.to_numeric, errors="coerce")
    det["Date"] = pd.to_datetime(det["DateEffetAffectation"], unit="D", origin="1899-12-30")
    return src, dst, motif, det


# ---------------------------------------------------------------- règles
# Dates de début : le champ source (DateEntréePoste) est la date d'effet du poste UNIQUEMENT ; le champ destination inclut
# la règle transformée du mapping (date d'effet du poste combinée à celle du détail du poste). Sur l'échantillon, la valeur
# de B vaut toujours soit DateEntréePoste, soit la date d'effet du détail le plus récent quand elle est postérieure :
# la règle appliquée ici est donc « la plus récente entre DateEntréePoste et la date d'effet du dernier détail du poste »
# (hypothèse déduite des données, à faire confirmer : le mapping parle de « la plus ancienne »).



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


def date_regle_debut(det, poste, debut):
    """Date de début transformée par la règle du mapping : la plus récente entre DateEntréePoste et la date d'effet du
    dernier détail du poste (DateEntréePoste seule si le poste n'a aucun détail)."""
    h = det[det.IdentifiantPoste == poste]
    return max(pd.Timestamp(debut), h.Date.max()).date() if len(h) else pd.Timestamp(debut).date()


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


def fin_unite_adm(det, poste, debut):
    """Fin de l'unité administrative courante (règle de date de fin du mapping).

    Détail du poste « courant » = celui en vigueur au début de l'affectation (dernier détail dont la date d'effet est antérieure ou égale).
    La fin = date d'effet du détail SUIVANT - 1 jour, seulement si ce détail a un code d'unité administrative différent ;
    sinon (aucun détail suivant, ou même unité) : aucune date de fin (None)."""
    h = det[det.IdentifiantPoste == poste].sort_values("Date").reset_index(drop=True)
    if h.empty:
        return None
    col = "CodeDirectionAffectée"
    avant = h[h.Date <= pd.Timestamp(debut)]
    i = int(avant.index[-1]) if len(avant) else 0
    if i + 1 >= len(h) or h[col][i + 1] == h[col][i]:
        return None
    return (h.Date[i + 1] - pd.Timedelta(days=1)).date()


def date_fin_attendue(det, r):
    """Date de fin attendue : la plus ancienne entre DateSortiePoste (système A) et la fin de l'unité administrative ; None si aucune."""
    fin = fin_unite_adm(det, r.CodePoste, r.DateEntréePoste)
    sortie = None if pd.isna(r.DateSortiePoste) else pd.Timestamp(r.DateSortiePoste).date()
    dates = [x for x in (sortie, fin) if x is not None]
    return min(dates) if dates else None


REGLE_DEBUT = "{champ} : source = date d'effet du poste (DateEntréePoste) ; B = règle transformée (la plus récente entre DateEntréePoste et la date d'effet du dernier détail du poste)"
REGLE_FIN = "la plus ancienne entre DateSortiePoste et la fin de l'unité adm. (date d'effet du détail suivant - 1 jour si l'unité change ; sinon aucune)"


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

        # dates de début : source = date d'effet du poste seulement ; B = règle transformée (voir date_regle_debut)
        debut = pd.Timestamp(r.DateEntréePoste).date()
        regle_d = date_regle_debut(det, r.CodePoste, r.DateEntréePoste)
        just = lambda e, a: ("B reflète la règle transformée (date d'effet du dernier détail du poste, postérieure à DateEntréePoste)"
                             if a == regle_d else None)
        cmp(r, d, "assignmentStartDate", debut, pd.to_datetime(d.assignmentStartDate).date(),
            REGLE_DEBUT.format(champ="Date de début d'affectation"), justify=just)
        cmp(r, d, "termStartDate", debut, pd.to_datetime(d.termStartDate).date(),
            REGLE_DEBUT.format(champ="Date d'effet du détail du poste"), justify=just)

        # dates de fin d'affectation et de détail du poste (souvent vides : « vide » attendu = « vide » trouvé)
        fin = date_fin_attendue(det, r)
        for champ, regle in (("assignmentEndDate", "Date d'expiration du poste : " + REGLE_FIN),
                             ("termEndDate", "Date de fin du détail du poste (même règle) : " + REGLE_FIN)):
            cmp(r, d, champ, fin, pd.to_datetime(d[champ]).date() if pd.notna(d[champ]) else None, regle,
                ok_expl="Valeurs conformes (aucune date de fin attendue)" if fin is None else "Valeurs conformes")

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
    ("A_REVUE_HUMAINE", "Cas à relire : confiance sous le seuil ou modèle pas assez sûr, un humain tranche"),
    ("Écart justifié (100 % des données)", "Application : champ dont toutes les lignes (au moins 3) sont des écarts justifiés, par ex. contactEmail ou positionName (artefacts de non-production / anonymisation)"),
    ("À relire (écart justifié) / (vraie anomalie)", "Application : « À relire » est scindé selon le verdict dont la ligne est issue (écart justifié ou vraie anomalie)"),
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
          f"{tot.get(ERREUR,0)} erreurs à investiguer, {tot.get('A_REVUE_HUMAINE',0)} à relire")
    print(df[df.Statut == ERREUR].sort_values("Priorité", ascending=False)[
        ["Priorité", "Matricule", "Champ", "ValeurSourceA", "ValeurDestB", "Source_verdict", "Cause_probable"]
    ].to_string(index=False))


REVUES_STATUTS = ("A_REVUE_HUMAINE", "A_REVUE_JUSTIFIE", "A_REVUE_ERREUR")   # « À relire » (l'application le scinde en deux)
JUSTIFIES_STATUTS = (JUSTIFIE, "ECART_SYSTEMATIQUE")                          # écarts justifiés, dont ceux présents sur 100 % du champ


def write_sheets(df, out):
    """Classeur du rapport : erreurs, à relire, écarts justifiés, résumé par champ, détail complet.
    Accepte les statuts du moteur et ceux de l'application (À relire scindé, écart justifié sur 100 % des données)."""
    base = df.Statut.map(lambda s: "A_REVUE_HUMAINE" if s in REVUES_STATUTS else JUSTIFIE if s in JUSTIFIES_STATUTS else s)
    resume = (df.groupby([df.Champ, base.rename("Statut")]).size().unstack(fill_value=0)
                .reindex(columns=[OK, JUSTIFIE, ERREUR], fill_value=0))
    erreurs = df[df.Statut == ERREUR].sort_values("Priorité", ascending=False)
    revue = df[df.Statut.isin(REVUES_STATUTS)].sort_values("Priorité", ascending=False)
    with pd.ExcelWriter(out) as xw:
        erreurs.to_excel(xw, sheet_name="Erreurs à investiguer", index=False)
        revue.to_excel(xw, sheet_name="À relire", index=False)
        df[df.Statut.isin(JUSTIFIES_STATUTS)].to_excel(xw, sheet_name="Écarts justifiés", index=False)
        resume.to_excel(xw, sheet_name="Résumé par champ")
        df.to_excel(xw, sheet_name="Détail complet", index=False)
        for ws in xw.book.worksheets:
            for c in ws.columns:
                ws.column_dimensions[c[0].column_letter].width = min(60, max(len(str(x.value or "")) for x in c) + 2)


if __name__ == "__main__":
    report(ia.enrich(run(), exporter_modele=True))
