"""Construit le guide d'utilisation (docs/guide_utilisation.html) : un seul fichier HTML, images intégrées (base64).

    python source/scripts/guide/capture_guide.py     # (re)génère les captures dans docs/img_guide/
    python source/scripts/guide/build_guide.py       # assemble docs/guide_utilisation.html
"""
import base64
import html
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
IMG = ROOT / "docs" / "img_guide"
SORTIE = ROOT / "docs" / "guide_utilisation.html"


def b64(chemin):
    return base64.b64encode(Path(chemin).read_bytes()).decode()


def fig(nom, legende, large=False):
    f = IMG / f"{nom}.png"
    if not f.exists():
        return f'<p class="manquant">[capture manquante : {nom}]</p>'
    return (f'<figure class="{"large" if large else ""}"><img src="data:image/png;base64,{b64(f)}" alt="{html.escape(legende)}">'
            f"<figcaption>{legende}</figcaption></figure>")


LOGO_LQ = b64(ROOT / "assets" / "logo-loto-quebec.png")
LOGO_CA = b64(ROOT / "assets" / "logo-corroborai.svg")

CSS = """
:root{--bleu:#1c5b8c;--turquoise:#479ea0;--violet:#8e6bbf;--violet-fonce:#4a2d80;--rouge:#d64545;--jaune:#e0b020;--vert:#2e9e5b;--orange:#e8892b;
 --texte:#1d2330;--gris:#5b6475;--fond:#f5f7fb;--carte:#fff;--bord:#dfe4ee}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;font-family:"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:var(--texte);background:var(--fond);line-height:1.6;font-size:16px}
header.hero{background:linear-gradient(135deg,var(--violet-fonce),var(--bleu) 55%,var(--turquoise));color:#fff;padding:42px 24px 38px}
.hero-in{max-width:1180px;margin:0 auto;display:flex;align-items:center;gap:22px;flex-wrap:wrap;justify-content:space-between}
.hero h1{margin:0;font-size:2.4rem;letter-spacing:-.02em}.hero p{margin:6px 0 0;opacity:.92;font-size:1.1rem;max-width:760px}
.hero img{height:54px;background:#fff;border-radius:10px;padding:6px 10px}
.layout{max-width:1180px;margin:0 auto;display:flex;gap:30px;padding:26px 18px 80px}
nav.toc{flex:0 0 250px;position:sticky;top:16px;align-self:flex-start;max-height:calc(100vh - 32px);overflow:auto;background:var(--carte);
 border:1px solid var(--bord);border-radius:12px;padding:14px 12px;font-size:.92rem}
nav.toc b{display:block;margin:0 0 8px 6px;color:var(--violet-fonce)}
nav.toc a{display:block;padding:5px 8px;border-radius:7px;color:var(--texte);text-decoration:none}
nav.toc a:hover{background:#eef1f8}nav.toc a.sub{padding-left:22px;color:var(--gris);font-size:.88rem}
main{flex:1;min-width:0}
section{background:var(--carte);border:1px solid var(--bord);border-radius:14px;padding:26px 30px;margin-bottom:22px}
h2{margin:0 0 6px;font-size:1.7rem;color:var(--violet-fonce);border-bottom:3px solid var(--turquoise);padding-bottom:8px;display:flex;gap:12px;align-items:center}
h2 .num{background:var(--violet-fonce);color:#fff;border-radius:50%;width:36px;height:36px;display:inline-flex;align-items:center;justify-content:center;font-size:1.05rem;flex:0 0 36px}
h3{margin:26px 0 6px;font-size:1.2rem;color:var(--bleu)}
p{margin:.55em 0}ul,ol{margin:.5em 0 .8em 1.2em;padding-left:.8em}li{margin:.25em 0}
code,kbd{background:#eef1f8;border:1px solid #dfe4ee;border-radius:5px;padding:1px 6px;font-family:Consolas,"Cascadia Code",monospace;font-size:.9em}
pre{background:#1d2330;color:#e8ecf5;border-radius:10px;padding:14px 16px;overflow:auto;font-size:.9rem;line-height:1.5}pre code{background:none;border:0;color:inherit;padding:0}
figure{margin:18px 0;text-align:center}figure img{max-width:100%;border:1px solid var(--bord);border-radius:10px;box-shadow:0 4px 18px rgba(20,30,60,.12);cursor:zoom-in}
figure.large img{width:100%}figcaption{margin-top:8px;color:var(--gris);font-size:.9rem;font-style:italic}
.manquant{background:#fff3cd;border:1px dashed #d4a017;border-radius:8px;padding:10px;text-align:center}
table{border-collapse:collapse;width:100%;margin:14px 0;font-size:.95rem}th,td{border:1px solid var(--bord);padding:8px 10px;text-align:left;vertical-align:top}
th{background:#eef1f8;color:var(--violet-fonce)}tr:nth-child(even) td{background:#fafbfe}
.pastille{display:inline-block;width:12px;height:12px;border-radius:50%;margin-right:6px;vertical-align:middle}
.astuce,.attention,.info,.exemple{border-left:5px solid;border-radius:9px;padding:11px 16px;margin:16px 0}
.astuce{background:#eaf7ef;border-color:var(--vert)}.attention{background:#fff1f0;border-color:var(--rouge)}
.info{background:#eaf2fb;border-color:var(--bleu)}.exemple{background:#f3eefb;border-color:var(--violet)}
.astuce::before,.attention::before,.info::before,.exemple::before{display:block;font-weight:700;margin-bottom:2px}
.astuce::before{content:"Astuce";color:var(--vert)}.attention::before{content:"Attention";color:var(--rouge)}
.info::before{content:"À savoir";color:var(--bleu)}.exemple::before{content:"Exemple";color:var(--violet-fonce)}
.etapes{counter-reset:e;list-style:none;margin-left:0;padding-left:0}.etapes li{counter-increment:e;position:relative;padding:8px 0 8px 46px;margin:6px 0}
.etapes li::before{content:counter(e);position:absolute;left:0;top:6px;width:32px;height:32px;border-radius:50%;background:var(--turquoise);color:#fff;
 display:flex;align-items:center;justify-content:center;font-weight:700}
.trois{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px;margin:16px 0}
.carte{border:1px solid var(--bord);border-radius:12px;padding:14px 16px;background:#fafbfe}.carte h4{margin:0 0 4px;color:var(--bleu)}
.verdicts td:first-child{white-space:nowrap;font-weight:600}
.flux{display:flex;gap:10px;align-items:stretch;flex-wrap:wrap;margin:16px 0}.flux div{flex:1;min-width:190px;border-radius:12px;padding:12px 14px;color:#fff}
.flux .n1{background:var(--bleu)}.flux .n2{background:var(--turquoise)}.flux .n3{background:var(--violet)}.flux b{display:block;margin-bottom:3px}
footer{text-align:center;color:var(--gris);padding:10px 0 40px;font-size:.9rem}
#zoom{display:none;position:fixed;inset:0;background:rgba(10,14,25,.9);z-index:99;align-items:center;justify-content:center;padding:20px;cursor:zoom-out}
#zoom img{max-width:96vw;max-height:94vh;border-radius:8px;background:#fff}
@media(max-width:900px){.layout{flex-direction:column}nav.toc{position:static;flex:none;width:100%;max-height:none}section{padding:18px}}
@media print{nav.toc,#zoom{display:none}.layout{display:block;padding:0}section{break-inside:avoid-page;border:0;padding:8px 0}body{background:#fff}header.hero{padding:16px}}
"""

