"""Assistant (chatbot) : questions courantes, définitions du glossaire, pilotage du tableau (données réelles du projet)."""
import pytest

import assistant
import corroboria
import ia


@pytest.fixture(scope="module")
def df():
    return ia.enrich(corroboria.run())


def rep(q, df, lang="fr", ctx=None):
    return assistant.repondre(q, df, lang, ctx or {"restant": 2, "total": 2})


def test_comptage_exact_des_anomalies(df):
    n = int((df.Statut == "ERREUR").sum())
    r = rep("Combien de vraies anomalies ?", df)
    assert f"**{n}**" in r["texte"] and r["actions"] == {}


def test_comptage_par_champ_synonyme_courriel(df):
    n = int(((df.Champ == "contactEmail") & (df.Statut == "ECART_JUSTIFIE")).sum())
    assert f"**{n}**" in rep("Combien d'écarts justifiés sur les courriels ?", df)["texte"]


def test_employe_et_champ_les_plus_touches(df):
    top_emp = df[df.Statut == "ERREUR"].Matricule.astype(str).value_counts().index[0]
    assert top_emp in rep("Quel employé a le plus d'anomalies ?", df)["texte"]
    top_champ = df[df.Statut == "ERREUR"].Champ.value_counts().index[0]
    assert top_champ in rep("Quel champ est le plus touché ?", df)["texte"]


def test_pilotage_du_tableau_statut_employe_champ(df):
    emp = df[df.Statut == "ERREUR"].Matricule.astype(str).iloc[0]
    r = rep(f"Montre-moi les anomalies de l'employé {emp}", df)
    assert r["actions"]["statuts"] == ["ERREUR"] and r["actions"]["employe"] == emp
    r = rep("Affiche les à relire sur les heures", df)
    assert r["actions"]["statuts"] == ["A_REVUE_JUSTIFIE", "A_REVUE_ERREUR"] and "weeklyHoursOverride" in r["actions"]["champs"]
    assert rep("Montre-moi", df)["actions"] == {}                      # question trop vague : on précise


def test_definition_champ_et_code(df):
    r = rep("C'est quoi positionName ?", df)
    assert "positionName" in r["texte"] and "Nom du rôle" in r["texte"]
    assert "Occasionnel" in rep("Que veut dire WHX ?", df)["texte"]
    assert "glossaire" in rep("C'est quoi zzzzz ?", df)["texte"]


def test_explication_ouvre_le_bandeau_ia(df):
    r = df[df.Statut == "ERREUR"].iloc[0]
    out = rep(f"Explique la ligne de l'employé {r.Matricule} sur {r.Champ}", df)
    assert out["actions"]["ouvrir"] in df.index and df.loc[out["actions"]["ouvrir"]].Matricule == r.Matricule


def test_seuil_reset_progres_aide_et_inconnu(df):
    assert rep("Mets le seuil à 95", df)["actions"] == {"seuil": 95}
    assert "entre 0 et 100" in rep("Change le seuil", df)["texte"]
    assert rep("Réinitialise les filtres", df)["actions"] == {"reset": True}
    assert "**2**" in rep("Combien reste-t-il à vérifier ?", df)["texte"]
    assert "Clique sur une question" in rep("aide", df)["texte"]
    assert "questions courantes" in rep("Quelle est la capitale de la France ?", df)["texte"]


def test_anglais(df):
    n = int((df.Statut == "ERREUR").sum())
    assert f"**{n}**" in rep("How many true anomalies?", df, "en")["texte"]
    assert "Click a question" in rep("help", df, "en")["texte"]


def test_lecture_seule(df):
    avant = df.copy()
    for q in ("Montre-moi les anomalies", "Explique l'employé 3712987", "Combien d'anomalies ?"):
        rep(q, df)
    assert df.equals(avant)                                            # l'assistant ne modifie jamais les données


@pytest.mark.parametrize("lang", ["fr", "en"])
def test_toutes_les_questions_proposees_sont_comprises(df, lang):
    for q in assistant.suggestions(df, lang):
        r = rep(q, df, lang)
        assert r["texte"] not in (assistant.T[lang]["inconnu"], assistant.T[lang]["montre_vague"]), q   # chaque bouton marche


def test_aide_et_inconnu_proposent_des_boutons(df):
    assert len(rep("aide", df)["suggestions"]) >= 8 and rep("Quelle est la capitale ?", df)["suggestions"]
    assert "suggestions" not in rep("Combien d'anomalies ?", df)
