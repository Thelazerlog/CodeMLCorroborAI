"""Retours d'experts : journal, règles apprises (seuil de 3 corrections concordantes) et effet sur les verdicts."""
import pandas as pd
import pytest

import corroboria
import ia
import retours


@pytest.fixture(autouse=True)
def fichiers_temporaires(tmp_path, monkeypatch):
    """Journal et règles dans un dossier temporaire : les vrais fichiers ne sont jamais modifiés par les tests."""
    monkeypatch.setattr(retours, "JOURNAL", tmp_path / "corrections.csv")
    monkeypatch.setattr(retours, "REGLES", tmp_path / "regles_apprises.json")


def corriger(n, verdict="ERREUR", champ="positionName", a="6585-Empl6585", b="3649-Empl3649", **kw):
    for i in range(n):
        retours.ajouter(f"100000{i}", champ, verdict, motif="erreur_confirmee", auteur="expert1", valeur_a=a, valeur_b=b, **kw)


def test_journal_garde_motif_auteur_date_et_historique():
    retours.ajouter("1", "positionName", "ERREUR", motif="erreur_confirmee", commentaire="vrai écart", auteur="nico",
                    valeur_a="1-Emp", valeur_b="2-Emp", regle="Concaténation", ancien="ECART_JUSTIFIE")
    j = retours.lire_journal()
    assert list(j.columns) == retours.COLS and j.Auteur[0] == "nico" and j.Motif[0] == "erreur_confirmee"
    assert j.AncienVerdict[0] == "ECART_JUSTIFIE" and len(j.Date[0]) == 16
    retours.ajouter("1", "positionName", "ECART_JUSTIFIE", auteur="nico")  # nouvel avis : le journal garde les deux
    assert len(retours.lire_journal()) == 2
    assert retours.corrections_effectives().Verdict.tolist() == ["ECART_JUSTIFIE"]  # la dernière gagne


def test_annulation_retire_la_correction_sans_effacer_l_historique():
    retours.ajouter("1", "positionName", "ERREUR", valeur_a="1-E", valeur_b="2-E")
    retours.annuler("1", "positionName", auteur="nico")
    assert retours.corrections_effectives().empty and len(retours.lire_journal()) == 2
    assert ia.load_corrections().empty


def test_ancien_format_a_trois_colonnes_toujours_lu(tmp_path):
    retours.JOURNAL.write_text("Matricule,Champ,Verdict\n2762457,contractTypeCode,ECART_JUSTIFIE\n", encoding="utf-8")
    assert retours.corrections_effectives().Verdict.tolist() == ["ECART_JUSTIFIE"]


def test_forme_des_valeurs():
    assert retours.forme("dev-08-v2_PNom10430430@loto-quebec.com") == "dev-#-v#_PNom#@loto-quebec.com"
    assert retours.forme("6900-Empl6900") == "#-Empl#"


def test_regle_proposee_a_partir_de_3_corrections_concordantes_seulement():
    corriger(2)
    assert retours.propositions() == []          # 2 corrections : pas encore
    corriger(3)
    p = retours.propositions()
    assert len(p) == 1 and p[0]["n"] == 3 and p[0]["verdict"] == "ERREUR"
    assert p[0]["forme_a"] == "#-Empl#" and p[0]["forme_b"] == "#-Empl#"


def test_contre_exemple_empeche_la_proposition():
    corriger(3)
    retours.ajouter("2000000", "positionName", "ECART_JUSTIFIE", valeur_a="7-Empl7", valeur_b="8-Empl8")
    assert retours.propositions() == []          # même forme, verdict contraire : on ne généralise pas


def test_valider_ou_rejeter_une_proposition():
    corriger(3)
    p = retours.propositions()[0]
    retours.rejeter(p, "nico")
    assert retours.propositions() == [] and retours.regles_actives() == []   # rejetée : ne revient pas
    corriger(3, champ="siteName", a="Emplacement1", b="Emplacement2")
    retours.valider(retours.propositions()[0], "nico")
    assert len(retours.regles_actives()) == 1 and retours.regles_actives()[0]["auteur"] == "nico"
    retours.desactiver(retours.regles_actives()[0]["id"], "nico")
    assert retours.regles_actives() == []


def test_regle_apprise_appliquee_puis_expert_prime():
    brut = corroboria.run()
    avant = ia.enrich(brut)
    cibles = avant[(avant.Champ == "positionName") & (avant.Statut != "OK")]
    assert len(cibles) >= 4 and (cibles.Statut == "ECART_JUSTIFIE").all()
    ex = cibles.iloc[:3]
    for r in ex.itertuples():                    # l'expert juge 3 fois que c'est une vraie erreur
        retours.ajouter(r.Matricule, r.Champ, "ERREUR", motif="erreur_confirmee", auteur="expert1",
                        valeur_a=r.ValeurSourceA, valeur_b=r.ValeurDestB)
    prop = retours.propositions()
    assert len(prop) == 1
    retours.valider(prop[0], "expert1")
    apres = ia.enrich(brut)
    pos = apres[(apres.Champ == "positionName") & (apres.Statut != "OK")]
    assert (pos.Statut == "ERREUR").all()                                   # généralisé aux autres lignes
    assert (pos.Source_verdict == "règle apprise").sum() == len(cibles) - 3  # 3 corrigées par l'expert, le reste par la règle
    assert (pos.Source_verdict == "expert").sum() == 3
    # un expert peut encore contredire la règle sur une ligne précise
    autre = cibles.iloc[3]
    retours.ajouter(autre.Matricule, autre.Champ, "ECART_JUSTIFIE", auteur="expert2")
    fin = ia.enrich(brut)
    ligne = fin[(fin.Matricule == autre.Matricule) & (fin.Champ == "positionName")]
    assert (ligne.Statut == "ECART_JUSTIFIE").all() and (ligne.Source_verdict == "expert").all()


def test_effet_des_retours_mesure():
    brut = corroboria.run()
    base = ia.effet_retours(brut)
    assert base["total_changes"] == 0                                       # sans retour, aucun changement
    cibles = ia.enrich(brut)
    cibles = cibles[(cibles.Champ == "positionName") & (cibles.Statut != "OK")].iloc[:3]
    for r in cibles.itertuples():
        retours.ajouter(r.Matricule, r.Champ, "ERREUR", valeur_a=r.ValeurSourceA, valeur_b=r.ValeurDestB)
    e = ia.effet_retours(brut)
    assert e["corriges_par_expert"] == 3 and e["total_changes"] >= 3


def test_les_vrais_fichiers_ne_sont_pas_touches_par_les_tests():
    assert retours.JOURNAL.name == "corrections.csv" and retours.JOURNAL.parent != retours.BASE