JS = """
const z=document.getElementById('zoom'),zi=z.querySelector('img');
document.querySelectorAll('figure img').forEach(i=>i.addEventListener('click',()=>{zi.src=i.src;z.style.display='flex'}));
z.addEventListener('click',()=>z.style.display='none');document.addEventListener('keydown',e=>{if(e.key==='Escape')z.style.display='none'});
"""

SECTIONS = []  # (id, titre, sous-sections [(id, titre)], contenu)


def sec(id_, titre, contenu, sous=()):
    SECTIONS.append((id_, titre, list(sous), contenu))


# ====================================================================== 1
sec("objectif", "À quoi sert CorroborIA ?", f"""
<p>Une comparaison « identique / différent » entre le système <b>A – RH</b> (source de vérité) et le système <b>B – Temps</b> (cible) produit beaucoup
de fausses alertes : certaines différences sont <b>légitimes</b> (encodage, données de test anonymisées, règles métier). CorroborIA <b>automatise l'analyse
des écarts</b> pour que l'équipe fonctionnelle ne regarde que les <b>vraies anomalies</b>, avec, pour chaque verdict, <b>la règle appliquée et la justification</b>.</p>
<div class="flux">
<div class="n1"><b>1. Règles du mapping</b>Comparaison champ par champ avec les règles métier (déterministe, traçable).</div>
<div class="n2"><b>2. IA locale</b>Un modèle scikit-learn tranche les cas ambigus et donne un niveau de confiance.</div>
<div class="n3"><b>3. LLM local</b>Il explique en langage clair une ligne choisie. Il ne change jamais un verdict.</div></div>
<h3>Les quatre verdicts</h3>
<table class="verdicts"><tr><th>Verdict</th><th>Ce que ça veut dire</th><th>Qui l'a décidé</th></tr>
<tr><td><span class="pastille" style="background:var(--vert)"></span>Conforme</td><td>La valeur du système B est celle attendue d'après le système A.</td><td>Règle du mapping</td></tr>
<tr><td><span class="pastille" style="background:var(--jaune)"></span>Écart justifié</td><td>Les valeurs diffèrent mais une règle métier ou un artefact connu l'explique (encodage des accents, préfixe <code>dev-</code> des courriels, libellés anonymisés…).</td><td>Règle ou IA</td></tr>
<tr><td><span class="pastille" style="background:var(--rouge)"></span>Vraie anomalie</td><td>Écart non expliqué : à investiguer.</td><td>Règle (ou expert)</td></tr>
<tr><td><span class="pastille" style="background:var(--orange)"></span>À relire</td><td>La confiance est sous le seuil que vous fixez : un humain doit trancher.</td><td>Seuil de confiance</td></tr></table>
<p>Chaque verdict indique son <b>origine</b> : <b>règle</b> du mapping, <b>IA</b> locale, <b>expert</b> (correction manuelle) ou <b>règle apprise</b> (proposée par le système, validée par un expert).</p>
<div class="info">Tout reste sur votre machine : le modèle de classification et le LLM (Ollama) fonctionnent en local, aucune donnée n'est envoyée à un service externe. Les fichiers d'origine sont lus en <b>lecture seule</b>.</div>
<div class="exemple"><b>Parcours express (5 minutes)</b> :
<ol class="etapes"><li>Ouvrez l'application et cliquez sur <b>Lancer la corroboration</b>.</li><li>Lisez le <b>tableau de bord</b> : 575 contrôles, 88 % de conformité, 19 vraies anomalies.</li>
<li>Dans <b>Données sélectionnées</b>, cliquez la pastille <b>Vraie anomalie</b>.</li><li>Cliquez la <b>cloche</b> d'une ligne : l'IA locale explique l'écart dans le bandeau violet.</li>
<li>Posez une question à l'<b>assistant</b> (bulle en bas à droite) : « Combien de vraies anomalies ? ».</li></ol></div>
""")

# ====================================================================== 2
sec("demarrer", "Démarrer", f"""
<h3>Prérequis</h3>
<ul><li><b>Python 3.10+</b> et les dépendances du projet : <code>pip install -r requirements.txt</code>.</li>
<li><b>Ollama</b> (facultatif, pour les explications du LLM local) : installez-le depuis <code>ollama.com</code> puis téléchargez un modèle :</li></ul>
<pre><code>ollama pull qwen2.5:3b     # équilibré (par défaut)
ollama pull qwen2.5:1.5b   # rapide
ollama pull qwen2.5:7b     # précis (plus lent)</code></pre>
<p>Sans Ollama, tout fonctionne ; seules les explications rédigées par le LLM sont indisponibles (l'explication du moteur de règles reste affichée).
Si vous avez un <b>GPU NVIDIA</b>, Ollama l'utilise automatiquement.</p>
<h3>Lancer l'application</h3>
<pre><code>python -m streamlit run app.py</code></pre>
<p>Le navigateur s'ouvre sur <code>http://localhost:8501</code>. Au premier affichage, la barre latérale propose de charger les fichiers et le message invite à lancer la corroboration.</p>
{fig("01_accueil", "Écran d'accueil : en-tête (logo, interrupteur de langue FR/EN), barre latérale des données et bouton « Lancer la corroboration ».", True)}
<div class="astuce">Après une mise à jour du code, <b>redémarrez le serveur</b> (Ctrl+C puis la commande ci-dessus) : un ancien processus peut garder d'anciennes versions des modules en mémoire.</div>
""")

