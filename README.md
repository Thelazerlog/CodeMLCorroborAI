# CorroborIA – détection intelligente des écarts (A-RH → B-Temps)

## Lancer
```
pip install -r requirements.txt
python corroboria.py          # génère rapport_corroboration.xlsx
python -m streamlit run app.py   # application
python -m pytest -v           # tests (servent aussi de démo : conforme / justifié / anomalie)
```
LLM local (optionnel) : installer [Ollama](https://ollama.com) puis `ollama pull qwen2.5:3b`. Autre modèle : variable `CORROBORIA_MODEL`.
Les fichiers Excel sources sont lus en lecture seule. Aucune donnée ne quitte la machine (pas d'appel réseau).

## Structure
```
app.py            application Streamlit        data/     extractions A/B, mapping, tables (lecture seule)
corroboria.py     moteur de règles             assets/   logos (détectés par leur nom : corrobor*, loto*/quebec*)
ia.py             modèle scikit-learn          docs/     consignes et présentation
llm.py            LLM local (Ollama)           tests/    pytest (démo : conforme / justifié / anomalie)
corrections.csv   retours d'experts            outputs/  rapports et cache LLM générés
```

## Architecture (3 niveaux)
1. **Règles déterministes** (`corroboria.py`) : appliquent le `Mapping.xlsx` champ par champ (accents, courriel, type de contrat, affectation, situation d'emploi via la table des motifs, heures, dates). Verdict `Source_verdict = règle`.
2. **IA locale** (`ia.py`) : sur les écarts *ambigus* (courriel, libellé de rôle, heures sans valeur source), un RandomForest scikit-learn estime P(erreur). Si 0,35 < P < 0,65 → `A_REVUE_HUMAINE` (affiché « À relire »). Verdict `Source_verdict = IA`, avec les facteurs utilisés.
3. **LLM local** (`llm.py`, Ollama, `qwen2.5:3b`) : rédige en français (2 phrases : constat + « À vérifier : ») la justification d'une erreur **à la demande**, via le bouton « Expliquer » de l'app (≈ 30-60 s sans GPU). Il ne change **jamais** un verdict. Réponses mises en cache (`outputs/llm_cache.json`) ; repli sur le gabarit si Ollama est absent. Tout reste sur la machine.
4. **Priorisation** : score 0-100 = gravité du champ (60 %) + confiance (25 %) + récurrence du champ (15 %), poids normalisés (`ia.priorite`, `ia.WEIGHTS`, `ia.SEVERITY`), et `Cause_probable` (ex. « B contient toujours 40 : valeur par défaut »).

## Application
- **En-tête** : logo, titre (CorroborIA / CorroborAI en anglais), interrupteur de langue FR/EN, logo Loto-Québec.
- **Tableau de bord** : anneau interactif (conforme / écart justifié / vraie anomalie / à relire) et indicateurs clés, dont la confiance générale du modèle (IA + vraies anomalies).
- **Seuil de confiance** (curseur sous l'anneau) : tout écart non conforme dont la confiance est sous le seuil passe dans « À relire », et l'anneau suit le curseur.
- **À faire** : lignes à investiguer (catégories au choix : vraie anomalie, écarts justifiés), barre de progression et premières lignes à vérifier ; un clic ouvre la ligne en surbrillance dans le tableau.
- **Investiguer les données** : exports et onglets Vraie anomalie, Écarts justifiés (colonne « Vérifié » cochable, pré-cochée en gris au-dessus du seuil), Par champ, Tout, Glossaire, **Paramètres** (poids du score de priorité et gravité par variable, modifiables).
- Les réglages et les lignes vérifiées ne sont conservés que pendant la session.

## Exports
Excel + CSV (séparateur `;`, UTF-8 avec BOM) : tout, vraies anomalies seules, justifiés. Le score de priorité exporté suit les poids réglés dans l'onglet Paramètres. Onglet **Glossaire** dans l'app (champs lus dans `Mapping.xlsx` + codes).

## Rapport (`outputs/rapport_corroboration.xlsx`)
Onglets : Erreurs à investiguer (vraies anomalies), À relire, Écarts justifiés, Résumé par champ, Détail complet. Chaque ligne porte la règle appliquée, le verdict, l'origine (règle / IA / expert), la confiance et l'explication.

## Retour d'expert
`corrections.csv` (Matricule, Champ, Verdict) : relu à chaque exécution, prime sur tout verdict et enrichit l'entraînement (poids x20). Modifiable aussi depuis l'app.

## Hypothèses et limites
- Règle « date la plus ancienne entre DateEntréePoste et date d'effet de l'unité adm. » : donne une date antérieure pour 100 % de l'échantillon (dates du `détail_du_poste` incohérentes). Désactivée (`USE_DETAIL_MIN = False`), on compare à `DateEntréePoste`.
- Courriel et libellé de rôle : préfixe `dev-` et nom différent traités comme artefacts d'anonymisation ; à revoir sur des données réelles.
- Pas de vérité terrain fournie : le modèle s'entraîne sur les verdicts de règles sûrs + cas synthétiques par perturbation + corrections d'experts. Échantillon de 22 lignes : les scores sont indicatifs.
- Champs non mappés (ex. `customAttribute_15`) ignorés, conformément à l'énoncé.
