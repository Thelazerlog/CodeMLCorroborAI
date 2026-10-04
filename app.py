"""Application CorroborIA : streamlit run app.py"""
import base64
import hashlib
import io
import unicodedata
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
from PIL import Image, ImageChops

import corroboria
import ia
import llm
import retours

HERE = Path(__file__).parent
ASSETS = HERE / "assets"
IMG = (".png", ".jpg", ".jpeg", ".webp", ".svg")


def find_logo(*needles):
    """Premier fichier image de assets/ dont le nom contient l'un des mots (sans accents ni casse)."""
    norm = lambda s: unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()
    for f in sorted(ASSETS.iterdir()):
        if f.suffix.lower() in IMG and any(n in norm(f.name) for n in needles):
            return f
    return None


def trimmed(path):
    """Logo sans marge : un SVG est rogné via son viewBox (déjà fait), un raster via PIL."""
    if path.suffix.lower() == ".svg":
        return str(path)
    im = Image.open(path).convert("RGBA")
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
    box = ImageChops.difference(Image.alpha_composite(bg, im).convert("RGB"), bg.convert("RGB")).getbbox()
    return im.crop(box) if box else im


LOGO = find_logo("corrobor")            # logo du projet
LOGO_LQ = find_logo("loto", "quebec")   # logo Loto-Québec (dans assets/)

st.set_page_config(page_title="CorroborIA", page_icon=trimmed(LOGO) if LOGO else None, layout="wide",
                   initial_sidebar_state="expanded")