# ====================================================================== 3
sec("charger", "Charger les données et lancer", f"""
<p>La barre latérale (à gauche) regroupe les données et les réglages du LLM local.</p>
{fig("02_barre_laterale_avant", "Barre latérale : quatre emplacements de fichiers, le bouton de lancement, puis le choix du modèle d'explication.")}
<h3>Les quatre fichiers</h3>
<table><tr><th>Emplacement</th><th>Contenu</th></tr>
<tr><td>Système A – RH (Source)</td><td>Extraction des employés du système RH (Excel .xlsx ou CSV).</td></tr><tr><td>Système B – Temps (Destination)</td><td>Extraction du système de gestion des horaires et du temps.</td></tr>
<tr><td>Détail du poste</td><td>Complément du système RH (heures, dates d'effet) utilisé pour des jointures.</td></tr>
<tr><td>Motif de la situation d'emploi</td><td>Table de correspondance des motifs d'absence (codes Remphor).</td></tr></table>
<div class="info"><b>Par défaut</b>, les fichiers fournis dans le dossier <code>data/</code> sont utilisés : vous n'avez rien à charger. Pour analyser d'autres extractions, glissez-les dans l'emplacement correspondant.
Le fichier <code>Mapping.xlsx</code> (correspondances et règles) est lu dans <code>data/</code>.</div>
<ol class="etapes"><li>(Facultatif) Chargez vos fichiers .xlsx dans les emplacements.</li><li>Cliquez sur <b>Lancer la corroboration</b>.</li>
<li>Patientez quelques secondes : l'analyse des 575 contrôles de l'échantillon est très rapide.</li></ol>
{fig("03_bouton_lancer", "Le bouton rouge « Lancer la corroboration » démarre l'analyse.")}
<h3>Si un fichier n'est pas le bon</h3>
<p>L'application vérifie les colonnes attendues et affiche un message en français plutôt qu'une erreur technique :</p>
{fig("35_fichier_invalide", "Exemple : un fichier qui n'est pas la bonne extraction est refusé avec la liste des colonnes manquantes.")}
""")

# ====================================================================== 4
sec("tableau-de-bord", "Le tableau de bord", f"""
<p>Une fois l'analyse lancée, la page affiche deux encadrés de synthèse.</p>
{fig("04_vue_generale", "Vue générale après le lancement : tableau de bord, puis section « Données sélectionnées ».", True)}
<h3>Premier encadré : la répartition des verdicts</h3>
{fig("05_tableau_de_bord", "À gauche, l'anneau et sa légende ; à droite, les indicateurs clés.", True)}
<ul><li><b>Anneau</b> : 575 contrôles répartis en conformes, écarts justifiés, vraies anomalies et « à relire ». Survolez une part pour voir son effectif ; <b>cliquez</b> une part pour afficher ses lignes plus bas.</li>
<li><b>Conformité</b> : part des contrôles conformes (87 %).</li><li><b>À investiguer</b> : vraies anomalies et lignes à relire (21).</li>
<li><b>Employés / Concernés</b> : employés analysés (20) et employés ayant au moins une anomalie ou une ligne à relire (12).</li>
<li><b>Priorité n°1</b> : l'anomalie la plus urgente (champ, employé, score sur 100).</li><li><b>Champ le plus touché</b> et <b>Écarts tranchés par l'IA</b> avec la confiance générale du modèle.</li></ul>
<h3 id="seuil">Le seuil de confiance minimal</h3>
{fig("06_curseur_seuil", "Le curseur sous l'anneau règle le seuil de confiance (de 0 à 100 %, 90 % par défaut).")}
<p>Tout écart <b>non conforme</b> dont la confiance est <b>inférieure au seuil</b> passe dans « À relire » : l'anneau se met à jour en direct. Les écarts décidés par une règle ont 100 % de confiance ; seuls les écarts tranchés par le modèle sont concernés.</p>
<table><tr><th>Seuil</th><th>Conformes</th><th>Écarts justifiés</th><th>Vraies anomalies</th><th>À relire</th></tr>
<tr><td>50 %</td><td>464</td><td>48</td><td>19</td><td>0</td></tr><tr><td>90 % (défaut)</td><td>464</td><td>46</td><td>19</td><td>2</td></tr>
<tr><td>95 %</td><td>464</td><td>25</td><td>19</td><td>23</td></tr><tr><td>100 %</td><td>464</td><td>2</td><td>19</td><td>46</td></tr></table>
<div class="astuce">Relever le seuil rend l'outil plus prudent (plus de lignes à relire) ; l'abaisser fait confiance au modèle. Une <b>vraie anomalie</b> décidée par une règle n'est jamais envoyée en « À relire » (voir <a href="#parametres">Paramètres</a>).</div>
<h3>La barre de revue humaine</h3>
{fig("07_barre_revue_humaine", "La barre mesure l'avancement de la revue des lignes « À relire ».")}
<p>Elle compte les lignes « À relire » que vous avez cochées <b>« Ok ? »</b> sur le total. Son message évolue : « À vous de jouer », « Bon début », « On avance bien », « Presque fini », « Mission accomplie ». Les rayures n'animent la barre que lorsque la progression change.</p>
<h3>Deuxième encadré : confiance, causes et employés</h3>
{fig("08_histogramme_et_camemberts", "Histogramme des scores de confiance du modèle, camembert des causes probables et camembert des employés.", True)}
<ul><li><b>Histogramme « Confiance du modèle »</b> : de 0 à 100 % par tranches de 2,5 %. Rouge = vraies anomalies, orange = écarts justifiés, violet = à relire.</li>
<li><b>Cause probable</b> et <b>Employé</b> : camemberts avec un interrupteur <i>Vraie anomalie / Écart justifié</i> placé dessous. <b>Cliquez une part</b> pour filtrer le tableau (voir section suivante).</li></ul>
""", sous=[("seuil", "Le seuil de confiance")])

