# CorroborIA – détection intelligente des écarts (système A – RH → système B – Temps)

NNous avons conçu CorroborAI, une application scalable qui permet de comparer les Système A - RH et Système B - Temps. Elle utilise une approche hybride incluant des règles déterministes et un modèle scikit-learn local et génère un fichier Excel Récapitulatif. Notre modèle est explicable, transparent et donne également un score de confiance pour chacune de ses prédictions (score moyen = 95%).

Mais ce n'est pas tout ! Notre application intègre également un tableau de bord complet, un système d'analyses des écarts ergonomique et un chatbot LLM guidant l'utilisateur dans l'utilisation et l'interprétation de l'application. Elle permet également à un Expert de réviser les données et met à jour automatiquement le modèle de machine learning utilisé pour la classification des écarts.

<p align="center"><img src="assets/Vue%20de%20l'application%201.png" alt="Vue sur le tableau de bord de l'application" width="900"/><br/><em>Vue sur le tableau de bord de l'application.</em></p>

<p align="center"><img src="assets/Explication%20IA%20d'un%20%C3%A9cart.png" alt="L'utilisateur demande de l'aide pour comprendre un écart et comment il a été classé à notre IA intégrée" width="900"/><br/><em>L'utilisateur demande de l'aide pour comprendre un écart et comment il a été classé à notre IA intégrée.</em></p>

## Installer rapidement l'application

1. **Cloner le dépôt**
   ```bash
   git clone https://github.com/Thelazerlog/CodeMLCorroborAI.git
   cd CodeMLCorroborAI
   ```
2. **Installer les dépendances** (Python 3.10 ou plus)
   ```bash
   pip install -r requirements.txt
   ```