# ------------------------------------------------------------------ langue (fr / en)
TR = {
    "fr": {
        "Conforme": "Conforme", "ECART_JUSTIFIE": "Écart justifié", "ERREUR": "Vraie anomalie", "A_REVUE_HUMAINE": "À relire",
        "data": "Données", "data_cap": "Par défaut, les fichiers fournis dans le dossier sont utilisés. Les fichiers sont lus en lecture seule.",
        "up_source": "Système A – RH (Source)", "up_dest": "Système B – Temps (Destination)", "up_detail": "Détail du poste",
        "up_motif": "Motif de la situation d'emploi", "run": "Lancer la corroboration",
        "llm": "LLM local", "llm_model": "Modèle d'explication",
        "llm_help": "Utilisé uniquement quand tu cliques sur « Expliquer ». Aucune donnée ne quitte la machine.",
        "not_installed": " – non installé", "ollama_off": "Ollama est arrêté ou injoignable : l'explication LLM est désactivée.",
        "ollama_pull": "Pour l'installer : `ollama pull {m}`",
        "side_note": "Règles du mapping = verdict déterministe. IA locale (scikit-learn) = cas ambigus. Aucune donnée ne quitte la machine.",
        "spinner": "Corroboration en cours…",
        "welcome": "Charge tes fichiers (ou garde ceux par défaut) puis clique sur **Lancer la corroboration**.",
        "fail": "Impossible d'analyser les fichiers : {e}",
        "dashboard": "Tableau de bord", "investigate": "Investiguer les données",
        "verdict": "Verdict", "count": "Nombre", "share": "Part", "checks": "contrôles",
        "k_compl": "Conformité", "k_compl_h": "Part des contrôles conformes à la règle du mapping.",
        "k_inv": "À investiguer", "k_inv_h": "Vraies anomalies et cas à relire par un humain.",
        "k_emp": "Employés", "k_emp_h": "Employés analysés.",
        "k_conc": "Concernés", "k_conc_h": "Employés ayant au moins une erreur ou un cas à revoir.",
        "no_err": "Aucune erreur à investiguer.",
        "top1": "**Priorité n°1** : `{c}`, employé {m} ({p}/100)", "top_field": "**Champ le plus touché** : `{c}` ({n} cas)",
        "by_ai": "**Écarts tranchés par l'IA** : {a} (confiance générale du modèle : **{c}**)",
        "dl_xlsx": "Rapport Excel", "dl_all": "CSV – tout", "dl_err": "CSV – à investiguer", "dl_just": "CSV – justifiés",
        "tab_inv": "Vraie anomalie", "tab_just": "Écarts justifiés", "tab_field": "Par champ", "tab_all": "Tout",
        "tab_gloss": "Glossaire", "tab_set": "Paramètres",
        "f_field": "Filtrer par champ", "f_emp": "Filtrer par matricule",
        "prio_help": "Score 0-100 : gravité du champ ({g:.0%}), confiance ({c:.0%}), récurrence du champ ({r:.0%}). Réglable dans Paramètres.",
        "why": "Pourquoi ce verdict ?", "pick": "Choisis une ligne", "row": "{m} · {c} · priorité {p}",
        "val_a": "Valeur Système A", "val_b": "Valeur Système B",
        "verdict_line": "**Verdict** : {d} {l} — origine : `{o}` — confiance {c:.0%}",
        "rule_line": "**Règle appliquée** : {x}", "expl_line": "**Explication** : {x}",
        "btn_llm": "Expliquer avec le LLM local ({m})", "btn_llm_h": "Appel au modèle sur ta machine (plusieurs secondes sans GPU) ; résultat mis en cache.",
        "llm_spin": "Le LLM local rédige l'explication…",
        "llm_none": "Le LLM n'a pas répondu (Ollama arrêté, modèle absent ou trop lent). Pour installer le modèle : ollama pull {m}. Explication par gabarit conservée.",
        "llm_expl": "**Explication LLM local ({m})** : {x}", "cause": "**Cause probable** : {x}",
        "all_checks": "Toutes les vérifications de cet employé",
        "expert": "**Retour d'expert** : corriger ce verdict (appris aux prochaines exécutions)",
        "correct": "Verdict correct", "save_corr": "Enregistrer la correction",
        "just_cap": "Différences acceptables : une règle métier ou un artefact connu les explique.",
        "gloss_cap": "Champs corroborés (d'après le fichier de mapping) et codes utilisés.", "codes": "Codes", "gloss_fields": "Champs",
        "code": "Code", "meaning": "Signification",
        "set_title": "Score de priorité", "set_intro": "Le score (0-100) des erreurs est : gravité du champ × poids + confiance × poids + récurrence × poids. "
                    "Les poids sont normalisés (leur somme est ramenée à 100 %). Les changements s'appliquent immédiatement au tableau de bord et aux tableaux.",
        "w_gravite": "Gravité du champ", "w_confiance": "Confiance du verdict", "w_recurrence": "Récurrence du champ",
        "w_norm": "Poids effectifs après normalisation : gravité {g:.0%} · confiance {c:.0%} · récurrence {r:.0%}",
        "sev_title": "Gravité par variable", "sev_intro": "Coefficient de 0 à 1 par champ (1 = le plus prioritaire). Modifie directement dans le tableau.",
        "sev_col": "Gravité (0-1)", "reset": "Rétablir les valeurs par défaut",
        "hist_title": "Confiance du modèle", "cause_title": "Cause probable", "emp_title": "Employé", "others": "Autres", "unspecified": "Non précisée",
        "conf_axis": "Confiance", "gpu_found": "GPU NVIDIA détecté : {g}", "gpu_none": "Aucun GPU NVIDIA détecté : calcul sur CPU.",
        "device": "Calcul", "dev_auto": "Automatique (GPU si disponible)", "dev_cpu": "CPU seulement", "on_proc": "Calculé sur : {p}",
        "click_hint": "Clique sur une part de l'anneau ou d'un camembert, ou choisis une pastille, pour afficher les lignes correspondantes.", "rows_of": "{n} lignes : {l}",
        "selected": "Données sélectionnées", "fun": ["À vous de jouer", "Bon début", "On avance bien", "Plus qu'un petit effort", "Presque fini", "Mission accomplie"],
        "fun_lbl": "Revue humaine", "rev_title": "Relecture", "rev_opt": "Relire les vraies anomalies sous le seuil de confiance",
        "rev_help": "Non : une vraie anomalie n'est jamais à relire (elle ne compte pas dans « À faire »). Oui : sous le seuil de confiance, elle passe en « À relire » et compte dans « À faire ».",
        "yes": "Oui", "no": "Non", "pick_pills": "Afficher", "and_cause": "cause", "and_emp": "employé",
        "sort_lbl": "Trier", "sort_desc": "Priorité décroissante", "sort_asc": "Priorité croissante",
        "dl_cur": "Télécharger le tableau actuellement affiché - CSV", "v_todo": "À vérifier", "v_all": "Tout", "v_field": "Par champ", "v_gloss": "Glossaire", "v_set": "Paramètres",
        "aide_ia": "Aide IA", "aide_help": "Appeler l'IA à l'aide : explication de la ligne par le LLM local (clic sur le symbole).",
        "statut_help": "Le statut peut être modifié depuis la liste déroulante (une confirmation est demandée). Cela remplace la revue de l'expert.",
        "conf_title": "Confirmer le changement de statut", "conf_ok": "Confirmer", "conf_no": "Annuler",
        "conf_txt": "Changer le statut de **{m}** · `{c}` de « {a} » à « {b} » ? La correction est enregistrée dans corrections.csv et apprise aux prochaines exécutions.",
        "conf_bad": "Seuls « Vraie anomalie » et « Écart justifié » peuvent être choisis.", "ban_title": "Explication IA locale",
        "ban_close": "Fermer", "ban_fallback": "Explication du moteur (le LLM local n'a pas répondu) :",
        "flt_cause": "Type d'erreur", "flt_emp": "Employé", "flt_all": "Tous", "flt_reset": "Réinitialiser les filtres", "flt_active": "Filtres actifs",
        "v_cor": "Corrections", "motif": "Motif de la correction", "commentaire": "Commentaire (facultatif)", "auteur": "Auteur",
        "motifs": {"artefact_anonymisation": "Artefact d'anonymisation", "donnee_source_erronee": "Donnée source erronée",
                   "regle_trop_stricte": "Règle trop stricte", "erreur_confirmee": "Erreur confirmée", "autre": "Autre"},
        "cor_notice": "{n} règle(s) apprise(s) proposée(s) : ouvre « Corrections » pour les valider ou les rejeter.",
        "cor_prop": "Règles proposées", "cor_prop_none": "Aucune règle proposée : il faut {n} corrections concordantes (même champ, mêmes formes de valeurs A et B, même verdict, sans contre-exemple).",
        "cor_prop_txt": "**{c}** : si la valeur A a la forme « {fa} » et la valeur B la forme « {fb} », alors **{v}** ({n} corrections concordantes, par exemple {ex}).",
        "cor_valider": "Valider la règle", "cor_rejeter": "Rejeter", "cor_actives": "Règles apprises actives",
        "cor_none_act": "Aucune règle apprise active.", "cor_desact": "Désactiver la règle {i}",
        "cor_regle_txt": "`{i}` · **{c}** : A « {fa} » / B « {fb} » → {v} ({n} corrections, validée par {a} le {d})",
        "cor_journal": "Journal des corrections", "cor_pick": "Correction à annuler", "cor_annuler": "Annuler la correction",
        "cor_effet": "Effet des retours d'experts", "cor_mesurer": "Mesurer l'effet",
        "cor_m1": "Lignes corrigées par un expert", "cor_m2": "Verdicts changés par les règles apprises",
        "cor_m3": "Verdicts du modèle changés (entraînement)", "cor_m4": "Verdicts changés au total",
        "todo_title": "À faire", "scope": "Données à investiguer", "todo_n": "Lignes à investiguer", "todo_left": "Restantes",
        "seuil": "Seuil de confiance minimal", "seuil_help": "En dessous de ce seuil, une validation humaine est nécessaire.",
        "todo_cap": "À investiguer : toutes les erreurs et cas à revoir, plus les écarts justifiés par l'IA dont la confiance est sous le seuil.",
        "progress": "{d} vérifiées sur {n}", "next_title": "Premières lignes à vérifier", "all_done": "Tout est vérifié.",
        "ver_help": "À cocher quand la ligne a été vérifiée. Cochée automatiquement (cellule grise) quand la confiance atteint le seuil.",
        "mark": "Marquer comme vérifié", "opened": "Ligne ouverte dans « Investiguer les données » plus bas.", "ver_col": "Vérifié",
        "cols": {},
        "src": {"règle": "règle", "IA": "IA", "expert": "expert", "règle apprise": "règle apprise"},
        "free_text": "",
    },
    "en": {
        "Conforme": "Compliant", "ECART_JUSTIFIE": "Justified gap", "ERREUR": "True anomaly", "A_REVUE_HUMAINE": "To review",
        "data": "Data", "data_cap": "By default, the files provided in the folder are used. Files are read-only.",
        "up_source": "System A – HR (source)", "up_dest": "System B – Time (target)", "up_detail": "Position detail",
        "up_motif": "Employment status reason", "run": "Run the corroboration",
        "llm": "Local LLM", "llm_model": "Explanation model",
        "llm_help": "Only used when you click \"Explain\". No data leaves the machine.",
        "not_installed": " – not installed", "ollama_off": "Ollama is stopped or unreachable: LLM explanation is disabled.",
        "ollama_pull": "To install it: `ollama pull {m}`",
        "side_note": "Mapping rules = deterministic verdict. Local AI (scikit-learn) = ambiguous cases. No data leaves the machine.",
        "spinner": "Corroboration in progress…",
        "welcome": "Load your files (or keep the default ones), then click **Run the corroboration**.",
        "fail": "Unable to analyse the files: {e}",
        "dashboard": "Dashboard", "investigate": "Investigate the data",
        "verdict": "Verdict", "count": "Count", "share": "Share", "checks": "checks",
        "k_compl": "Compliance", "k_compl_h": "Share of checks compliant with the mapping rule.",
        "k_inv": "To investigate", "k_inv_h": "Confirmed anomalies and cases to review.",
        "k_emp": "Employees", "k_emp_h": "Employees analysed.",
        "k_conc": "Affected", "k_conc_h": "Employees with at least one error or case to review.",
        "no_err": "No error to investigate.",
        "top1": "**Top priority**: `{c}`, employee {m} ({p}/100)", "top_field": "**Most affected field**: `{c}` ({n} cases)",
        "by_ai": "**Gaps decided by AI**: {a} (overall model confidence: **{c}**)",
        "dl_xlsx": "Excel report", "dl_all": "CSV – all", "dl_err": "CSV – to investigate", "dl_just": "CSV – justified",
        "tab_inv": "True anomaly", "tab_just": "Justified gaps", "tab_field": "By field", "tab_all": "All",
        "tab_gloss": "Glossary", "tab_set": "Settings",
        "f_field": "Filter by field", "f_emp": "Filter by employee ID",
        "prio_help": "Score 0-100: field severity ({g:.0%}), confidence ({c:.0%}), field recurrence ({r:.0%}). Adjustable in Settings.",
        "why": "Why this verdict?", "pick": "Pick a row", "row": "{m} · {c} · priority {p}",
        "val_a": "System A value", "val_b": "System B value",
        "verdict_line": "**Verdict**: {d} {l} — origin: `{o}` — confidence {c:.0%}",
        "rule_line": "**Rule applied**: {x}", "expl_line": "**Explanation**: {x}",
        "btn_llm": "Explain with the local LLM ({m})", "btn_llm_h": "Calls the model on your machine (several seconds without GPU); result is cached.",
        "llm_spin": "The local LLM is writing the explanation…",
        "llm_none": "The LLM did not answer (Ollama stopped, model missing or too slow). To install the model: ollama pull {m}. Template explanation kept.",
        "llm_expl": "**Local LLM explanation ({m})**: {x}", "cause": "**Probable cause**: {x}",
        "all_checks": "All checks for this employee",
        "expert": "**Expert feedback**: correct this verdict (learned on next runs)",
        "correct": "Correct verdict", "save_corr": "Save the correction",
        "just_cap": "Acceptable differences: a business rule or a known artefact explains them.",
        "gloss_cap": "Corroborated fields (from the mapping file) and codes used.", "codes": "Codes", "gloss_fields": "Fields",
        "code": "Code", "meaning": "Meaning",
        "set_title": "Priority score", "set_intro": "The score (0-100) of errors is: field severity × weight + confidence × weight + recurrence × weight. "
                    "Weights are normalised (their sum is brought back to 100%). Changes apply immediately to the dashboard and tables.",
        "w_gravite": "Field severity", "w_confiance": "Verdict confidence", "w_recurrence": "Field recurrence",
        "w_norm": "Effective weights after normalisation: severity {g:.0%} · confidence {c:.0%} · recurrence {r:.0%}",
        "sev_title": "Severity by variable", "sev_intro": "Coefficient from 0 to 1 per field (1 = highest priority). Edit directly in the table.",
        "sev_col": "Severity (0-1)", "reset": "Restore default values",
        "hist_title": "Model confidence", "cause_title": "Probable cause", "emp_title": "Employee", "others": "Others", "unspecified": "Unspecified",
        "conf_axis": "Confidence", "gpu_found": "NVIDIA GPU detected: {g}", "gpu_none": "No NVIDIA GPU detected: running on CPU.",
        "device": "Compute", "dev_auto": "Automatic (GPU if available)", "dev_cpu": "CPU only", "on_proc": "Computed on: {p}",
        "click_hint": "Click a slice of the ring or of a pie, or pick a pill, to display the matching rows.", "rows_of": "{n} rows: {l}",
        "selected": "Selected data", "fun": ["Your move", "Good start", "Making progress", "Just a little more", "Almost done", "Mission accomplished"],
        "fun_lbl": "Human review", "rev_title": "Review", "rev_opt": "Re-read true anomalies below the confidence threshold",
        "rev_help": "No: a true anomaly is never re-read (it does not count in \"To do\"). Yes: below the confidence threshold, it becomes \"To review\" and counts in \"To do\".",
        "yes": "Yes", "no": "No", "pick_pills": "Show", "and_cause": "cause", "and_emp": "employee",
        "sort_lbl": "Sort", "sort_desc": "Highest priority first", "sort_asc": "Lowest priority first",
        "dl_cur": "Download the table currently displayed - CSV", "v_todo": "To check", "v_all": "All", "v_field": "By field", "v_gloss": "Glossary", "v_set": "Settings",
        "aide_ia": "AI help", "aide_help": "Call the AI for help: the local LLM explains the row (click the symbol).",
        "statut_help": "The status can be changed from the drop-down list (a confirmation is requested). This replaces the expert review.",
        "conf_title": "Confirm the status change", "conf_ok": "Confirm", "conf_no": "Cancel",
        "conf_txt": "Change the status of **{m}** · `{c}` from \"{a}\" to \"{b}\"? The correction is saved in corrections.csv and learned on the next runs.",
        "conf_bad": "Only \"True anomaly\" and \"Justified gap\" can be chosen.", "ban_title": "Local AI explanation",
        "ban_close": "Close", "ban_fallback": "Engine explanation (the local LLM did not answer):",
        "flt_cause": "Error type", "flt_emp": "Employee", "flt_all": "All", "flt_reset": "Reset filters", "flt_active": "Active filters",
        "v_cor": "Corrections", "motif": "Reason for the correction", "commentaire": "Comment (optional)", "auteur": "Author",
        "motifs": {"artefact_anonymisation": "Anonymisation artefact", "donnee_source_erronee": "Wrong source data",
                   "regle_trop_stricte": "Rule too strict", "erreur_confirmee": "Confirmed error", "autre": "Other"},
        "cor_notice": "{n} learned rule(s) proposed: open \"Corrections\" to validate or reject them.",
        "cor_prop": "Proposed rules", "cor_prop_none": "No rule proposed: {n} concordant corrections are needed (same field, same value shapes for A and B, same verdict, no counter-example).",
        "cor_prop_txt": "**{c}**: if value A has the shape \"{fa}\" and value B the shape \"{fb}\", then **{v}** ({n} concordant corrections, e.g. {ex}).",
        "cor_valider": "Validate the rule", "cor_rejeter": "Reject", "cor_actives": "Active learned rules",
        "cor_none_act": "No active learned rule.", "cor_desact": "Deactivate rule {i}",
        "cor_regle_txt": "`{i}` · **{c}**: A \"{fa}\" / B \"{fb}\" → {v} ({n} corrections, validated by {a} on {d})",
        "cor_journal": "Corrections journal", "cor_pick": "Correction to cancel", "cor_annuler": "Cancel the correction",
        "cor_effet": "Effect of expert feedback", "cor_mesurer": "Measure the effect",
        "cor_m1": "Rows corrected by an expert", "cor_m2": "Verdicts changed by learned rules",
        "cor_m3": "Model verdicts changed (training)", "cor_m4": "Verdicts changed in total",
        "todo_title": "To do", "scope": "Data to investigate", "todo_n": "Rows to investigate", "todo_left": "Remaining",
        "seuil": "Minimum confidence threshold", "seuil_help": "Below this threshold, human validation is required.",
        "todo_cap": "To investigate: all errors and review cases, plus AI-justified gaps whose confidence is below the threshold.",
        "progress": "{d} verified out of {n}", "next_title": "First rows to check", "all_done": "Everything is verified.",
        "ver_help": "Tick once the row has been checked. Ticked automatically (grey cell) when confidence reaches the threshold.",
        "mark": "Mark as verified", "opened": "Row opened in \"Investigate the data\" below.", "ver_col": "Verified",
        "cols": {"Vérifié": "Ok?", "Priorité": "Priority", "Matricule": "Employee ID", "Champ": "Field", "ValeurSourceA": "System A value",
                 "ValeurDestB": "System B value", "Statut": "Status", "Source_verdict": "Decided by",
                 "Confiance": "Confidence", "Cause_probable": "Probable cause", "Règle": "Rule",
                 "Explication": "Explanation", "CodeEmploi": "Job code", "TypeAffectation": "Assignment type"},
        "src": {"règle": "rule", "IA": "AI", "expert": "expert", "règle apprise": "learned rule"},
        "free_text": "Rule, explanation and cause texts are generated in French by the engine.",
    },
}
lang = "en" if st.session_state.get("lang_en") else "fr"  # interrupteur FR / EN