# ====================================================================== 5
sec("donnees", "Explorer : « Données sélectionnées »", f"""
<p>C'est le cœur de l'application : un tableau unique, piloté par des pastilles, des filtres et des clics sur les graphiques.</p>
{fig("09_donnees_selectionnees_defaut", "À l'ouverture, la pastille « À relire » est sélectionnée : le tableau montre les lignes à relire.", True)}
<h3>Les pastilles</h3>
{fig("10_pastilles", "La rangée « Afficher » : quatre statuts puis cinq vues. Les pastilles se combinent.")}
<table><tr><th>Pastille</th><th>Affiche</th></tr>
<tr><td>Conforme · Écart justifié · Vraie anomalie · À relire</td><td>Les lignes de ces statuts (plusieurs possibles à la fois).</td></tr>
<tr><td>Tout</td><td>Les 575 lignes : c'est le rapport complet.</td></tr><tr><td>Par champ</td><td>Un graphique des verdicts par champ et son tableau.</td></tr>
<tr><td>Glossaire</td><td>Les champs du mapping, les codes et les règles appliquées avec leurs comptes.</td></tr>
<tr><td>Corrections</td><td>Le journal des corrections d'experts, les règles proposées et apprises.</td></tr>
<tr><td>Paramètres</td><td>La relecture des vraies anomalies, les poids du score de priorité, la gravité par variable.</td></tr></table>
<div class="info">Cliquer une part de l'anneau du tableau de bord <b>coche aussi la pastille</b> du même statut (et la décoche en recliquant).</div>
{fig("11_vraies_anomalies", "Exemple : la pastille « Vraie anomalie » affiche les 19 lignes, triées par priorité décroissante.", True)}
<h3>Trier</h3>
<p>Sous les pastilles, le choix <b>Trier</b> propose « Priorité décroissante » (par défaut : les plus urgentes d'abord) ou « Priorité croissante ».</p>
<h3 id="filtres">Filtrer : type d'erreur, champ, employé</h3>
{fig("17_filtre_employe", "Filtre « Employé » : la ligne « Filtres actifs » rappelle ce qui filtre, avec le bouton « Réinitialiser les filtres ».", True)}
<ul><li><b>Type d'erreur</b> : la cause probable (menu déroulant). <b>Champ</b> : un ou plusieurs champs. <b>Employé</b> : un matricule précis.</li>
<li>Les filtres se <b>combinent entre eux et avec les pastilles</b> (ET logique).</li>
<li>Dès qu'un filtre existe, une ligne <b>« Filtres actifs »</b> l'affiche et un bouton <b>Réinitialiser les filtres</b> apparaît.</li></ul>
<h3>Filtrer en cliquant un camembert</h3>
{fig("18_clic_camembert", "Un clic sur une part du camembert « Cause probable » sélectionne cette cause (les autres parts s'estompent).")}
{fig("19_filtre_cause", "Le tableau ne montre plus que les lignes de la cause choisie, et le filtre est visible.", True)}
<div class="attention">Si le tableau semble vide, vérifiez les pastilles et les filtres actifs : ils s'ajoutent. Cliquez « Réinitialiser les filtres » ou cochez « Tout ».</div>
<h3>Les lignes conformes et les écarts justifiés</h3>
{fig("21_lignes_conformes", "La pastille « Conforme » : les contrôles dont la valeur du système B est celle attendue.")}
{fig("22_ecarts_justifies", "La pastille « Écart justifié » : écarts expliqués par une règle ou par le modèle (avec sa confiance).", True)}
<h3>Exporter</h3>
{fig("20_vue_tout_export", "Le bouton « Télécharger le tableau actuellement affiché - CSV » exporte exactement ce que vous voyez ; avec « Tout », c'est le rapport complet.", True)}
<p>Le fichier CSV (séparateur <code>;</code>, UTF-8 avec BOM) s'ouvre directement dans Excel. Il contient le verdict, la règle appliquée, l'explication, la confiance, la priorité, la cause probable, le code d'emploi et le type d'affectation.</p>
""", sous=[("filtres", "Filtres")])

# ====================================================================== 6
sec("lire", "Lire le tableau, colonne par colonne", f"""
{fig("12_tableau_detail", "Le tableau détaillé des vraies anomalies.", True)}
<table><tr><th>Colonne</th><th>Rôle</th></tr>
<tr><td>Cloche</td><td>Demande une explication à l'IA locale pour cette ligne (voir section suivante).</td></tr>
<tr><td><b>Ok ?</b></td><td>Case à cocher pour marquer la ligne comme vérifiée. Certaines cases sont <b>pré-cochées en gris</b> : écarts justifiés dont la confiance atteint le seuil, et vraies anomalies tant que l'option « relire » est sur Non.</td></tr>
<tr><td>Priorité</td><td>Score de 0 à 100 : gravité du champ (60 %), confiance (25 %), récurrence du champ (15 %). Réglable dans Paramètres.</td></tr>
<tr><td>Matricule · Champ</td><td>L'employé et le champ du mapping concernés.</td></tr><tr><td>Valeur A · Valeur B</td><td>Les deux valeurs comparées (système RH et système Temps).</td></tr>
<tr><td>Statut</td><td>Le verdict, en couleur. <b>Modifiable</b> par liste déroulante (icône crayon), avec confirmation.</td></tr>
<tr><td>Source du verdict</td><td>règle · IA · expert · règle apprise.</td></tr><tr><td>Confiance</td><td>100 % pour une règle ; probabilité du modèle pour l'IA.</td></tr>
<tr><td>Règle</td><td>La règle du mapping appliquée à ce contrôle (traçabilité).</td></tr>
<tr><td>Cause probable</td><td>Regroupe les écarts d'une même origine (ex. « B contient toujours 40 : valeur par défaut probable »). La colonne disparaît quand elle est vide.</td></tr></table>
<h3>Cloche, cases et statut</h3>
{fig("13_cloche", "La cloche grise à gauche de chaque ligne : un clic demande l'explication.")}
{fig("14_cases_ok", "La colonne « Ok ? » : coches grisées = pré-cochées automatiquement ; coches violettes = cochées par vous.")}
{fig("15_statut_modifiable", "Le statut est coloré selon sa valeur ; l'icône crayon indique qu'il est modifiable.")}
<div class="info">Survolez un en-tête, la cloche ou le statut : une infobulle explique à quoi ils servent.</div>
""")

