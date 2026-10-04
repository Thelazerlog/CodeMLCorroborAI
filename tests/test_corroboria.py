"""Tests CorroborIA - servent aussi de démo : python -m pytest -v

Trois scénarios de référence : un cas conforme, un écart justifié, une vraie anomalie.
Les données sont fabriquées à partir d'une ligne réelle ; les fichiers fournis ne sont jamais modifiés.
"""
import hashlib
from pathlib import Path

import pandas as pd
import pytest

import corroboria as c
import ia
import llm
import retours

BASE = Path(__file__).parent.parent
DATA = BASE / "data"
REAL_SRC = pd.read_excel(DATA / "Employe_Source_Anonymise_VF.xlsx")
MOTIF = pd.DataFrame({"CodeCatégorieStatut": [703, 807], "CodeStatutSystèmeExterne": [100, 170],
                      "CodeGestionAccès": [1, 2]})


def dest_from(s):
    """Ligne cible parfaite pour une ligne source (selon les règles du mapping)."""
    prim, temp = c.type_flags(s.TypeAffectation)
    absent = s.CodeSuspensionAccès in (2, 3, 6, 7)
    return {
        "personId": s.Matricule, "givenName": s.PrénomUsuel, "surname": s.NomFamille,
        "contactEmail": f"{s.PrénomUsuel[0]}{s.NomFamille}{str(s.Matricule)[-3:]}@loto-quebec.com",
        "onboardDate": s.DateEmbaucheRécente.strftime("%Y-%m-%dT00:00:00.000Z"),
        "siteCode": s.CodeSite, "siteName": s.LibelléSite, "divisionId": s.CodeDirection,
        "divisionCode": s.CodeImputation, "divisionName": f"{s.CodeDirection:05d}-{s.LibelléDirection}",
        "positionId": s.CodeEmploi, "positionCode": s.CodeEmploi,
        "positionName": f"{s.CodeEmploi}-{s.IntituléEmploi}", "payGradeId": s.ÉchelleSalariale,
        "contractTypeCode": c.contract_code(s), "isPrimaryAssignment": prim, "isTemporaryAssignment": temp,
        "assignmentStartDate": s.DateEntréePoste, "termStartDate": s.DateEntréePoste,
        "weeklyHoursOverride": int(s.HeuresNormeHebdo), "dailyHoursOverride": int(s.HeuresNormeQuotidienne),
        "detailedStatus": "Absence complète" if absent else "Actif",
        "statusReasonCode": {807: 170}.get(s.CodeRaisonStatut) if absent else None,
        "expectedReturnDate": s.DateRetourAnticipée if absent else pd.NaT,
    }


def make(tmp_path, src_rows, dest_edit=None, drop_dest=()):
    """Écrit 4 petits fichiers xlsx et retourne le dict de chemins pour corroboria.run()."""
    src = pd.DataFrame(src_rows)
    dst = pd.DataFrame([dest_from(r) for _, r in src.iterrows()])
    dst = dst.drop(index=list(drop_dest)).reset_index(drop=True)
    for fn in (dest_edit or []):
        fn(dst)
    det_cols = "IdentifiantPoste,IdentifiantEmploi,CodeDirectionAffectée,DateEffetAffectation,CodeBudget," \
               "IndicateurGestion,CodePosteSecondaire,MatriculeGestionnaire,HeuresSemaineContrat," \
               "HeuresJourContrat,JoursTravailléesSemaine"
    det = pd.DataFrame({det_cols: [f"{r.CodePoste},{r.CodeEmploi},{r.CodeDirection},40000,1,0,1,1,40,8,5"
                                   for _, r in src.iterrows()]})
    paths = {}
    for k, d in (("source", src), ("destination", dst), ("motif", MOTIF), ("detail", det)):
        paths[k] = tmp_path / f"{k}.xlsx"
        d.to_excel(paths[k], index=False)
    return paths


def base_row(**kw):
    r = REAL_SRC[REAL_SRC.Matricule == 9989151].iloc[0].copy()  # permanent, temps plein, actif
    for k, v in kw.items():
        r[k] = v
    return r


def get(df, champ, matricule=9989151):
    r = df[(df.Champ == champ) & (df.Matricule == matricule)]
    assert len(r) >= 1, f"aucun contrôle {champ}"
    return r.iloc[0]


# ------------------------------------------------------------------ 1) CAS CONFORME
def test_cas_conforme(tmp_path):
    df = c.run(make(tmp_path, [base_row()]))
    assert (df.Statut == c.OK).all(), df[df.Statut != c.OK][["Champ", "Explication"]]