def t(key, **kw):
    s = TR[lang][key]
    return s.format(**kw) if kw else s


def flag_svg(code):
    """Drapeaux en SVG (les émojis drapeaux ne s'affichent pas sous Windows)."""
    if code == "fr":
        s = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 3 2' preserveAspectRatio='none'><rect width='1' height='2' fill='#0055a4'/>"
             "<rect x='1' width='1' height='2' fill='#fff'/><rect x='2' width='1' height='2' fill='#ef4135'/></svg>")
    else:
        s = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 60 30' preserveAspectRatio='none'><rect width='60' height='30' fill='#012169'/>"
             "<path d='M0 0l60 30m0-30L0 30' stroke='#fff' stroke-width='6'/>"
             "<path d='M0 0l60 30m0-30L0 30' stroke='#C8102E' stroke-width='3'/>"
             "<path d='M30 0v30M0 15h60' stroke='#fff' stroke-width='10'/>"
             "<path d='M30 0v30M0 15h60' stroke='#C8102E' stroke-width='6'/></svg>")
    uri = "data:image/svg+xml;base64," + base64.b64encode(s.encode()).decode()
    on = (code == lang)
    return (f'<img src="{uri}" alt="" style="height:16px;width:24px;min-width:24px;flex-shrink:0;object-fit:fill;display:block;border-radius:2px;'
            f'outline:{"1.5px solid #1c5b8c" if on else "1px solid rgba(128,128,128,.4)"};opacity:{1 if on else .45}"/>')



# Pastilles de couleur (caractère « ● », pas d'émoji) : conforme / justifié / erreur / à revoir
KEYS = {"OK": "Conforme", "ECART_JUSTIFIE": "ECART_JUSTIFIE", "ERREUR": "ERREUR", "A_REVUE_HUMAINE": "A_REVUE_HUMAINE"}
LABEL = {s: TR[lang][k] for s, k in KEYS.items()}
HEX = {"OK": "#2e9e5b", "ECART_JUSTIFIE": "#e0b020", "ERREUR": "#d64545", "A_REVUE_HUMAINE": "#e8892b"}
NAMED = {"OK": "green", "ECART_JUSTIFIE": "yellow", "ERREUR": "red", "A_REVUE_HUMAINE": "orange"}


def dot(statut):
    """Pastille colorée en Markdown Streamlit."""
    return f":{NAMED[statut]}[●]"


def styled(d, highlight=None, fmt_statut=True):
    """DataFrame avec la colonne Statut affichée « ● Libellé » dans la couleur du verdict."""
    fmt = {"Statut": lambda v: f"● {LABEL.get(v, v)}"} if fmt_statut else {}
    if "Confiance" in d.columns:
        fmt["Confiance"] = "{:.0%}"
    if "Source_verdict" in d.columns:
        fmt["Source_verdict"] = lambda v: TR[lang]["src"].get(v, v)
    s = d.style.format(fmt)
    s = s.map(lambda v: f"color: {HEX[v]}; font-weight: 600" if v in HEX else "", subset=["Statut"])
    if highlight is not None:
        s = s.apply(lambda r: ["background-color: rgba(255, 193, 7, .35)" if r.name == highlight else "" for _ in r], axis=1)
    return s


@st.cache_resource
def icone(nom, taille=36, rogner=True):
    """Icône de assets/ (rognée si demandé) réduite, en data-URI (affichée dans le tableau et le bandeau)."""
    f = ASSETS / nom
    if not f.exists():
        return None
    im = (trimmed(f) if rogner else Image.open(f)).convert("RGBA")
    im.thumbnail((taille, taille))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def prio_col():
    """Colonne Priorité en barre 0-100, identique dans tous les tableaux."""
    return st.column_config.ProgressColumn(TR[lang]["cols"].get("Priorité", "Priorité"), min_value=0, max_value=100,
                                           format="%d / 100", width=96,
                                           help=t("prio_help", g=wn["gravite"], c=wn["confiance"], r=wn["recurrence"]))


def show(d, highlight=None, **cfg):
    """Tableau stylé avec en-têtes traduits ; cfg = configuration de colonnes supplémentaire."""
    conf = {c: st.column_config.Column(n) for c, n in TR[lang]["cols"].items() if c in d.columns}
    conf.update(cfg)
    st.dataframe(styled(d, highlight), width="stretch", hide_index=True, column_config=conf)


COLS = ["Priorité", "Matricule", "Champ", "ValeurSourceA", "ValeurDestB", "Statut", "Source_verdict", "Confiance", "Cause_probable"]

@st.cache_data(ttl=120, show_spinner=False)
def gpu_list():
    return llm.gpu_info()


# ------------------------------------------------------------------ barre latérale
with st.sidebar:
    if LOGO_LQ:
        st.image(trimmed(LOGO_LQ), width=170)
    st.header(t("data"))
    st.caption(t("data_cap"))
    ups = {k: st.file_uploader(t(lbl), type="xlsx", key=k) for k, lbl in [
        ("source", "up_source"), ("destination", "up_dest"), ("detail", "up_detail"), ("motif", "up_motif")]}
    files = {k: v for k, v in ups.items() if v is not None}
    if "ver" not in st.session_state:
        st.session_state.ver = 0
    if st.button(t("run"), type="primary", width="stretch"):
        st.session_state.ver += 1
        st.session_state.run = True
    st.subheader(t("llm"))
    # Ollama n'est interrogé que lorsqu'on clique sur « Expliquer » (aucun appel réseau à chaque rechargement)
    labels = {m: f"{name} ({m})" for name, m, _ in llm.PROFILES}
    model = st.radio(t("llm_model"), [m for _, m, _ in llm.PROFILES], format_func=labels.get, help=t("llm_help"))  # boutons : pas de saisie libre
    gpus = gpu_list()
    st.caption(t("gpu_found", g=" ; ".join(gpus)) if gpus else t("gpu_none"))
    device = st.radio(t("device"), ["auto", "cpu"], horizontal=True, key="device", disabled=not gpus,
                      format_func=lambda d: t("dev_auto") if d == "auto" else t("dev_cpu"))
    st.caption(dict((m, n) for _, m, n in llm.PROFILES)[model])
    st.divider()
    st.caption(t("side_note"))