# ====================================================================== 7
sec("ia", "Faire expliquer une ligne par l'IA locale", f"""
<p>Un clic sur la <b>cloche</b> d'une ligne ouvre le <b>bandeau violet</b> en bas de l'écran. Le LLM local y rédige une explication en trois phrases :
<i>Ce que c'est</i>, <i>Ce qu'on voit</i>, <i>À vérifier</i>.</p>
{fig("27_bandeau_explication", "Le bandeau « Explication IA locale » : la ligne concernée, le verdict et l'explication dans la zone blanche.", True)}
<ol class="etapes"><li>Cliquez la cloche : elle devient <b>violette</b> et la ligne est surlignée.</li><li>Patientez (de quelques secondes à environ 2 minutes sur processeur, selon le modèle) : <i>Ollama n'est appelé qu'à ce moment-là</i>.</li>
<li>Lisez l'explication ; le bouton <b>Fermer</b> referme le bandeau. Une explication déjà calculée est relue du cache, sans nouvel appel.</li></ol>
<h3>Comment l'IA comprend les données</h3>
<p>Pour que l'explication soit compréhensible, le code donne au LLM, pour la ligne choisie :</p>
<ul><li>la <b>fiche du champ</b> retrouvée dans le glossaire du mapping (description, colonne du système A, règle) et dans <code>glossaire_ia.json</code> (explication en langage courant, modifiable) ;</li>
<li>les <b>codes</b> traduits (JWN = permanent temps plein, WHX = occasionnel surnuméraire…) et les <b>valeurs décodées</b> (« 6900-Empl6900 » = emploi 6900, description Empl6900 ; préfixe <code>dev-08-v2_</code> = adresse d'un environnement de développement) ;</li>
<li>l'analyse du moteur et la cause probable, sans le jargon du modèle.</li></ul>
<div class="attention">Le LLM <b>ne change jamais un verdict</b>. Un petit modèle peut se tromper : relisez ses conseils. Si Ollama est absent ou ne répond pas, le bandeau affiche l'explication du moteur de règles et la commande à lancer pour installer le modèle.</div>
<h3>Choisir le modèle</h3>
{fig("33_barre_laterale_llm", "Dans la barre latérale : trois profils (Équilibré, Rapide, Précis), détection du GPU NVIDIA et choix CPU / automatique.")}
<table><tr><th>Profil</th><th>Modèle</th><th>Usage</th></tr><tr><td>Équilibré</td><td><code>qwen2.5:3b</code></td><td>Défaut, 15 à 40 s sur processeur.</td></tr>
<tr><td>Rapide</td><td><code>qwen2.5:1.5b</code></td><td>Environ deux fois plus rapide, français moins soigné.</td></tr><tr><td>Précis</td><td><code>qwen2.5:7b</code></td><td>Meilleure qualité (explique mieux les cas difficiles), 40 à 130 s sur processeur.</td></tr></table>
""")

# ====================================================================== 8
sec("correction", "Corriger un verdict (retour d'expert)", f"""
<p>Un expert fonctionnel peut <b>corriger le statut</b> d'une ligne directement dans le tableau, avec un justificatif.</p>
<ol class="etapes"><li>Cliquez la cellule <b>Statut</b> de la ligne : une liste déroulante propose « Vraie anomalie » et « Écart justifié ».</li>
<li>Choisissez la nouvelle valeur : une <b>boîte de confirmation</b> s'ouvre.</li><li>Indiquez le <b>motif</b>, un <b>commentaire</b> (facultatif) et votre nom, puis <b>Confirmer</b> (ou <b>Annuler</b> : rien n'est modifié).</li></ol>
{fig("16_confirmation_statut", "La confirmation demande le motif (artefact d'anonymisation, donnée source erronée, règle trop stricte, erreur confirmée, autre), un commentaire et l'auteur.", True)}
<h3>Ce que fait la correction</h3>
<ul><li>Elle est inscrite dans le <b>journal</b> <code>corrections.csv</code> avec la date, l'auteur, le motif, les valeurs A et B, la règle appliquée et l'ancien verdict. L'historique n'est jamais effacé.</li>
<li>Elle <b>remplace le verdict</b> de la ligne (origine « expert », confiance 100 %) et la ligne est marquée vérifiée.</li>
<li>Elle <b>enrichit l'entraînement</b> du modèle local (poids élevé) : les écarts semblables sont mieux classés aux analyses suivantes.</li>
<li>Elle peut être <b>annulée</b> depuis la pastille <b>Corrections</b>.</li></ul>
<div class="info">Une correction d'expert <b>prime toujours</b> sur une règle apprise et sur le verdict du modèle.</div>
""")