# ------------------------------------------------------------------ 2) ÉCART JUSTIFIÉ
def test_ecart_justifie_encodage(tmp_path):
    """« Absence complète » mal décodé en B : valeur correcte, défaut d'encodage."""
    s = base_row(CodeStatutEmploi=2, CodeRaisonStatut=807, CodeSuspensionAccès=2,
                 DateRetourAnticipée=pd.Timestamp("2026-01-15"))
    p = make(tmp_path, [s], [lambda d: d.__setitem__("detailedStatus", "Absence complÃ¨te")])
    df = c.run(p)
    r = get(df, "detailedStatus (encodage)")
    assert r.Statut == c.JUSTIFIE and "UTF-8" in r.Explication


def test_ecart_justifie_courriel_dev_par_ia(tmp_path):
    """Préfixe d'environnement de dév. sur le courriel : tranché par la composante IA, pas par une règle."""
    p = make(tmp_path, [base_row()],
             [lambda d: d.__setitem__("contactEmail", "dev-08-v2_PNom10372372@loto-quebec.com")])
    out = ia.enrich(c.run(p))
    r = get(out, "contactEmail")
    assert r.Statut == c.JUSTIFIE and r.Source_verdict == "IA"
    assert "P(erreur)" in r.Explication


# ------------------------------------------------------------------ 3) VRAIE ANOMALIE
def test_vraie_anomalie_type_contrat(tmp_path):
    """Employé permanent temps plein : JWN attendu, B contient XFLR."""
    p = make(tmp_path, [base_row()], [lambda d: d.__setitem__("contractTypeCode", "XFLR")])
    out = ia.enrich(c.run(p))
    r = get(out, "contractTypeCode")
    assert r.Statut == c.ERREUR and r.Source_verdict == "règle" and r.ValeurSourceA == "JWN"
    assert r.Priorité >= 80  # gravité élevée


def test_anomalie_heures(tmp_path):
    """Source 35 h, B contient la valeur par défaut 40 h."""
    p = make(tmp_path, [base_row(HeuresNormeHebdo=35.0, HeuresNormeQuotidienne=7.0)],
             [lambda d: d.__setitem__("weeklyHoursOverride", 40)])
    assert get(c.run(p), "weeklyHoursOverride").Statut == c.ERREUR


def test_affectation_manquante_en_b(tmp_path):
    rows = [base_row(), base_row(Matricule=1111111, TypeAffectation="A", CodePoste=45985)]
    df = c.run(make(tmp_path, rows, drop_dest=[1]))
    r = get(df, "Enregistrement", 1111111)
    assert r.Statut == c.ERREUR and "absente" in r.Explication


# ------------------------------------------------------------------ règles métier
@pytest.mark.parametrize("code,attendu", [(1, "Actif"), (2, "Absence complète"), (3, "Absence complète"),
                                          (6, "Absence complète"), (7, "Absence complète")])
def test_situation_emploi(tmp_path, code, attendu):
    s = base_row(CodeSuspensionAccès=code, CodeRaisonStatut=807 if code != 1 else 703,
                 DateRetourAnticipée=pd.Timestamp("2026-01-15") if code != 1 else pd.NaT)
    df = c.run(make(tmp_path, [s]))
    r = get(df, "detailedStatus")
    assert r.ValeurSourceA == attendu and r.Statut == c.OK


@pytest.mark.parametrize("cat,perm,ft,attendu", [("V", "Oui", "Oui", "JWN"), ("V", "Oui", "Non", "XFLR"),
                                                 ("T", "Non", "Non", "KELH"), ("O", "Non", "Non", "WHX"),
                                                 ("M", "Non", "Non", "CEGQ"), ("R", "Non", "Non", "CNZC"),
                                                 ("J", "Non", "Non", "RMQ"), ("Z", "Non", "Non", "JAW"),
                                                 ("Q", "Non", "Non", "TRSY")])
def test_type_employe(cat, perm, ft, attendu):
    assert c.contract_code(base_row(CatégorieEmploi=cat, EstPermanent=perm, EstTempsPlein=ft)) == attendu


def test_nom_sans_accents(tmp_path):
    s = base_row(PrénomUsuel="Éloïse", NomFamille="Gérard")
    p = make(tmp_path, [s], [lambda d: d.__setitem__("givenName", "Eloise")])
    assert get(c.run(p), "givenName").Statut == c.OK


def test_regle_dates_detail_desactivee():
    assert c.USE_DETAIL_MIN is False  # décision utilisateur : règle gardée désactivée


# ------------------------------------------------------------------ retour d'expert
def test_correction_expert(tmp_path, monkeypatch):
    p = make(tmp_path, [base_row()], [lambda d: d.__setitem__("contractTypeCode", "XFLR")])
    (tmp_path / "corrections.csv").write_text("Matricule,Champ,Verdict\n9989151,contractTypeCode,ECART_JUSTIFIE\n",
                                              encoding="utf-8")
    monkeypatch.setattr(retours, "JOURNAL", tmp_path / "corrections.csv")  # ancien format à 3 colonnes, toujours lu
    monkeypatch.setattr(retours, "REGLES", tmp_path / "regles_apprises.json")
    r = get(ia.enrich(c.run(p)), "contractTypeCode")
    assert r.Statut == c.JUSTIFIE and r.Source_verdict == "expert"