@st.cache_data(show_spinner=False)
def compute(ver, names, _files):
    return ia.enrich(corroboria.run(_files or None))


def data_uri(path):
    """Logo encodé en base64 pour l'incruster dans le titre (SVG tel quel, raster rogné en PNG)."""
    if path.suffix.lower() == ".svg":
        return "data:image/svg+xml;base64," + base64.b64encode(path.read_bytes()).decode()
    buf = io.BytesIO()
    trimmed(path).save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


icon = f'<img src="{data_uri(LOGO)}" alt="" style="height:48px;width:auto;display:block"/>' if LOGO else ""
lq = f'<img src="{data_uri(LOGO_LQ)}" alt="Loto-Québec" style="height:56px;width:auto;display:block"/>' if LOGO_LQ else ""
I, A = '<span style="color:#1c5b8c">I</span>', '<span style="color:#479ea0">A</span>'
title = "Corrobor" + (A + I if lang == "en" else I + A)  # CorroborIA en français, CorroborAI en anglais
# une seule rangée centrée verticalement : logo + titre, interrupteur de langue (collé au titre), logo Loto-Québec à droite
st.markdown("""<style>
.st-key-hdr [data-testid="stHorizontalBlock"]{flex-wrap:nowrap;gap:10px;align-items:center}
.st-key-hdr [data-testid="stColumn"]{flex:0 0 auto !important;width:auto !important;min-width:0 !important}
.st-key-hdr [data-testid="stColumn"]:nth-child(5){flex:1 1 auto !important}
.st-key-hdr h1 a{display:none}
.st-key-lang_en{position:relative;top:7px}
.st-key-hdr [data-testid="stColumn"]:nth-child(2){margin-left:-4px}
</style>""", unsafe_allow_html=True)
with st.container(key="hdr"):
    h0, hfr, htg, hen, _, hlq = st.columns(6, vertical_alignment="center")
    h0.markdown(f'''<div style="display:flex;align-items:center;gap:14px">{icon}<h1 style="margin:0;padding:0;font-size:2.75rem;line-height:1.2;letter-spacing:-0.02em;white-space:nowrap">{title}</h1></div>''',
                unsafe_allow_html=True)
    hfr.markdown('<div style="display:flex;align-items:center"><span style="width:1px;height:30px;background:rgba(128,128,128,.55);'
                 f'margin-right:14px"></span>{flag_svg("fr")}</div>', unsafe_allow_html=True)
    htg.toggle("Language", key="lang_en", label_visibility="collapsed")
    hen.markdown(f'<div style="display:flex">{flag_svg("en")}</div>', unsafe_allow_html=True)
    hlq.markdown(f'<div style="display:flex;justify-content:flex-end">{lq}</div>', unsafe_allow_html=True)
st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

accueil = st.empty()  # vidé dès que la corroboration est lancée, pour ne pas rester sous le spinner
if not st.session_state.get("run"):
    accueil.info(t("welcome"))
    st.stop()
accueil.empty()

try:
    with st.spinner(t("spinner")):
        df = compute(st.session_state.ver, tuple(sorted((k, v.name) for k, v in files.items())), files)
except Exception as e:
    st.error(t("fail", e=e))
    st.stop()

# paramètres du score de priorité (onglet Paramètres) : relus ici pour s'appliquer à tout l'écran
W_DEF = {k: int(round(v * 100)) for k, v in ia.WEIGHTS.items()}
for _k, _v in [*((f"w_{k}", v) for k, v in W_DEF.items()), ("relire_anom", False)]:
    st.session_state.setdefault(_k, _v)
    st.session_state[_k] = st.session_state[_k]  # garde la valeur même si le widget n'est pas affiché dans ce tour
weights = {k: st.session_state[f"w_{k}"] / 100 for k in W_DEF}
sev_user = st.session_state.get("sev", {})
seuil = st.session_state.get("seuil", 90) / 100
relire_anom = st.session_state["relire_anom"]  # option Paramètres : relire aussi les vraies anomalies sous le seuil
df = df.assign(StatutInit=df.Statut)  # verdict d'origine, avant application du seuil
df.loc[(df.Statut != "OK") & (df.Confiance.astype(float) < seuil) & ((df.StatutInit != "ERREUR") | relire_anom),
       "Statut"] = "A_REVUE_HUMAINE"
df = df.assign(Priorité=ia.priorite(df, weights, sev_user))
wsum = sum(weights.values()) or 1.0
wn = {k: v / wsum for k, v in weights.items()}

# lignes à faire : erreurs / revue + écarts justifiés par l'IA dont la confiance est sous le seuil réglable
vstate = st.session_state.setdefault("vstate", {})  # clé de ligne -> vérifié (True/False) choisi à la main


def vkey(r):
    return f"{r.Matricule}|{r.Champ}|{r.TypeAffectation}|{r.ValeurSourceA}|{r.ValeurDestB}"


scope = ["ERREUR", "ECART_JUSTIFIE"]  # catégories prises en compte dans la barre de revue humaine
# à faire = lignes « À relire » (confiance sous le seuil) ; une vraie anomalie n'en fait partie que si l'option Paramètres est sur « Oui »
a_faire = df[(df.Statut == "A_REVUE_HUMAINE") & (df.StatutInit.isin(scope) | (df.StatutInit == "A_REVUE_HUMAINE"))]
a_faire = a_faire.sort_values(["Priorité", "Confiance"], ascending=[False, True])


def auto_ok(r):
    """Pré-vérifié automatiquement : écart justifié dont la confiance atteint le seuil, et vraie anomalie tant que
    l'option Paramètres « relire les vraies anomalies » est sur Non (ou si sa confiance atteint le seuil)."""
    if r.Statut == "ECART_JUSTIFIE":
        return float(r.Confiance) >= seuil
    if r.Statut == "ERREUR":
        return (not relire_anom) or float(r.Confiance) >= seuil
    return False


def is_ok(r):
    return vstate.get(vkey(r), auto_ok(r))


fait = pd.Series([is_ok(r) for r in a_faire.itertuples()], index=a_faire.index, dtype=bool)


def maj_statut(i, nouveau, motif="", commentaire="", auteur=""):
    """Correction de statut confirmée : ajoutée au journal (retours.py), relue par le moteur, puis recalcul."""
    r = df.loc[i]
    retours.ajouter(r.Matricule, r.Champ, nouveau, motif=motif, commentaire=commentaire, auteur=auteur,
                    valeur_a=r.ValeurSourceA, valeur_b=r.ValeurDestB, regle=r.Règle, ancien=r.Statut)
    vstate[vkey(r)] = True
    st.session_state.ver += 1


def reset_filtres():
    """Efface les filtres des listes déroulantes et la sélection faite en cliquant sur les camemberts."""
    st.session_state.flt_cause = None
    st.session_state.flt_emp = None
    st.session_state.pie_v = st.session_state.get("pie_v", 0) + 1


def annuler_statut():
    st.session_state.pop("statut_pending", None)
    st.session_state.dlg_n = st.session_state.get("dlg_n", 0) + 1


@st.dialog(t("conf_title"), on_dismiss=annuler_statut)
def confirmer_statut(i, nouveau):
    r = df.loc[i]
    n = st.session_state.get("dlg_n", 0)
    st.markdown(t("conf_txt", m=r.Matricule, c=r.Champ, a=LABEL[r.Statut], b=LABEL.get(nouveau, nouveau)))
    valide = nouveau in ("ERREUR", "ECART_JUSTIFIE")
    if not valide:
        st.warning(t("conf_bad"))
    motif = st.selectbox(t("motif"), retours.MOTIFS, format_func=lambda m: TR[lang]["motifs"][m], key=f"dlg_motif_{n}")
    commentaire = st.text_area(t("commentaire"), key=f"dlg_comm_{n}", height=70)
    auteur = st.text_input(t("auteur"), value=st.session_state.get("auteur", ""), key=f"dlg_auteur_{n}")
    c1, c2 = st.columns(2)
    if c1.button(t("conf_ok"), type="primary", disabled=not valide, width="stretch"):
        st.session_state.auteur = auteur
        maj_statut(i, nouveau, motif, commentaire, auteur)
        annuler_statut()
        st.rerun()
    if c2.button(t("conf_no"), width="stretch"):
        annuler_statut()
        st.rerun()


def cb_regle(action, prop):
    getattr(retours, action)(prop, st.session_state.get("auteur", ""))
    st.session_state.ver += 1


def cb_desactiver(id_regle):
    retours.desactiver(id_regle, st.session_state.get("auteur", ""))
    st.session_state.ver += 1


def cb_annuler_correction(cle):
    m, c = cle.split("|", 1)
    retours.annuler(m, c, st.session_state.get("auteur", ""))
    st.session_state.ver += 1