# ====================================================================== 9
sec("regles-apprises", "Les règles apprises", f"""
<p>Quand plusieurs experts corrigent le même type d'écart de la même façon, CorroborIA <b>propose une règle</b> qui s'applique aux écarts du même type. Rien n'est appliqué sans validation.</p>
{fig("26_corrections_vide", "La pastille « Corrections » avant toute correction : aucune règle proposée ; il faut 3 corrections concordantes.", True)}
<h3>Quand une règle est-elle proposée ?</h3>
<ul><li>Au moins <b>3 corrections concordantes</b> : même champ, même « forme » des valeurs A et B (les suites de chiffres sont remplacées par <code>#</code> : « 6585-Empl6585 » devient « #-Empl# »), même verdict ;</li>
<li><b>aucun contre-exemple</b> : si une correction contraire existe, aucune règle n'est proposée ;</li><li>et la règle n'a pas déjà été traitée (validée, rejetée ou désactivée).</li></ul>
<div class="exemple">Exemple de démonstration : l'expert juge trois fois qu'un libellé de poste différent est une <b>vraie erreur</b>. Le système propose la règle « positionName : A de forme <code>#-Empl#</code> et B de forme <code>#-Empl#</code> ⇒ Vraie anomalie ».</div>
{fig("36_regle_proposee", "Une règle est proposée avec le nombre de corrections concordantes et des exemples. Un avis s'affiche aussi au-dessus du tableau.", True)}
<ol class="etapes"><li>Lisez la règle proposée (champ, formes, verdict, exemples).</li><li><b>Valider la règle</b> : elle est enregistrée (<code>regles_apprises.json</code>) et appliquée au prochain affichage, avec l'origine « règle apprise ».</li>
<li>Ou <b>Rejeter</b> : elle n'est plus proposée. Une règle active peut être <b>désactivée</b> à tout moment.</li></ol>
{fig("37_regle_validee", "Après validation : la règle apparaît parmi les « Règles apprises actives » avec son auteur et sa date ; le journal garde les corrections.", True)}
<h3>Mesurer l'effet</h3>
{fig("38_effet_des_retours", "Le bouton « Mesurer l'effet » compare les verdicts avec et sans retours d'experts.", True)}
<p>Quatre indicateurs : lignes corrigées par un expert, verdicts changés par les règles apprises, verdicts changés par le modèle réentraîné, total des verdicts changés.</p>
<div class="info">Les règles apprises restent <b>distinctes des règles du mapping</b> (fournies par l'énoncé) : le verdict indique toujours « règle du mapping » ou « règle apprise ».</div>
""")

# ====================================================================== 10
sec("assistant", "L'assistant (chatbot)", f"""
<p>Une <b>bulle</b> en bas à droite ouvre un assistant dans le <b>bandeau violet</b>. Il répond aux questions courantes <b>et pilote l'écran</b>.</p>
{fig("28_bulle_assistant", "La bulle de l'assistant (en bas à droite) quand rien d'autre n'est ouvert.")}
{fig("29_assistant_ouvert", "L'assistant ouvert : message d'accueil et questions proposées sous forme de boutons cliquables.", True)}
<h3>Répondre</h3>
{fig("30_assistant_reponse", "Un clic sur « Combien de vraies anomalies ? » : réponse calculée sur les données, avec la répartition par champ.", True)}
<h3>Piloter l'écran</h3>
{fig("31_assistant_pilotage", "« Montre-moi les anomalies de l'employé 3712987 » règle la pastille et le filtre du tableau.", True)}
{fig("32_assistant_et_explication", "« Explique la ligne de l'employé… » filtre sur la ligne et ouvre l'explication de l'IA ; le chat et l'explication s'affichent côte à côte.", True)}
<table><tr><th>Vous pouvez demander</th><th>Exemples</th></tr>
<tr><td>Compter</td><td>« Combien de vraies anomalies ? » · « Combien d'écarts justifiés sur les courriels ? »</td></tr>
<tr><td>Trouver le plus touché</td><td>« Quel employé a le plus d'anomalies ? » · « Quel champ est le plus touché ? »</td></tr>
<tr><td>Afficher dans le tableau</td><td>« Montre-moi les anomalies de l'employé 3712987 » · « Affiche les à relire sur les heures »</td></tr>
<tr><td>Définir</td><td>« C'est quoi positionName ? » · « Que veut dire WHX ? »</td></tr>
<tr><td>Expliquer une ligne</td><td>« Explique la ligne de l'employé 3712987 sur contractTypeCode »</td></tr>
<tr><td>Régler</td><td>« Mets le seuil à 95 » · « Réinitialise les filtres »</td></tr><tr><td>Suivre l'avancement</td><td>« Où en suis-je ? » · « Combien reste-t-il à vérifier ? »</td></tr></table>
<ul><li>Le bouton <b>Assistant ▸ / ▾</b> du bandeau affiche ou masque le chat ; <b>Fermer</b> ferme tout et ramène la bulle.</li>
<li>Les <b>chiffres viennent toujours des données</b> : le code comprend la question et calcule ; le LLM n'intervient que pour expliquer une ligne.</li>
<li>L'assistant est en <b>lecture seule</b> : il ne modifie ni un statut ni une règle. Hors périmètre, il propose des questions cliquables.</li></ul>
""")

# ====================================================================== 11
sec("parametres", "Les paramètres", f"""
{fig("25_parametres", "La pastille « Paramètres » : relecture des vraies anomalies, poids du score de priorité, gravité par variable.", True)}
<h3>Relire les vraies anomalies sous le seuil</h3>
<p>Réponse <b>Oui</b> par défaut : une vraie anomalie dont la confiance est sous le seuil passe en « À relire (vraie anomalie) » et compte dans la barre de revue. Avec <b>Non</b>, une vraie anomalie reste une vraie anomalie même sous le seuil, et ses cases « Ok ? » sont pré-cochées.</p>
<h3>Score de priorité</h3>
<p>Trois curseurs règlent le poids de la <b>gravité du champ</b> (60 % par défaut), de la <b>confiance</b> (25 %) et de la <b>récurrence du champ</b> (15 %). Les poids sont normalisés : seule leur proportion compte. Le tableau, le tri et la « priorité n°1 » du tableau de bord suivent immédiatement.</p>
<h3>Gravité par variable</h3>
<p>Un tableau éditable donne à chaque champ un coefficient de 0 à 1 (1 = le plus prioritaire), par exemple <code>contractTypeCode</code> à 0,9 ou <code>contactEmail</code> à 0,3. « Rétablir les valeurs par défaut » remet tout à zéro.</p>
<div class="info">Les réglages de cet écran ne sont conservés que pendant la session.</div>
""")