# ------------------------------------------------------------------ LLM local (à la demande)
ROW = pd.Series({"Champ": "contractTypeCode", "Règle": "Règle type d'employé", "ValeurSourceA": "JWN",
                 "ValeurDestB": "XFLR", "Statut": "ERREUR", "Source_verdict": "règle", "Confiance": 1.0,
                 "Explication": "Valeur attendue JWN, trouvée XFLR", "Cause_probable": ""})


def test_llm_indisponible_repli(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise OSError("Ollama arrêté")
    monkeypatch.setattr(llm, "CACHE", tmp_path / "cache.json")
    monkeypatch.setattr(llm.urllib.request, "urlopen", boom)
    assert llm.explain_row(ROW) is None  # pas d'exception : l'app garde l'explication par gabarit


def test_llm_a_la_demande_et_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "CACHE", tmp_path / "cache.json")
    calls = []

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def read(self):
            return b'{"message": {"content": "Pour contractTypeCode, A a JWN mais B contient XFLR."}}'

    monkeypatch.setattr(llm.urllib.request, "urlopen", lambda *a, **k: calls.append(1) or Resp())
    assert llm.cached(ROW) is None and not calls  # rien d'appelé tant qu'on ne le demande pas
    assert "JWN" in llm.explain_row(ROW) and len(calls) == 1
    assert llm.explain_row(ROW) == llm.cached(ROW) and len(calls) == 1  # 2e fois : cache, pas d'appel


def _ligne(champ, a, b, **kw):
    return pd.Series({"Champ": champ, "ValeurSourceA": a, "ValeurDestB": b, "Statut": "ECART_JUSTIFIE", "Source_verdict": "IA",
                      "Confiance": 0.94, "Règle": "Concaténation", "Explication": "Libellé différent | IA : P(erreur) = 3%.",
                      "Cause_probable": "", **kw})


def test_prompt_structure_et_consignes():
    assert "FICHE DU CHAMP" in llm.SYSTEM and "À vérifier" in llm.SYSTEM and "propagation" not in llm._prompt(ROW)
    assert "contractTypeCode" in llm._prompt(ROW)


def test_fiche_glossaire_pour_positionname():
    p = llm._prompt(_ligne("positionName", "6900-Empl6900", "5123-Empl5123"))
    assert "Nom du rôle" in p and "IntituléEmploi" in p            # description + colonne du système A (Mapping.xlsx)
    assert "Concaténation de Emploi" in p                          # règle du mapping
    assert "numéro 6900, description « Empl6900 »" in p            # valeur décodée
    assert "P(erreur)" not in p                                    # jargon du modèle IA retiré


def test_decodage_des_codes_et_des_courriels():
    p = llm._prompt(_ligne("contractTypeCode", "JWN", "WHX"))
    assert "JWN = Permanent temps plein" in p and "WHX = Occasionnel" in p
    mail = llm.lecture("contactEmail", "dev-08-v2_PNom10430430@loto-quebec.com")
    assert "environnement de développement" in mail and "dev-08-v2_" in mail
    assert "identifiant « PNom6035643643 »" in llm.lecture("contactEmail", "PNom6035643643@loto-quebec.com")


def test_champ_sans_fiche_reste_prudent():
    assert "aucune fiche" in llm.fiche("champInconnu") or "Pour comprendre" in llm.fiche("Enregistrement")
    assert "aucune fiche" in llm.fiche("champInconnu")


# ------------------------------------------------------------------ export + lecture seule
def test_export_excel_et_csv(tmp_path):
    df = ia.enrich(c.run(make(tmp_path, [base_row()], [lambda d: d.__setitem__("contractTypeCode", "XFLR")])))
    xl = tmp_path / "r.xlsx"
    c.write_sheets(df, xl)
    assert {"Erreurs à investiguer", "Écarts justifiés", "Détail complet"} <= set(pd.ExcelFile(xl).sheet_names)
    csv = df.to_csv(index=False, sep=";").encode("utf-8-sig")
    assert csv.startswith(b"\xef\xbb\xbf")


def test_glossaire():
    g = c.glossary_fields()
    assert "contractTypeCode" in set(g["Champ système B"]) and len(c.GLOSSARY_CODES) > 10


def test_fichiers_sources_non_modifies():
    files = list(DATA.glob("*.xlsx"))
    before = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    ia.enrich(c.run())
    assert before == {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