# ---------- tableau « Données sélectionnées » : composant HTML (cloche en image à gauche, statut coloré + crayon)
TABLEAU_CSS = """
.corro{font-size:13px;color:var(--st-text-color,inherit);font-family:var(--st-font,inherit)}
.wrap{max-height:440px;overflow:auto;border:1px solid rgba(128,128,128,.3);border-radius:8px}
table{border-collapse:collapse;width:100%}
th{position:sticky;top:0;z-index:2;background:var(--st-secondary-background-color,#262730);text-align:left;font-weight:600;
   padding:8px;border-bottom:1px solid rgba(128,128,128,.35);white-space:nowrap}
td{padding:5px 8px;border-bottom:1px solid rgba(128,128,128,.18);white-space:nowrap;vertical-align:middle}
tr.actif td{background:rgba(255,193,7,.22)}
td.auto input{accent-color:#9a9a9a;opacity:.75}
td.bell,th.bell{width:40px;padding:2px 6px;text-align:center}
button.bell{background:none;border:0;cursor:pointer;padding:2px;border-radius:6px;line-height:0}
button.bell:hover{background:rgba(142,107,191,.22)}
button.bell img{width:34px;height:34px;object-fit:contain;display:block}
input[type=checkbox]{width:16px;height:16px;cursor:pointer;accent-color:#8e6bbf}
td.ver,th.ver{text-align:center;width:60px}
.bar{display:inline-block;vertical-align:middle;width:56px;height:8px;border-radius:5px;background:rgba(128,128,128,.3);margin-right:6px}
.bar span{display:block;height:100%;border-radius:5px;background:#d64545}
td.statut{position:relative;font-weight:700;min-width:150px}
td.statut .cell{display:flex;align-items:center;justify-content:space-between;gap:10px}
td.statut img{width:15px;height:15px;opacity:.85}
td.statut select{position:absolute;inset:0;width:100%;height:100%;opacity:0;cursor:pointer}
td.statut:hover{background:rgba(128,128,128,.18)}
td.long{max-width:300px;overflow:hidden;text-overflow:ellipsis}
"""
TABLEAU_JS = """
export default function(component) {
  const { data, setTriggerValue, parentElement } = component;
  const old = parentElement.querySelector('.corro'); if (old) old.remove();
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const T = data.t, I = data.icons, S = data.show;
  const th = (txt, cls, tip) => `<th class="${cls || ''}" ${tip ? `title="${esc(tip)}"` : ''}>${esc(txt)}</th>`;
  const head = '<tr>' + th('', 'bell', T.aide_help) + th(T.verifie, 'ver', T.ver_help) + th(T.prio) + th(T.matricule) + th(T.champ)
    + th(T.va) + th(T.vb) + th(T.statut, '', T.statut_help) + th(T.source) + th(T.conf) + (S.regle ? th(T.regle) : '') + (S.cause ? th(T.cause) : '') + '</tr>';
  const body = data.rows.map(r => {
    const opts = r.options.map(o => `<option value="${esc(o[0])}" ${o[0] === r.statut ? 'selected' : ''}>${esc(o[1])}</option>`).join('');
    return `<tr class="${r.actif ? 'actif' : ''}">`
      + `<td class="bell"><button class="bell" data-id="${r.id}" title="${esc(T.aide_help)}"><img src="${r.actif ? I.violette : I.grise}" alt=""/></button></td>`
      + `<td class="ver ${r.auto ? 'auto' : ''}"><input type="checkbox" data-id="${r.id}" ${r.verifie ? 'checked' : ''}/></td>`
      + `<td><span class="bar"><span style="width:${r.prio}%"></span></span>${r.prio} / 100</td>`
      + `<td>${esc(r.matricule)}</td><td>${esc(r.champ)}</td><td>${esc(r.va)}</td><td>${esc(r.vb)}</td>`
      + `<td class="statut" style="color:${r.couleur}" title="${esc(T.statut_help)}"><div class="cell"><span>${esc(r.label)}</span>`
      + `<img src="${I.crayon}" alt=""/></div><select data-id="${r.id}" data-orig="${esc(r.statut)}">${opts}</select></td>`
      + `<td>${esc(r.source)}</td><td>${esc(r.conf)}</td>`
      + (S.regle ? `<td class="long" title="${esc(r.regle)}">${esc(r.regle)}</td>` : '')
      + (S.cause ? `<td class="long" title="${esc(r.cause)}">${esc(r.cause)}</td>` : '') + '</tr>';
  }).join('');
  const box = document.createElement('div'); box.className = 'corro';
  box.innerHTML = `<div class="wrap"><table><thead>${head}</thead><tbody>${body}</tbody></table></div>`;
  parentElement.appendChild(box);
  const wrap = box.querySelector('.wrap');
  wrap.scrollTop = window.__corroScroll || 0;                       // garde la position après une mise à jour
  wrap.addEventListener('scroll', () => { window.__corroScroll = wrap.scrollTop; });
  box.querySelectorAll('button.bell').forEach(b => b.onclick = () => setTriggerValue('cloche', Number(b.dataset.id)));
  box.querySelectorAll('input[type=checkbox]').forEach(c => c.onchange = () =>
    setTriggerValue('verifie', {id: Number(c.dataset.id), valeur: c.checked}));
  box.querySelectorAll('select').forEach(s => s.onchange = () => {
    setTriggerValue('statut', {id: Number(s.dataset.id), valeur: s.value});
    s.value = s.dataset.orig;                                       // l'affichage ne change qu'après confirmation
  });
}
"""


@st.cache_resource
def composant_tableau(version):
    """Une version par contenu CSS/JS : une modification du code est prise en compte sans redémarrer le serveur."""
    return st.components.v2.component(f"corroboria_tableau_{version}", css=TABLEAU_CSS, js=TABLEAU_JS)


def cb_cloche():
    ev = st.session_state.get("tab_sel") or {}
    if ev.get("cloche") is not None:
        st.session_state.aide_row = int(ev["cloche"])
        st.session_state.aide_pending = True


def cb_verifie():
    ev = (st.session_state.get("tab_sel") or {}).get("verifie")
    if ev:
        vstate[vkey(df.loc[int(ev["id"])])] = bool(ev["valeur"])


def cb_statut():
    ev = (st.session_state.get("tab_sel") or {}).get("statut")
    if ev:
        st.session_state.statut_pending = {"id": int(ev["id"]), "valeur": ev["valeur"]}


def icone_svg(nom):
    f = ASSETS / nom
    return "data:image/svg+xml;base64," + base64.b64encode(f.read_bytes()).decode() if f.exists() else ""


def tableau_lignes(d, actif):
    """Affiche les lignes de d (DataFrame trié) dans le composant ; les actions arrivent par les rappels cb_*."""
    cols = TR[lang]["cols"]
    lignes = []
    for i, r in zip(d.index, d.itertuples()):
        valides = [("ERREUR", LABEL["ERREUR"]), ("ECART_JUSTIFIE", LABEL["ECART_JUSTIFIE"])]
        if r.Statut not in ("ERREUR", "ECART_JUSTIFIE"):
            valides = [(r.Statut, LABEL[r.Statut])] + valides
        lignes.append({"id": int(i), "actif": int(i) == actif, "verifie": bool(is_ok(r)),
                       "auto": bool(auto_ok(r) and vkey(r) not in vstate), "prio": int(r.Priorité),
                       "matricule": str(r.Matricule), "champ": r.Champ, "va": str(r.ValeurSourceA), "vb": str(r.ValeurDestB),
                       "statut": r.Statut, "label": LABEL[r.Statut], "couleur": HEX[r.Statut], "options": valides,
                       "source": TR[lang]["src"].get(r.Source_verdict, r.Source_verdict), "conf": f"{float(r.Confiance):.0%}",
                       "regle": str(r.Règle), "cause": str(r.Cause_probable or "")})
    vide = lambda c: all(str(x[c]).strip() in ("", "nan", "None") for x in lignes)
    data = {"rows": lignes, "show": {"regle": not vide("regle"), "cause": not vide("cause")},
            "icons": {"grise": icone("cloche_grise.png", 68, rogner=False), "violette": icone("cloche_violette_son.png", 68, rogner=False),
                      "crayon": icone_svg("pencil-square-svgrepo-com.svg")},
            "t": {"aide_help": t("aide_help"), "statut_help": t("statut_help"), "ver_help": t("ver_help"),
                  "verifie": cols.get("Vérifié", "Ok ?"), "prio": cols.get("Priorité", "Priorité"),
                  "matricule": cols.get("Matricule", "Matricule"), "champ": cols.get("Champ", "Champ"),
                  "va": cols.get("ValeurSourceA", "ValeurSourceA"), "vb": cols.get("ValeurDestB", "ValeurDestB"),
                  "statut": cols.get("Statut", "Statut"), "source": cols.get("Source_verdict", "Source_verdict"),
                  "conf": cols.get("Confiance", "Confiance"), "regle": cols.get("Règle", "Règle"),
                  "cause": cols.get("Cause_probable", "Cause probable")}}
    composant_tableau(hashlib.md5((TABLEAU_CSS + TABLEAU_JS).encode()).hexdigest()[:8])(data=data, key="tab_sel", on_cloche_change=cb_cloche, on_verifie_change=cb_verifie,
                        on_statut_change=cb_statut)


# ------------------------------------------------------------------ dashboard
ORDER = ["OK", "ECART_JUSTIFIE", "ERREUR", "A_REVUE_HUMAINE"]
c = df.Statut.value_counts()
total = len(df)
n = {s: int(c.get(s, 0)) for s in ORDER}
SHOWN = [s for s in ORDER if s != "A_REVUE_HUMAINE" or n[s] > 0]  # « À relire » n'apparaît que s'il y a des lignes
a_investiguer = df[df.Statut.isin(["ERREUR", "A_REVUE_HUMAINE"])].sort_values("Priorité", ascending=False)