# ====================================================================== 12
sec("vues", "Par champ et Glossaire", f"""
{fig("23_par_champ", "« Par champ » : les verdicts de chaque champ du mapping, en graphique et en tableau.", True)}
<p>Repérez d'un coup d'œil les champs qui concentrent les anomalies (ici <code>contractTypeCode</code>, les heures et les dates).</p>
{fig("24_glossaire", "« Glossaire » : champs du mapping, codes et règles appliquées avec leurs comptes (traçabilité).", True)}
<ul><li><b>Champs</b> : description, colonnes du système A et du système B, règle, lus dans <code>Mapping.xlsx</code>.</li><li><b>Codes</b> : signification de JWN, XFLR, WHX…, des types d'affectation P/A/S et des statuts.</li>
<li><b>Règles appliquées</b> : chaque règle, sa nature (déterministe ou cas ambigu confié à l'IA) et ses compteurs de contrôles, conformes et écarts.</li></ul>
""")

# ====================================================================== 13
sec("langue", "Changer de langue", f"""
<p>L'interrupteur à droite du titre bascule l'interface entre le <b>français</b> (drapeau FR) et l'<b>anglais</b> (drapeau EN). Le titre devient « CorroborAI ».</p>
{fig("34_interface_anglaise", "L'interface en anglais.", True)}
<div class="info">Les textes produits par le moteur (règle appliquée, explication, cause probable) et les explications du LLM restent en français.</div>
""")

# ====================================================================== 14
sec("rapport", "Rapports et modèle exportables", f"""
<h3>Depuis l'application</h3>
<p>Le bouton <b>« Télécharger le tableau actuellement affiché - CSV »</b> exporte la vue courante (avec la pastille <b>Tout</b>, le rapport complet).</p>
<h3>Rapport Excel complet</h3>
<pre><code>python corroboria.py</code></pre>
<p>Génère <code>outputs/rapport_corroboration.xlsx</code> avec les onglets <b>Erreurs à investiguer</b>, <b>À relire</b>, <b>Écarts justifiés</b>, <b>Résumé par champ</b> et <b>Détail complet</b>. Chaque ligne porte le verdict, la règle appliquée, l'origine, la confiance, la priorité, la cause probable et l'explication.</p>
<h3>Modèle entraîné</h3>
<p>La même commande ré-entraîne le modèle à l'identique (graine fixe) et exporte <code>modele/modele_corroboria.joblib</code> (le modèle) et <code>modele/modele_corroboria.json</code> (variables, importances, nombre d'exemples d'entraînement).</p>
""")

# ====================================================================== 15
sec("demo", "Démonstration en trois cas", f"""
<p>Cette démonstration montre, dans l'application, <b>un cas conforme</b>, <b>un écart justifié automatiquement</b> et <b>une vraie anomalie détectée</b>.</p>
<h3>Cas 1 – Un contrôle conforme</h3>
<ol class="etapes"><li>Cliquez la pastille <b>Conforme</b> (et décochez « À relire »).</li><li>Choisissez par exemple le champ <code>givenName</code> ou <code>personId</code> : la valeur du système B est celle attendue, la règle appliquée est « Prénom sans accents » ou « Matricule = personId », la confiance est de 100 %.</li></ol>
{fig("21_lignes_conformes", "Cas conforme : 508 contrôles sur 575 sont conformes.")}
<h3>Cas 2 – Un écart justifié automatiquement</h3>
<ol class="etapes"><li>Cliquez la pastille <b>Écart justifié</b>.</li><li>Prenez une ligne <code>contactEmail</code> : le système A contient <code>PNom1545850850@loto-quebec.com</code> et le système B <code>dev-08-v2_PNom10370370@loto-quebec.com</code>.</li>
<li>Le gabarit du courriel est respecté ; le préfixe <code>dev-</code> et les chiffres différents sont un <b>artefact d'environnement de développement</b> : le modèle conclut « écart justifié » avec une confiance d'environ 93 %.</li>
<li>Cliquez la cloche pour lire l'explication en langage clair.</li></ol>
{fig("22_ecarts_justifies", "Cas écart justifié : les courriels de développement et les libellés anonymisés sont reconnus comme acceptables.", True)}
<h3>Cas 3 – Une vraie anomalie</h3>
<ol class="etapes"><li>Cliquez la pastille <b>Vraie anomalie</b>.</li><li>Prenez la première ligne : <code>contractTypeCode</code> de l'employé 2762457, valeur A <code>JWN</code> (permanent temps plein), valeur B <code>WHX</code> (occasionnel surnuméraire).</li>
<li>La règle « type d'employé » attendait JWN : l'écart n'est expliqué par aucune règle, c'est une <b>vraie anomalie</b> (confiance 100 %, priorité 94/100).</li><li>Cliquez la cloche pour l'explication, puis cochez « Ok ? » une fois la ligne investiguée.</li></ol>
{fig("11_vraies_anomalies", "Cas vraie anomalie : les 19 anomalies sont classées par priorité.", True)}
<div class="exemple">Autres anomalies de l'échantillon : heures différentes de la norme du poste (35 h contre 40 h), dates de début de poste différentes, libellé de site différent, affectation absente du système Temps.</div>
""")

# ====================================================================== 16
sec("technique", "Notebook, tests et organisation du projet", f"""
<h3>Notebook de remise</h3>
<p><code>CorroborIA_remise.ipynb</code> explique l'exploration des données, les choix d'approche et les résultats (déjà exécuté) : règles, modèle, seuil, priorité, LLM, retours d'experts, assistant, exports et tests.</p>
<pre><code>jupyter notebook CorroborIA_remise.ipynb</code></pre>
<h3>Tests</h3>
<pre><code>python -m pytest -v</code></pre>
<p>Une soixantaine de tests couvrent un cas conforme, un écart justifié, une vraie anomalie, les règles métier, le LLM (sans Ollama), les retours d'experts, l'assistant, la robustesse (fichiers invalides) et la <b>non-modification des fichiers sources</b>.</p>
<h3>Fichiers principaux</h3>
<table><tr><th>Fichier</th><th>Rôle</th></tr><tr><td><code>app.py</code></td><td>Application Streamlit.</td></tr><tr><td><code>corroboria.py</code></td><td>Moteur de règles, rapport Excel, glossaire.</td></tr>
<tr><td><code>ia.py</code></td><td>Modèle scikit-learn, priorité, effet des retours.</td></tr><tr><td><code>llm.py</code></td><td>LLM local : fiche du champ, prompt, cache.</td></tr>
<tr><td><code>retours.py</code></td><td>Journal des corrections, règles apprises.</td></tr><tr><td><code>assistant.py</code></td><td>Chatbot.</td></tr>
<tr><td><code>glossaire_ia.json</code></td><td>Explications en langage courant des champs (modifiable).</td></tr><tr><td><code>corrections.csv</code>, <code>regles_apprises.json</code></td><td>Retours d'experts.</td></tr></table>
<p>Pour régénérer ce guide : <code>python source/scripts/guide/capture_guide.py</code> puis <code>python source/scripts/guide/build_guide.py</code>.</p>
""")

