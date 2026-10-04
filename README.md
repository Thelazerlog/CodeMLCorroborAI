# CorroborIA – détection intelligente des écarts (A-RH → B-Temps)

## Lancer
```
pip install -r requirements.txt
python corroboria.py          # génère rapport_corroboration.xlsx
python -m streamlit run app.py   # application
jupyter notebook CorroborIA_remise.ipynb   # notebook de remise (déjà exécuté)
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
CorroborIA_remise.ipynb   notebook de remise
corrections.csv   journal des corrections d'experts
retours.py        journal, règles apprises (seuil de 3), effet
regles_apprises.json  règles validées par un expert (créé à la 1re validation)
glossaire_ia.json explications en langage courant des champs (données au LLM)
outputs/          rapports et cache LLM générés
```

## Architecture (3 niveaux)
1. **Règles déterministes** (`corroboria.py`) : appliquent le `Mapping.xlsx` champ par champ (accents, courriel, type de contrat, affectation, situation d'emploi via la table des motifs, heures, dates). Verdict `Source_verdict = règle`.
2. **IA locale** (`ia.py`) : sur les écarts *ambigus* (courriel, libellé de rôle, heures sans valeur source), un RandomForest scikit-learn estime P(erreur). Si 0,35 < P < 0,65 → `A_REVUE_HUMAINE` (affiché « À relire »). Verdict `Source_verdict = IA`, avec les facteurs utilisés.
3. **LLM local** (`llm.py`, Ollama, `qwen2.5:3b`) : rédige en français (3 phrases : ce que c'est, ce qu'on voit, « À vérifier : ») la justification d'une erreur **à la demande**, quand on clique sur la **cloche** (images `assets/cloche_*.png`) à gauche d'une ligne du tableau (l'explication s'affiche dans un bandeau en bas de page ; ≈ 30-60 s sans GPU ; Ollama n'est interrogé qu'à ce moment-là). Pour être compréhensible, il reçoit une **fiche du champ** retrouvée par le code dans le glossaire de `Mapping.xlsx` (description, colonne du système A, règle) et dans `glossaire_ia.json` (explication en langage courant, modifiable), les codes de la ligne traduits (JWN = permanent temps plein, etc.) et les valeurs décodées (« 6900-Empl6900 » = emploi 6900, description Empl6900). Il ne change **jamais** un verdict. Réponses mises en cache (`outputs/llm_cache.json`) ; repli sur le gabarit si Ollama est absent. Tout reste sur la machine.
4. **Priorisation** : score 0-100 = gravité du champ (60 %) + confiance (25 %) + récurrence du champ (15 %), poids normalisés (`ia.priorite`, `ia.WEIGHTS`, `ia.SEVERITY`), et `Cause_probable` (ex. « B contient toujours 40 : valeur par défaut »).

## Application
- **En-tête** : logo, titre (CorroborIA / CorroborAI en anglais), interrupteur de langue FR/EN, logo Loto-Québec.
- **Tableau de bord** : anneau interactif (conforme / écart justifié / vraie anomalie / à relire) et indicateurs clés, dont la confiance générale du modèle (IA + vraies anomalies).
- **Seuil de confiance** (curseur sous l'anneau) : tout écart non conforme dont la confiance est sous le seuil (0-100 %, 90 % par défaut) passe dans « À relire », et l'anneau suit le curseur. Les vraies anomalies n'y passent que si l'option *Relire les vraies anomalies sous le seuil* (onglet Paramètres, « Non » par défaut) est activée.
- **Barre de revue humaine** (tableau de bord) : lignes « À relire » vérifiées sur le total, avec message d'encouragement.
- **Données sélectionnées** : tableau des lignes choisies par pastilles de statut ou par clic sur l'anneau et les camemberts, avec tri par priorité.
- **Investiguer les données** : exports et onglets Vraie anomalie, Écarts justifiés (colonne « Vérifié » cochable, pré-cochée en gris au-dessus du seuil), Par champ, Tout, Glossaire, **Paramètres** (poids du score de priorité et gravité par variable, modifiables).
- Les réglages et les lignes vérifiées ne sont conservés que pendant la session.

## Exports
Excel + CSV (séparateur `;`, UTF-8 avec BOM) : tout, vraies anomalies seules, justifiés. Le score de priorité exporté suit les poids réglés dans l'onglet Paramètres. Onglet **Glossaire** dans l'app (champs lus dans `Mapping.xlsx` + codes).

## Rapport (`outputs/rapport_corroboration.xlsx`)
Onglets : Erreurs à investiguer (vraies anomalies), À relire, Écarts justifiés, Résumé par champ, Détail complet. Chaque ligne porte la règle appliquée, le verdict, l'origine (règle / IA / expert), la confiance et l'explication.

## Retour d'expert et règles apprises (`retours.py`)
Dans le tableau, le statut d'une ligne se corrige avec la liste déroulante (texte coloré, crayon `assets/pencil-square-svgrepo-com.svg`) ; une boîte de **confirmation** demande le motif (artefact d'anonymisation, donnée source erronée, règle trop stricte, erreur confirmée, autre), un commentaire facultatif et l'auteur.
- **Journal** : `corrections.csv` (Matricule, Champ, Verdict, Motif, Commentaire, Auteur, Date, ValeurA, ValeurB, Regle, AncienVerdict). L'historique est conservé : une correction s'annule dans la pastille **Corrections** (ligne « ANNULE »). L'ancien format à 3 colonnes reste lu.
- **Effets** : la correction remplace le verdict de la ligne (origine « expert », confiance 100 %) et enrichit l'entraînement du modèle (poids ×20).
- **Règle apprise** : à partir de **3 corrections concordantes** (même champ, même « forme » des valeurs A et B où les chiffres deviennent `#`, même verdict, aucun contre-exemple), la pastille **Corrections** propose une règle ; l'expert la **valide ou la rejette**. Une règle validée (`regles_apprises.json`) est appliquée aux écarts du même type (origine « règle apprise »), reste distincte des règles du mapping, et peut être désactivée. Une correction d'expert prime toujours sur une règle apprise.
- **Effet mesurable** : le bouton « Mesurer l'effet » compare les verdicts avec et sans retours (lignes corrigées, verdicts changés par les règles apprises, verdicts du modèle changés).

## Hypothèses et limites
- Règle « date la plus ancienne entre DateEntréePoste et date d'effet de l'unité adm. » : donne une date antérieure pour 100 % de l'échantillon (dates du `détail_du_poste` incohérentes). Désactivée (`USE_DETAIL_MIN = False`), on compare à `DateEntréePoste`.
- Courriel et libellé de rôle : préfixe `dev-` et nom différent traités comme artefacts d'anonymisation ; à revoir sur des données réelles.
- Pas de vérité terrain fournie : le modèle s'entraîne sur les verdicts de règles sûrs + cas synthétiques par perturbation + corrections d'experts. Échantillon de 22 lignes : les scores sont indicatifs.
- Champs non mappés (ex. `customAttribute_15`) ignorés, conformément à l'énoncé.