def donut():
    """Camembert en anneau interactif : survol = mise en avant + infobulle."""
    data = pd.DataFrame({t("verdict"): [LABEL[s] for s in SHOWN], t("count"): [n[s] for s in SHOWN]})
    data[t("share")] = data[t("count")] / max(total, 1)
    data["Taille"] = data[t("count")].clip(lower=total * 0.012)  # une petite part (ex. 2 lignes) reste visible
    hover = alt.selection_point(fields=[t("verdict")], on="pointerover", clear="pointerout")
    click = alt.selection_point(name="part", fields=[t("verdict")])
    arc = (alt.Chart(data).mark_arc(innerRadius=62, outerRadius=100, cornerRadius=4, padAngle=0.02)
           .encode(theta=alt.Theta("Taille:Q", stack=True),
                   color=alt.Color(f"{t('verdict')}:N", sort=[LABEL[s] for s in ORDER], legend=None,
                                   scale=alt.Scale(domain=[LABEL[s] for s in ORDER], range=[HEX[s] for s in ORDER])),
                   opacity=alt.condition(hover, alt.value(1), alt.value(0.35)),
                   tooltip=[f"{t('verdict')}:N", f"{t('count')}:Q", alt.Tooltip(f"{t('share')}:Q", format=".1%")])
           .add_params(hover, click))
    centre = (alt.Chart(pd.DataFrame({"t": [f"{total}"]})).mark_text(size=28, fontWeight="bold", dy=-8)
              .encode(text="t:N"))
    sous = (alt.Chart(pd.DataFrame({"t": [t("checks")]})).mark_text(size=12, dy=16, opacity=0.7)
            .encode(text="t:N"))
    return (arc + centre + sous).properties(height=224, padding={"top": 12, "bottom": 12, "left": 4, "right": 4})


def barre_completion(fait_n, total_n):
    """Barre de complétion de la revue humaine : rayures animées, repères 25/50/75 %, message d'encouragement."""
    pct = 100 if total_n == 0 else round(100 * fait_n / total_n)
    msgs = TR[lang]["fun"]
    msg = msgs[0] if pct == 0 else msgs[1] if pct < 25 else msgs[2] if pct < 50 else msgs[3] if pct < 75 else msgs[4] if pct < 100 else msgs[5]
    fini = pct >= 100
    fond = ("linear-gradient(90deg,#2e9e5b,#6fcf97)" if fini else
            "repeating-linear-gradient(45deg,#479ea0 0,#479ea0 10px,#1c5b8c 10px,#1c5b8c 20px)")
    # l'animation ne joue que quand la progression vient de changer (3 passages), jamais en continu
    change = st.session_state.get("_prev_pct") not in (None, pct)
    st.session_state["_prev_pct"] = pct
    anim = "background-size:28px 28px;" + ("animation:cbar .7s linear 3;" if change and not fini else "")
    reperes = "".join(f'<span style="position:absolute;left:{p}%;top:0;bottom:0;width:2px;background:rgba(255,255,255,.55)"></span>'
                      for p in (25, 50, 75))
    st.markdown(
        "<style>@keyframes cbar{to{background-position:28px 0}}</style>"
        f'<div style="margin-top:12px"><div style="display:flex;justify-content:space-between;font-size:.9rem;margin-bottom:4px">'
        f'<span><b>{TR[lang]["fun_lbl"]}</b> : {msg}</span><span><b>{fait_n}/{total_n}</b> ({pct} %)</span></div>'
        f'<div style="position:relative;height:18px;border-radius:12px;background:rgba(128,128,128,.28);overflow:hidden">'
        f'<div style="width:{pct}%;height:100%;border-radius:12px;background:{fond};{anim}transition:width .6s ease"></div>'
        f'{reperes}</div></div>', unsafe_allow_html=True)


def section(titre, top=24):
    st.markdown(f"<div style='margin:{top}px 0 8px;font-size:1.75rem;font-weight:700;line-height:1.2'>{titre}</div>",
                unsafe_allow_html=True)


section(t("dashboard"), 20)
with st.container(border=True):
    g, d = st.columns(2, gap="large", vertical_alignment="center")
    with g:
        gc, gl = st.columns([1, 1], vertical_alignment="center")
        with gc:
            evt = st.altair_chart(donut(), width="stretch", on_select="rerun", key="donut")
        with gl:
            rows = "".join(
                f'<div style="display:flex;align-items:center;gap:10px;margin:7px 0;font-size:1.05rem">'
                f'<span style="color:{HEX[s]};font-size:1.5rem;line-height:1">&#9679;</span>'
                f'<span>{LABEL[s]} <b>{n[s]}</b></span></div>' for s in SHOWN)
            st.markdown(f'<div style="display:flex;flex-direction:column;justify-content:center">{rows}</div>',
                        unsafe_allow_html=True)
        st.slider(t("seuil"), 0, 100, 90, 1, format="%d %%", key="seuil", help=t("seuil_help"))

    with d:
        taux = n["OK"] / max(total, 1)
        k1, k2, k3, k4 = st.columns(4)
        k1.metric(t("k_compl"), f"{taux:.0%}", help=t("k_compl_h"))
        k2.metric(t("k_inv"), len(a_investiguer), help=t("k_inv_h"))
        k3.metric(t("k_emp"), df.Matricule.nunique(), help=t("k_emp_h"))
        k4.metric(t("k_conc"), a_investiguer.Matricule.nunique(), help=t("k_conc_h"))
        if a_investiguer.empty:
            st.success(t("no_err"))
        else:
            top = a_investiguer.iloc[0]
            vc = a_investiguer.Champ.value_counts()
            par_ia = int((df[df.Statut != "OK"].Source_verdict == "IA").sum())
            ia_rows = df[(df.Source_verdict == "IA") | df.Statut.isin(["ERREUR", "A_REVUE_HUMAINE"])]  # IA + vraies anomalies
            conf = f"{ia_rows.Confiance.astype(float).mean():.0%}" if len(ia_rows) else "n/a"
            st.markdown(t("top1", c=top.Champ, m=top.Matricule, p=top.Priorité) + "  \n"
                        + t("top_field", c=vc.index[0], n=int(vc.iloc[0])) + "  \n"
                        + t("by_ai", a=par_ia, b=total - n["OK"], c=conf))
        barre_completion(int(fait.sum()), len(a_faire))


PALETTE = ["#1c5b8c", "#479ea0", "#8cc4b8", "#f2a65a", "#b56576", "#6a994e", "#9aa5b1"]
ROUGE, ORANGE = HEX["ERREUR"], "#f08c00"


VIOLET = "#8e6bbf"


def histogram():
    """Scores de confiance (lignes tranchées par l'IA + vraies anomalies + à relire), empilés par statut actuel :
    rouge = vraie anomalie, orange = écart justifié, violet = à relire."""
    d = df[(df.Source_verdict == "IA") | df.Statut.isin(["ERREUR", "A_REVUE_HUMAINE"])]
    d = d[d.Statut.isin(["ERREUR", "ECART_JUSTIFIE", "A_REVUE_HUMAINE"])].assign(
        Verdict=lambda x: x.Statut.map(LABEL), Confiance=lambda x: x.Confiance.astype(float))
    dom = [LABEL["ERREUR"], LABEL["ECART_JUSTIFIE"], LABEL["A_REVUE_HUMAINE"]]
    return (alt.Chart(d).mark_bar(stroke="white", strokeWidth=0.5)
            .encode(x=alt.X("Confiance:Q", bin=alt.Bin(extent=[0, 1.025], step=0.025), title=t("conf_axis"),
                            scale=alt.Scale(domain=[0, 1.025], nice=False),
                            axis=alt.Axis(format=".0%", values=[i / 10 for i in range(11)], labelFontSize=10, titleFontSize=11)),
                    y=alt.Y("count():Q", title=None, axis=alt.Axis(labelFontSize=10)),
                    color=alt.Color("Verdict:N", scale=alt.Scale(domain=dom, range=[ROUGE, ORANGE, VIOLET]),
                                    legend=alt.Legend(orient="top-left", title=None, symbolType="circle", labelFontSize=11,
                                                      fillColor="rgba(0,0,0,0)", padding=0)),
                    tooltip=["Verdict:N", alt.Tooltip("count():Q", title=t("count"))])
            .properties(height=176, padding={"top": 6, "bottom": 6, "left": 4, "right": 4}))


def etiquette(serie):
    """Étiquette de chaque ligne dans un camembert : les 3 modalités les plus fréquentes, le reste en « Autres »."""
    vc = serie.value_counts()
    top = list(vc.index) if len(vc) <= 4 else list(vc.head(3).index)
    return serie.where(serie.isin(top), t("others")).astype(str)


def cause_serie(x):
    """Cause probable ; à défaut (écarts justifiés), la règle appliquée."""
    return x.Cause_probable.where(x.Cause_probable.astype(bool), x.Règle).replace("", t("unspecified"))