# ====================================================================== 17
sec("depannage", "Dépannage et questions fréquentes", f"""
<table><tr><th>Problème</th><th>Solution</th></tr>
<tr><td>Message « Impossible d'analyser les fichiers »</td><td>Lisez le détail : colonnes manquantes ou fichier non Excel. Rechargez la bonne extraction à l'emplacement indiqué.</td></tr>
<tr><td>Erreur « unexpected keyword argument » après une mise à jour</td><td>Redémarrez le serveur Streamlit : d'anciens modules restent en mémoire.</td></tr>
<tr><td>« Le LLM n'a pas répondu »</td><td>Ollama est arrêté, le modèle n'est pas installé ou la réponse est trop lente. Lancez <code>ollama pull qwen2.5:3b</code> (le message indique la commande).</td></tr>
<tr><td>Les explications sont lentes</td><td>Normal sur processeur. Choisissez « Rapide », ou utilisez un GPU NVIDIA (détecté automatiquement).</td></tr>
<tr><td>Le tableau est vide</td><td>Des filtres ou des pastilles s'ajoutent : cliquez « Réinitialiser les filtres » ou cochez « Tout ».</td></tr>
<tr><td>Mes coches « Ok ? » ont disparu</td><td>Elles sont conservées pendant la session seulement ; les corrections d'expert, elles, sont enregistrées.</td></tr>
<tr><td>Une correction d'expert est erronée</td><td>Pastille <b>Corrections</b> → choisissez-la → <b>Annuler la correction</b> (l'historique reste).</td></tr>
<tr><td>Où sont mes corrections ?</td><td>Dans <code>corrections.csv</code> (journal) et <code>regles_apprises.json</code> (règles validées), à la racine du projet.</td></tr></table>
<h3>Limites à connaître</h3>
<ul><li>Aucune vérité terrain n'est fournie : les niveaux de confiance sont indicatifs.</li><li>La règle « date la plus ancienne entre DateEntréePoste et la date d'effet de l'unité administrative » est <b>désactivée</b> (elle donne une date antérieure pour tout l'échantillon) : à confirmer avec les organisateurs.</li>
<li>Un LLM de 3 milliards de paramètres peut se tromper ; ses conseils sont à relire.</li></ul>
""")

# ====================================================================== 18
sec("glossaire-termes", "Mini-glossaire", f"""
<table><tr><th>Terme</th><th>Signification</th></tr>
<tr><td>Corroboration</td><td>Comparaison des données entre le système A (RH) et le système B (Temps).</td></tr><tr><td>Écart justifié</td><td>Différence légitime, expliquée par une règle métier ou un artefact connu.</td></tr>
<tr><td>Vraie anomalie</td><td>Différence non expliquée, à investiguer.</td></tr><tr><td>Confiance</td><td>Probabilité du verdict : 100 % pour une règle, estimée par le modèle pour l'IA.</td></tr>
<tr><td>Seuil</td><td>Confiance minimale en dessous de laquelle une ligne passe en « À relire ».</td></tr><tr><td>Priorité</td><td>Score 0-100 qui ordonne les anomalies à investiguer.</td></tr>
<tr><td>Cause probable</td><td>Regroupement des écarts partageant la même origine.</td></tr><tr><td>Règle apprise</td><td>Règle proposée après 3 corrections concordantes d'experts et validée par un expert.</td></tr>
<tr><td>LLM</td><td>Modèle de langage local (Ollama) qui rédige les explications.</td></tr><tr><td>Mapping</td><td>Fichier de correspondance des champs et des règles entre les deux systèmes.</td></tr></table>
""")


def construire():
    toc = ['<nav class="toc"><b>Sommaire</b>']
    corps = []
    for i, (id_, titre, sous, contenu) in enumerate(SECTIONS, 1):
        toc.append(f'<a href="#{id_}">{i}. {titre}</a>')
        toc += [f'<a class="sub" href="#{sid}">{stitre}</a>' for sid, stitre in sous]
        corps.append(f'<section id="{id_}"><h2><span class="num">{i}</span>{titre}</h2>{contenu}</section>')
    toc.append("</nav>")
    page = f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CorroborIA – Guide d'utilisation</title><style>{CSS}</style></head><body>
<header class="hero"><div class="hero-in"><div><h1>CorroborIA – Guide d'utilisation</h1>
<p>Corroboration intelligente entre le système A (RH) et le système B (Temps) : comparer, justifier les écarts, ne retenir que les vraies anomalies.</p></div>
<img src="data:image/png;base64,{LOGO_LQ}" alt="Loto-Québec"></div></header>
<div class="layout">{''.join(toc)}<main>{''.join(corps)}<footer>CorroborIA · guide généré le {date.today().strftime('%d/%m/%Y')} · captures réalisées sur l'application avec les données fournies</footer></main></div>
<div id="zoom"><img alt=""></div><script>{JS}</script></body></html>"""
    SORTIE.write_text(page, encoding="utf-8")
    manquantes = [n for n in __import__("re").findall(r"capture manquante : ([\w]+)", page)]
    print("guide :", SORTIE, f"{SORTIE.stat().st_size / 1e6:.1f} Mo", "| captures manquantes :", manquantes or "aucune")


if __name__ == "__main__":
    construire()