3. **Télécharger un des modèles Ollama** (installer d'abord [Ollama](https://ollama.com)) : `qwen2.5:3b` (équilibré, recommandé), `qwen2.5:1.5b` (rapide) ou `qwen2.5:7b` (précis)
   ```bash
   ollama pull qwen2.5:3b
   ```
4. **Lancer l'application** :)
   ```bash
   python -m streamlit run app.py
   ```
   Puis ouvrir http://localhost:8501 et cliquer sur **Lancer la corroboration**. Les fichiers fournis dans `data/` sont utilisés par défaut ; sans Ollama, l'application fonctionne quand même (seule l'explication par le LLM de la cloche est désactivée).






**Guide d'utilisation illustré : [`docs/guide_utilisation.html`](docs/guide_utilisation.html)** (un seul fichier, à ouvrir dans un navigateur).

## Démarrage rapide
```
pip install -r requirements.txt
python corroboria.py                       # analyse + rapport Excel (outputs/rapport_corroboration.xlsx) + modèle (modele/modele_corroboria.*)
python -m streamlit run app.py             # application (charger les fichiers, lancer, consulter)
jupyter notebook CorroborIA_remise.ipynb   # notebook de remise (déjà exécuté)
python demo.py                             # démonstration en ligne de commande : conforme, écart justifié, vraie anomalie
python -m pytest -v                        # tests (servent aussi de démonstration)
python scripts/build_notebook.py           # régénère et exécute le notebook de remise (nbformat, nbclient)
python scripts/guide/build_guide.py        # régénère docs/guide_utilisation.html à partir des captures
```
- Les fichiers fournis sont dans `data/` et utilisés par défaut ; ils peuvent être remplacés depuis l'application (**Excel .xlsx ou CSV**, séparateur et encodage détectés). Ils sont **lus en lecture seule** (un test le vérifie par somme de contrôle).
- LLM local (optionnel) : installer [Ollama](https://ollama.com) puis `ollama pull qwen2.5:3b` (équilibré), `qwen2.5:1.5b` (rapide) ou `qwen2.5:7b` (précis). Un GPU NVIDIA est utilisé automatiquement s'il existe.
- Si les fichiers chargés ne sont pas les bonnes extractions, l'application l'indique en français (colonnes attendues manquantes, fichier illisible).

## Structure
```
app.py                     application Streamlit
demo.py                    démonstration en ligne de commande (3 cas)
corroboria.py              moteur de règles, rapport Excel, glossaire
ia.py                      modèle scikit-learn, priorité, effet des retours
llm.py                     LLM local (Ollama) : fiche du champ, prompt, cache
retours.py                 journal des corrections d'experts, règles apprises (seuil de 3)
assistant.py               chatbot : questions courantes et pilotage du tableau
glossaire_ia.json          explications en langage courant des champs (données au LLM)
corrections.csv            journal des corrections d'experts
regles_apprises.json       règles validées par un expert (créé à la 1re validation)
data/                      extractions A/B, mapping, tables (lecture seule)
assets/                    logos et icônes (cloche grise/violette, crayon)
docs/                      consignes, présentation, guide d'utilisation (HTML), captures (img_guide/), exemple de rapport
scripts/                   outils de remise : build_notebook.py, guide/ (capture_guide.py, serveur_demo.py, build_guide.py)
tests/                     pytest (démo : conforme / justifié / anomalie, robustesse, retours, assistant)
modele/                    modèle entraîné (.joblib) et sa fiche (.json), versionnés
outputs/                   rapport Excel, cache LLM (générés)
CorroborIA_remise.ipynb    notebook de remise
```

## Architecture : trois niveaux
1. **Comparaison brute + règles déterministes** (`corroboria.py`) : chaque champ du mapping est normalisé (accents, vides, dates, libellés, structures répétitives) puis comparé à la valeur attendue. Le verdict porte la **règle appliquée** et une explication. `Source_verdict = règle`.
2. **IA locale sur les cas ambigus** (`ia.py`) : pour les écarts que les règles ne tranchent pas seules (courriel, libellé de poste, heures sans valeur source), un RandomForest estime P(erreur). Entre 0,35 et 0,65 le cas passe à « À relire ». `Source_verdict = IA`, avec les facteurs utilisés.
3. **LLM local pour expliquer** (`llm.py`) : sur demande (clic sur la cloche d'une ligne), il rédige en 4 phrases claires ce que c'est, ce qu'on voit, quoi vérifier et **pourquoi la ligne a ce verdict** (règle ou modèle, confiance, seuil non atteint pour un « À relire »). Il reçoit une **fiche du champ** retrouvée par le code (glossaire du mapping + `glossaire_ia.json`), les codes traduits (JWN = permanent temps plein…) et les valeurs décodées (« 6900-Empl6900 » = emploi 6900, description Empl6900). **Il ne change jamais un verdict.** Réponses en cache (`outputs/llm_cache.json`) ; repli sur l'explication du moteur si Ollama est absent.

Sur ces trois niveaux se greffent : la **priorisation** (score 0-100 = gravité du champ 60 % + confiance 25 % + récurrence 15 %, réglable), le statut **Écart justifié (100 % des données)** (champ dont toutes les lignes, au moins 3, sont des écarts justifiés : `contactEmail`, `positionName`), le **seuil de confiance** (sous le seuil : « À relire », scindé dans l'application en **À relire (écart justifié)** et **À relire (vraie anomalie)** selon le verdict dont la ligne est issue), les **retours d'experts** et l'**assistant**.

Chaque verdict indique son origine : **règle** du mapping, **IA** locale, **expert** (correction manuelle) ou **règle apprise** (validée par un expert).

## Règles prises en charge
| Champ système B | Règle (source : `Mapping.xlsx`) | Nature |
|---|---|---|
| `personId` | = Matricule | règle |
| `givenName`, `surname` | copie, comparée sans accents | règle |
| `contactEmail` | gabarit : initiale du prénom + nom + 3 derniers chiffres du matricule + `@loto-quebec.com` ; préfixe `dev-` et noms anonymisés = artefact | règle + **IA** |
| `onboardDate` | = DateEmbaucheRécente | règle |
| `siteName`, `siteCode` | = LibelléSite, CodeSite | règle |
| `divisionId`, `divisionCode` | = CodeDirection, CodeImputation | règle |
| `divisionName` | unité adm. + « - » + description | règle |
| `positionId`, `positionCode` | = CodeEmploi | règle |
| `positionName` | emploi + « - » + description | **IA** (libellés anonymisés) |
| `payGradeId` | = ÉchelleSalariale | règle |
| `contractTypeCode` | PERM/FT/EMPTP → JWN, XFLR, KELH, WHX, CEGQ, CNZC, RMQ, JAW, TRSY | règle |
| `isPrimaryAssignment`, `isTemporaryAssignment` | type P = primaire, A = temporaire, S = ni l'un ni l'autre | règle |
| `detailedStatus`, `statusReasonCode`, `expectedReturnDate` | situation d'emploi via la table des motifs : accès 00/01 = actif ; 02, 03, 06, 07 = absence complète avec code Remphor et date de retour | règle |
| `weeklyHoursOverride`, `dailyHoursOverride` | heures de la norme du poste ; valeur A vide : repli sur le détail du poste | règle + **IA** |
| `assignmentStartDate`, `termStartDate` | source = DateEntréePoste seule ; B = règle transformée (la plus récente entre DateEntréePoste et la date d'effet du dernier détail du poste) : égal à la source = conforme, égal à la règle = écart justifié | règle |
| `assignmentEndDate`, `termEndDate` | la plus ancienne entre DateSortiePoste et la fin de l'unité adm. (date d'effet du détail suivant − 1 jour si l'unité change ; sinon aucune). Vide attendu = vide trouvé | règle |
| `Enregistrement` | complétude : chaque affectation du système A doit exister dans B (et inversement) | règle |

L'application affiche ce catalogue avec les comptes réels (pastille **Glossaire** → « Règles appliquées »).

## Modèle entraîné
- **Algorithme** : `RandomForestClassifier(n_estimators=200, max_depth=6, class_weight="balanced", random_state=0)`, 13 variables (similarité des textes, forme, écart numérique ou en jours, stabilité de la correspondance A→B…).
- **Données d'entraînement** : verdicts sûrs des règles + cas synthétiques par perturbation + corrections d'experts (poids ×20). Pas de vérité terrain fournie : les scores sont indicatifs.
- **Reproduire / fournir le modèle** : `python corroboria.py` ré-entraîne à l'identique (graine fixe) et exporte `modele/modele_corroboria.joblib` (le modèle) et `modele/modele_corroboria.json` (fiche : variables, importances, nombre d'exemples). Un test vérifie que deux entraînements donnent les mêmes verdicts.

## Rapport et exports
- **Excel** (`python corroboria.py` → `outputs/rapport_corroboration.xlsx` ; un exemple est fourni dans [`docs/exemple_rapport_corroboration.xlsx`](docs/exemple_rapport_corroboration.xlsx)) : onglets Erreurs à investiguer, À relire, Écarts justifiés, Résumé par champ, Détail complet. Chaque ligne porte le verdict, la règle appliquée, l'origine, la confiance, la priorité, la cause probable et l'explication.
- **CSV depuis l'application** : bouton « Télécharger le tableau actuellement affiché - CSV » (séparateur `;`, UTF-8 avec BOM, s'ouvre dans Excel). Avec la pastille **Tout** : le rapport complet. Les colonnes incluent verdict, règle, explication, code d'emploi et type d'affectation pour investiguer.

## Retours d'experts et règles apprises (`retours.py`)
Dans le tableau, le statut d'une ligne se corrige avec la liste déroulante (une boîte de **confirmation** demande motif, commentaire et auteur).
- **Journal** `corrections.csv` : Matricule, Champ, Verdict, Motif, Commentaire, Auteur, Date, ValeurA, ValeurB, Regle, AncienVerdict. L'historique est conservé ; une correction s'annule dans la pastille **Corrections** (ligne « ANNULE »). L'ancien format à 3 colonnes reste lu.
- **Effets** : la correction remplace le verdict de la ligne (origine « expert ») et enrichit l'entraînement du modèle.
- **Règle apprise** : à partir de **3 corrections concordantes** (même champ, même « forme » des valeurs A et B où les chiffres deviennent `#`, même verdict, aucun contre-exemple), une règle est **proposée** ; l'expert la valide ou la rejette. Une règle validée (`regles_apprises.json`) s'applique aux écarts du même type (origine « règle apprise »), distincte des règles du mapping, et peut être désactivée. Une correction d'expert prime toujours sur une règle apprise. Rien n'est appliqué sans validation.
- **Effet mesurable** : « Mesurer l'effet » compare les verdicts avec et sans retours.

## Assistant (`assistant.py`)
Une bulle en bas à droite ouvre un assistant dans le bandeau violet. Il répond aux questions courantes (« Combien de vraies anomalies ? », « Quel employé a le plus d'anomalies ? », « C'est quoi positionName ? »…) et **pilote l'écran** (« Montre-moi les anomalies de l'employé X », « Mets le seuil à 95 », « Explique la ligne… »). Le code comprend la question et calcule sur les données : aucun chiffre ne vient d'un modèle. Lecture seule.

## Application (résumé ; détail dans le guide)
En-tête (logo, langue FR/EN) · **Tableau de bord** (anneau des verdicts, indicateurs, seuil de confiance, barre de revue humaine, histogramme de confiance, camemberts cause probable et employé) · **Données sélectionnées** (pastilles Conforme / Écart justifié / Vraie anomalie / À relire / Tout / Par champ / Glossaire / Corrections / Paramètres, tri par priorité, filtres type d'erreur, champ et employé, cases « Ok ? », statut modifiable, cloche d'aide IA, export CSV) · **Bandeau violet** (explication IA locale et assistant). Les réglages et les lignes vérifiées ne sont conservés que pendant la session ; les corrections d'experts et les règles apprises sont enregistrées dans les fichiers.

## Tests et démonstration
`python -m pytest -v` (une soixantaine de tests) sert aussi de script de démonstration, avec au minimum :
- un **cas conforme** : `test_cas_conforme` ;
- un **écart justifié automatiquement** : `test_ecart_justifie_encodage` (règle) et `test_ecart_justifie_courriel_dev_par_ia` (IA) ;
- une **vraie anomalie** : `test_vraie_anomalie_type_contrat`, `test_anomalie_heures`, `test_affectation_manquante_en_b`.

Le guide d'utilisation déroule la même démonstration dans l'application (section « Démonstration en trois cas »).

## Hypothèses et limites
- Dates de début (`assignmentStartDate`, `termStartDate`) : la source (`DateEntréePoste`) est la date d'effet du poste **uniquement** ; B inclut la règle transformée. Sur l'échantillon, B vaut `DateEntréePoste` ou, quand elle est postérieure, la date d'effet du dernier détail du poste : la règle codée est donc « la plus **récente** des deux » (déduite des données, alors que le mapping parle de « la plus ancienne »). Un B égal à cette valeur est un écart justifié ; toute autre date reste une vraie anomalie. **À confirmer avec les organisateurs.**
- Courriel et libellé de poste : préfixe `dev-` et noms différents traités comme artefacts d'anonymisation ; à revoir sur des données réelles.
- Pas de vérité terrain : l'exactitude n'a pu être mesurée que par cohérence avec les règles et par les tests. Sur l'échantillon (20 employés, 575 contrôles) : 508 conformes, 54 écarts justifiés, 13 vraies anomalies.
- Le modèle tranche les écarts ambigus de façon cohérente avec les règles ; il n'a pas prouvé qu'il détecte des anomalies que les règles manqueraient.
- Un LLM de 3 milliards de paramètres peut se tromper ; ses conseils sont à relire. Les temps de réponse sur CPU sont de 15 à 130 s.
- Champs non mappés (ex. `customAttribute_15`) ignorés, conformément à l'énoncé.
- Confidentialité : tout est local (pandas, scikit-learn, Ollama sur localhost) ; aucun appel réseau vers un service externe.