def pie(serie, cle, hauteur=152):
    """Camembert cliquable des modalités les plus fréquentes (le reste regroupé dans « Autres »)."""
    vc = etiquette(serie).value_counts()
    data = pd.DataFrame({"Libellé": [str(i) for i in vc.index], t("count"): vc.values})
    hover = alt.selection_point(fields=["Libellé"], on="pointerover", clear="pointerout")
    click = alt.selection_point(name="part", fields=["Libellé"])
    chart = (alt.Chart(data).mark_arc(innerRadius=0, outerRadius=62, stroke="white", strokeWidth=1)
             .encode(theta=alt.Theta(f"{t('count')}:Q", stack=True),
                     color=alt.Color("Libellé:N", sort=list(data["Libellé"]), scale=alt.Scale(range=PALETTE),
                                     legend=alt.Legend(orient="right", title=None, symbolType="circle", labelFontSize=13,
                                                       labelLimit=108, rowPadding=1, symbolSize=90)),
                     opacity=alt.condition(hover, alt.value(1), alt.value(0.45)),
                     tooltip=["Libellé:N", f"{t('count')}:Q"])
             .add_params(hover, click)
             .properties(height=hauteur, padding={"top": 6, "bottom": 6, "left": 4, "right": 4}))
    ev = st.altair_chart(chart, width="stretch", on_select="rerun", key=cle)
    return [p.get("Libellé") for p in (ev.selection.get("part") or [])] if ev else []


def valeur(cle):
    """Choix courant de l'interrupteur (lu avant son affichage, car il est placé sous le graphique)."""
    return st.session_state.get(cle) or "ERREUR"


def choix(cle):
    """Interrupteur Vraie anomalie / Écarts justifiés (par défaut : vraie anomalie)."""
    st.segmented_control("-", ["ERREUR", "ECART_JUSTIFIE"], default="ERREUR", key=cle, format_func=lambda s: LABEL[s],
                         label_visibility="collapsed")


with st.container(border=True):
    h1c, h2c, h3c = st.columns(3, gap="large")
    with h1c:
        st.markdown(f"**{t('hist_title')}**")
        st.altair_chart(histogram(), width="stretch")
    with h2c:
        st.markdown(f"**{t('cause_title')}**")
        lab_cause = pie(cause_serie(df[df.StatutInit == valeur("pie_cause")]), f"pie_cause_chart_{st.session_state.get('pie_v', 0)}")
        choix("pie_cause")
    with h3c:
        st.markdown(f"**{t('emp_title')}**")
        lab_emp = pie(df[df.StatutInit == valeur("pie_emp")].Matricule.astype(str), f"pie_emp_chart_{st.session_state.get('pie_v', 0)}")
        choix("pie_emp")


def csv_bytes(d):  # séparateur ; et BOM UTF-8 : s'ouvre correctement dans Excel en français
    return d.drop(columns=["RefAlt", "Nature", "StatutInit"], errors="ignore").to_csv(index=False, sep=";").encode("utf-8-sig")


section(t("selected"))
VUES = ["V_ALL", "V_FIELD", "V_GLOSS", "V_COR", "V_SET"]
CHOIX = SHOWN + VUES
NOM_VUE = {"V_COR": "v_cor", "V_ALL": "v_all", "V_FIELD": "v_field", "V_GLOSS": "v_gloss", "V_SET": "v_set"}
with st.container(border=True):
    # un clic sur l'anneau coche la pastille du statut (et décocher la part la décoche) ; ensuite les pastilles font foi
    clic = {s for s in SHOWN if evt and LABEL[s] in [p.get(t("verdict")) for p in (evt.selection.get("part") or [])]}
    avant = st.session_state.get("_anneau_prev", set())
    if clic != avant:
        courant = (set(st.session_state.get("sel_stat") or []) | (clic - avant)) - (avant - clic)
        st.session_state["sel_stat"] = [v for v in CHOIX if v in courant]
        st.session_state["_anneau_prev"] = clic
    st.session_state.setdefault("sel_stat", ["A_REVUE_HUMAINE"])  # au départ : les lignes à relire
    pastilles = st.pills(t("pick_pills"), CHOIX, selection_mode="multi", key="sel_stat",
                         format_func=lambda v: t(NOM_VUE[v]) if v in NOM_VUE else LABEL[v]) or []
    propositions = retours.propositions()
    if propositions:
        st.info(t("cor_notice", n=len(propositions)))
    col_dl, col_tri = st.columns([5, 4], vertical_alignment="bottom")
    bouton = col_dl.container()  # bouton d'export (à gauche du tri), rempli une fois le tableau affiché connu
    with col_tri:
        ordre = st.segmented_control(t("sort_lbl"), ["desc", "asc"], default="desc", key="sel_sort",
                                     format_func=lambda o: t("sort_" + o)) or "desc"
    export, export_nom = None, "tableau"

    # filtres : type d'erreur (cause probable) et employé, en plus des clics sur les camemberts
    f1, f2, f3 = st.columns([3, 2, 2], vertical_alignment="bottom")
    causes_dispo = list(cause_serie(df[df.Statut != "OK"]).value_counts().index)
    flt_cause = f1.selectbox(t("flt_cause"), [None] + causes_dispo, key="flt_cause",
                             format_func=lambda v: t("flt_all") if v is None else v)
    flt_emp = f2.selectbox(t("flt_emp"), [None] + sorted(df.Matricule.astype(str).unique()), key="flt_emp",
                           format_func=lambda v: t("flt_all") if v is None else v)
    actifs = ([f"{t('and_cause')} : {', '.join(lab_cause)}"] if lab_cause else []) \
        + ([f"{t('and_emp')} : {', '.join(lab_emp)}"] if lab_emp else []) \
        + ([f"{t('and_cause')} : {flt_cause}"] if flt_cause else []) + ([f"{t('and_emp')} : {flt_emp}"] if flt_emp else [])
    if actifs:  # le filtre est visible tant qu'il existe, avec un bouton pour l'enlever
        f3.button(t("flt_reset"), key="flt_reset", on_click=reset_filtres, width="stretch")
        st.markdown(f"**{t('flt_active')}** : " + " · ".join(actifs))
    if lang == "en":
        st.caption(t("free_text"))

    statuts = [s for s in SHOWN if s in pastilles or "V_ALL" in pastilles]
    indices, parties = [], []
    if statuts:
        indices.append(set(df.index[df.Statut.isin(statuts)]))
        parties.append(t("v_all") if "V_ALL" in pastilles else ", ".join(LABEL[s] for s in statuts))
    if lab_cause:
        sub = df[df.StatutInit == valeur("pie_cause")]
        et = etiquette(cause_serie(sub))
        indices.append(set(et.index[et.isin(lab_cause)]))
        parties.append(f"{t('and_cause')} : {', '.join(lab_cause)}")
    if lab_emp:
        sub = df[df.StatutInit == valeur("pie_emp")]
        et = etiquette(sub.Matricule.astype(str))
        indices.append(set(et.index[et.isin(lab_emp)]))
        parties.append(f"{t('and_emp')} : {', '.join(lab_emp)}")
    if flt_cause is not None:
        ce = cause_serie(df[df.Statut != "OK"])
        indices.append(set(ce.index[ce == flt_cause]))
        parties.append(f"{t('and_cause')} : {flt_cause}")
    if flt_emp is not None:
        indices.append(set(df.index[df.Matricule.astype(str) == flt_emp]))
        parties.append(f"{t('and_emp')} : {flt_emp}")
    if not indices and not any(v in pastilles for v in VUES):
        st.caption(t("click_hint"))

    # ---- lignes (statuts, anneau, camemberts, « Tout »)
    if indices:
        sel = df.loc[sorted(set.intersection(*indices))].sort_values(["Priorité", "Matricule"], ascending=[ordre == "asc", True])
        st.markdown(f"**{t('rows_of', n=len(sel), l=' · '.join(parties))}**")
        if st.session_state.get("aide_row") not in sel.index:
            st.session_state.pop("aide_row", None)
        tableau_lignes(sel, st.session_state.get("aide_row"))
        if st.session_state.get("statut_pending"):  # changement de statut demandé dans le tableau : confirmation
            p = st.session_state.statut_pending
            if p["id"] in df.index:
                confirmer_statut(p["id"], p["valeur"])
        export, export_nom = sel[COLS + ["Règle", "Explication"]], "lignes_selectionnees"


    # ---- Par champ
    if "V_FIELD" in pastilles:
        st.subheader(t("v_field"))
        res = (df.groupby(["Champ", "Statut"]).size().unstack(fill_value=0)
                 .reindex(columns=ORDER, fill_value=0).rename(columns=LABEL))
        st.bar_chart(res, color=[HEX[s] for s in ORDER], horizontal=True)
        st.dataframe(res, width="stretch")
        if export is None:
            export, export_nom = res.reset_index(), "par_champ"

    # ---- Glossaire (champs + codes)
    if "V_GLOSS" in pastilles:
        st.subheader(t("v_gloss"))
        st.caption(t("gloss_cap"))
        champs_gl = corroboria.glossary_fields()
        st.markdown(f"**{t('gloss_fields')}**")
        st.dataframe(champs_gl, width="stretch", hide_index=True)
        st.markdown(f"**{t('codes')}**")
        codes_gl = pd.DataFrame(corroboria.GLOSSARY_CODES, columns=[t("code"), t("meaning")])
        st.dataframe(codes_gl, width="stretch", hide_index=True)
        if export is None:
            export, export_nom = champs_gl, "glossaire_champs"

    # ---- Corrections : règles proposées, règles apprises, journal, effet
    if "V_COR" in pastilles:
        st.subheader(t("v_cor"))
        st.markdown(f"**{t('cor_prop')}**")
        if not propositions:
            st.caption(t("cor_prop_none", n=retours.SEUIL_REGLE))
        for k, p in enumerate(propositions):
            st.markdown(t("cor_prop_txt", c=p["champ"], fa=p["forme_a"], fb=p["forme_b"], v=LABEL[p["verdict"]], n=p["n"],
                          ex=", ".join(p["exemples"])))
            b1, b2, _ = st.columns([2, 1, 5])
            b1.button(t("cor_valider"), key=f"val_{k}", type="primary", on_click=cb_regle, args=("valider", p))
            b2.button(t("cor_rejeter"), key=f"rej_{k}", on_click=cb_regle, args=("rejeter", p))
        st.markdown(f"**{t('cor_actives')}**")
        actives = retours.regles_actives()
        if not actives:
            st.caption(t("cor_none_act"))
        for r_ in actives:
            st.markdown(t("cor_regle_txt", i=r_["id"], c=r_["champ"], fa=r_["forme_a"], fb=r_["forme_b"], v=LABEL[r_["verdict"]],
                          n=r_["n"], a=r_["auteur"] or "?", d=r_["date"]))
            st.button(t("cor_desact", i=r_["id"]), key=f"des_{r_['id']}", on_click=cb_desactiver, args=(r_["id"],))
        st.markdown(f"**{t('cor_journal')}**")
        journal = retours.lire_journal()
        st.dataframe(journal.iloc[::-1], width="stretch", hide_index=True)
        eff = retours.corrections_effectives()
        if len(eff):
            cles = [f"{m}|{c}" for m, c in zip(eff.Matricule, eff.Champ)]
            choix_ = st.selectbox(t("cor_pick"), cles, format_func=lambda s: s.replace("|", " · "), key="cor_pick")
            st.button(t("cor_annuler"), key="cor_annuler", on_click=cb_annuler_correction, args=(choix_,))
        st.markdown(f"**{t('cor_effet')}**")
        if st.button(t("cor_mesurer"), key="cor_mesurer"):
            with st.spinner("…"):
                st.session_state.effet = ia.effet_retours(corroboria.run(files or None))
        if st.session_state.get("effet"):
            e_ = st.session_state.effet
            m1, m2, m3, m4 = st.columns(4)
            m1.metric(t("cor_m1"), e_["corriges_par_expert"])
            m2.metric(t("cor_m2"), e_["changes_par_regles_apprises"])
            m3.metric(t("cor_m3"), e_["changes_par_le_modele"])
            m4.metric(t("cor_m4"), e_["total_changes"])
        if export is None:
            export, export_nom = journal, "journal_corrections"

    # ---- Paramètres
    if "V_SET" in pastilles:
        def reset_settings():
            for k, v in W_DEF.items():
                st.session_state[f"w_{k}"] = v
            st.session_state.sev = {}
            st.session_state.relire_anom = False

        st.subheader(t("rev_title"))
        st.radio(t("rev_opt"), [False, True], horizontal=True, key="relire_anom", help=t("rev_help"),
                 format_func=lambda v: t("yes") if v else t("no"))

        st.subheader(t("set_title"))
        st.caption(t("set_intro"))
        sc = st.columns(3)
        for col, k in zip(sc, W_DEF):
            col.slider(t(f"w_{k}"), 0, 100, step=5, format="%d %%", key=f"w_{k}")
        st.caption(t("w_norm", g=wn["gravite"], c=wn["confiance"], r=wn["recurrence"]))

        st.subheader(t("sev_title"))
        st.caption(t("sev_intro"))
        sev_now = {**ia.SEVERITY, **sev_user}
        champs_all = sorted(df.Champ.unique(), key=lambda c: (-sev_now.get(c, .5), c))
        base = pd.DataFrame({"Champ": champs_all, "Gravité": [float(sev_now.get(c, .5)) for c in champs_all]})
        edited = st.data_editor(
            base, hide_index=True, width="stretch", disabled=["Champ"], key=f"sev_editor_{st.session_state.get('sev_v', 0)}",
            column_config={"Champ": st.column_config.Column(TR[lang]["cols"].get("Champ", "Champ")),
                           "Gravité": st.column_config.NumberColumn(t("sev_col"), min_value=0.0, max_value=1.0, step=0.05,
                                                                       format="%.2f")})
        new = {r.Champ: round(float(r.Gravité), 2) for r in edited.itertuples()}
        if new != {c: round(float(sev_now.get(c, .5)), 2) for c in champs_all}:
            st.session_state.sev = {**sev_user, **new}
            st.rerun()

        def reset_and_refresh():
            reset_settings()
            st.session_state.sev_v = st.session_state.get("sev_v", 0) + 1

        st.button(t("reset"), on_click=reset_and_refresh)
        if export is None:
            export, export_nom = base, "gravite_par_variable"

    # ---- un seul bouton : le tableau actuellement affiché
    if export is not None:
        bouton.download_button(t("dl_cur"), csv_bytes(export), f"{export_nom}.csv", "text/csv")


# ------------------------------------------------------------------ bandeau « Explication IA locale » (bas de page)
st.markdown("""<style>
.st-key-bandeau_ia{position:fixed !important;left:var(--sbw,300px);right:0;bottom:0;z-index:1000;margin:0 !important;
 width:auto !important;max-width:none !important;box-sizing:border-box;padding:14px 22px 18px;
 border-radius:12px 12px 0 0;color:#fff;max-height:46vh;overflow:auto;
 background:linear-gradient(135deg,#4a2d80,#8e6bbf);box-shadow:0 -4px 22px rgba(0,0,0,.45)}
.st-key-bandeau_ia p,.st-key-bandeau_ia span,.st-key-bandeau_ia strong,.st-key-bandeau_ia em,.st-key-bandeau_ia li{color:#fff !important}
.st-key-bandeau_ia code{background:rgba(0,0,0,.35) !important;color:#fff !important;border-radius:6px;padding:1px 6px}
.st-key-bandeau_ia button{background:rgba(255,255,255,.16) !important;border:1px solid rgba(255,255,255,.7) !important;color:#fff !important}
.st-key-bandeau_ia button p,.st-key-bandeau_ia button span,.st-key-bandeau_ia button div{color:#fff !important}
.st-key-bandeau_ia button:hover{background:rgba(255,255,255,.3) !important}
.st-key-bandeau_ia a,.st-key-bandeau_ia a *{color:#fff !important;text-decoration:underline}
.st-key-bandeau_texte a,.st-key-bandeau_texte a *{color:#4a2d80 !important}
.st-key-bandeau_texte{background:#fff !important;border-radius:8px;padding:12px 16px;margin-top:6px}
.st-key-bandeau_texte p,.st-key-bandeau_texte span,.st-key-bandeau_texte strong,.st-key-bandeau_texte em{color:#1b1b1f !important}
.st-key-bandeau_texte code{background:#eceaf3 !important;color:#1b1b1f !important}
</style>""", unsafe_allow_html=True)
# largeur de la barre latérale -> variable CSS --sbw : le bandeau fixe démarre exactement à son bord
SBW_JS = """
export default function() {
  const sb = document.querySelector('[data-testid="stSidebar"]');
  const set = () => document.documentElement.style.setProperty('--sbw', (sb ? sb.getBoundingClientRect().right : 0) + 'px');
  set();
  const ro = new ResizeObserver(set); if (sb) ro.observe(sb);
  window.addEventListener('resize', set);
  return () => { ro.disconnect(); window.removeEventListener('resize', set); };
}"""


@st.cache_resource
def composant_sbw(version):
    return st.components.v2.component(f"sbw_{version}", isolate_styles=False, js=SBW_JS)


composant_sbw(hashlib.md5(SBW_JS.encode()).hexdigest()[:8])(key="sbw")
_i = st.session_state.get("aide_row")
if _i is not None and _i in df.index:
    st.markdown("<div style='height:230px'></div>", unsafe_allow_html=True)  # le bandeau fixe ne masque pas la fin de la page
    r = df.loc[_i]
    cle_llm = f"llm_{model}_{_i}"
    texte = llm.cached(r, model) or st.session_state.get(cle_llm)
    echec = False
    with st.container(key="bandeau_ia"):
        entete, fermer = st.columns([6, 1], vertical_alignment="center")
        cloche = icone("cloche_violette_son.png", 40)
        entete.markdown((f'<img src="{cloche}" style="height:26px;vertical-align:middle;margin-right:8px"/>' if cloche else "")
                        + f"**{t('ban_title')}** · `{r.Champ}` · {r.Matricule} · A : {r.ValeurSourceA} → B : {r.ValeurDestB}"
                        f" · {dot(r.Statut)} {LABEL[r.Statut]} ({r.Confiance:.0%})", unsafe_allow_html=True)
        fermer.button(t("ban_close"), key="aide_close", on_click=lambda: st.session_state.pop("aide_row", None), width="stretch")
        if st.session_state.pop("aide_pending", False) and not texte:  # Ollama n'est appelé qu'après un clic sur la cloche
            with st.spinner(t("llm_spin")):
                texte = llm.explain_row(r, model, device if gpus else "auto")
                st.session_state[cle_llm + "_proc"] = llm.processor(model)
            echec = texte is None
            if texte:
                st.session_state[cle_llm] = texte
        if echec:
            st.warning(t("llm_none", m=model))
        with st.container(key="bandeau_texte"):  # zone d'écriture blanche : texte lisible sur le fond violet
            if texte:
                st.markdown(texte)
                if st.session_state.get(cle_llm + "_proc"):
                    st.caption(t("on_proc", p=st.session_state[cle_llm + "_proc"]) + f" · {model}")
            else:
                st.markdown(f"{t('ban_fallback')} {r.Explication}")
