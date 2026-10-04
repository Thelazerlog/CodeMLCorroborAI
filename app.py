"""Application CorroborIA : streamlit run app.py"""
import base64
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
        "Conforme": "Conforme", "ECART_JUSTIFIE": "Écart justifié", "ERREUR": "Erreur", "A_REVUE_HUMAINE": "À revue humaine",
        "data": "Données", "data_cap": "Par défaut, les fichiers fournis dans le dossier sont utilisés. Les fichiers sont lus en lecture seule.",
        "up_source": "Système A – RH (source)", "up_dest": "Système B – Temps (cible)", "up_detail": "Détail du poste",
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
        "k_inv": "À investiguer", "k_inv_h": "Erreurs confirmées et cas à revoir par un humain.",
        "k_emp": "Employés", "k_emp_h": "Employés analysés.",
        "k_conc": "Concernés", "k_conc_h": "Employés ayant au moins une erreur ou un cas à revoir.",
        "no_err": "Aucune erreur à investiguer.",
        "top1": "**Priorité n°1** : `{c}`, employé {m} ({p}/100)", "top_field": "**Champ le plus touché** : `{c}` ({n} cas)",
        "by_ai": "**Écarts tranchés par l'IA** : {a} sur {b} (confiance générale du modèle : **{c}**)",
        "dl_xlsx": "Rapport Excel", "dl_all": "CSV – tout", "dl_err": "CSV – à investiguer", "dl_just": "CSV – justifiés",
        "tab_inv": "À investiguer", "tab_just": "Écarts justifiés", "tab_field": "Par champ", "tab_all": "Tout",
        "tab_gloss": "Glossaire", "tab_set": "Paramètres",
        "f_field": "Filtrer par champ", "f_emp": "Filtrer par matricule",
        "prio_help": "Score 0-100 : gravité du champ ({g:.0%}), confiance ({c:.0%}), récurrence du champ ({r:.0%}). Réglable dans Paramètres.",
        "why": "Pourquoi ce verdict ?", "pick": "Choisis une ligne", "row": "{m} · {c} · priorité {p}",
        "val_a": "Valeur Système A", "val_b": "Valeur Système B",
        "verdict_line": "**Verdict** : {d} {l} — origine : `{o}` — confiance {c:.0%}",
        "rule_line": "**Règle appliquée** : {x}", "expl_line": "**Explication** : {x}",
        "btn_llm": "Expliquer avec le LLM local ({m})", "btn_llm_h": "Appel au modèle sur ta machine (plusieurs secondes sans GPU) ; résultat mis en cache.",
        "llm_spin": "Le LLM local rédige l'explication…",
        "llm_none": "Le LLM n'a pas répondu (Ollama arrêté ou trop lent). Explication par gabarit conservée.",
        "llm_expl": "**Explication LLM local ({m})** : {x}", "cause": "**Cause probable** : {x}",
        "all_checks": "Toutes les vérifications de cet employé",
        "expert": "**Retour d'expert** : corriger ce verdict (appris aux prochaines exécutions)",
        "correct": "Verdict correct", "save_corr": "Enregistrer la correction",
        "just_cap": "Différences acceptables : une règle métier ou un artefact connu les explique.",
        "gloss_cap": "Champs corroborés (d'après le fichier de mapping) et codes utilisés.", "codes": "Codes",
        "code": "Code", "meaning": "Signification",
        "set_title": "Score de priorité", "set_intro": "Le score (0-100) des erreurs est : gravité du champ × poids + confiance × poids + récurrence × poids. "
                    "Les poids sont normalisés (leur somme est ramenée à 100 %). Les changements s'appliquent immédiatement au tableau de bord et aux tableaux.",
        "w_gravite": "Gravité du champ", "w_confiance": "Confiance du verdict", "w_recurrence": "Récurrence du champ",
        "w_norm": "Poids effectifs après normalisation : gravité {g:.0%} · confiance {c:.0%} · récurrence {r:.0%}",
        "sev_title": "Gravité par variable", "sev_intro": "Coefficient de 0 à 1 par champ (1 = le plus prioritaire). Modifie directement dans le tableau.",
        "sev_col": "Gravité (0-1)", "reset": "Rétablir les valeurs par défaut",
        "cols": {},
        "src": {"règle": "règle", "IA": "IA", "expert": "expert"},
        "free_text": "",
    },
    "en": {
        "Conforme": "Compliant", "ECART_JUSTIFIE": "Justified gap", "ERREUR": "Error", "A_REVUE_HUMAINE": "Needs human review",
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
        "k_inv": "To investigate", "k_inv_h": "Confirmed errors and cases for human review.",
        "k_emp": "Employees", "k_emp_h": "Employees analysed.",
        "k_conc": "Affected", "k_conc_h": "Employees with at least one error or case to review.",
        "no_err": "No error to investigate.",
        "top1": "**Top priority**: `{c}`, employee {m} ({p}/100)", "top_field": "**Most affected field**: `{c}` ({n} cases)",
        "by_ai": "**Gaps decided by AI**: {a} out of {b} (overall model confidence: **{c}**)",
        "dl_xlsx": "Excel report", "dl_all": "CSV – all", "dl_err": "CSV – to investigate", "dl_just": "CSV – justified",
        "tab_inv": "To investigate", "tab_just": "Justified gaps", "tab_field": "By field", "tab_all": "All",
        "tab_gloss": "Glossary", "tab_set": "Settings",
        "f_field": "Filter by field", "f_emp": "Filter by employee ID",
        "prio_help": "Score 0-100: field severity ({g:.0%}), confidence ({c:.0%}), field recurrence ({r:.0%}). Adjustable in Settings.",
        "why": "Why this verdict?", "pick": "Pick a row", "row": "{m} · {c} · priority {p}",
        "val_a": "System A value", "val_b": "System B value",
        "verdict_line": "**Verdict**: {d} {l} — origin: `{o}` — confidence {c:.0%}",
        "rule_line": "**Rule applied**: {x}", "expl_line": "**Explanation**: {x}",
        "btn_llm": "Explain with the local LLM ({m})", "btn_llm_h": "Calls the model on your machine (several seconds without GPU); result is cached.",
        "llm_spin": "The local LLM is writing the explanation…",
        "llm_none": "The LLM did not answer (Ollama stopped or too slow). Template explanation kept.",
        "llm_expl": "**Local LLM explanation ({m})**: {x}", "cause": "**Probable cause**: {x}",
        "all_checks": "All checks for this employee",
        "expert": "**Expert feedback**: correct this verdict (learned on next runs)",
        "correct": "Correct verdict", "save_corr": "Save the correction",
        "just_cap": "Acceptable differences: a business rule or a known artefact explains them.",
        "gloss_cap": "Corroborated fields (from the mapping file) and codes used.", "codes": "Codes",
        "code": "Code", "meaning": "Meaning",
        "set_title": "Priority score", "set_intro": "The score (0-100) of errors is: field severity × weight + confidence × weight + recurrence × weight. "
                    "Weights are normalised (their sum is brought back to 100%). Changes apply immediately to the dashboard and tables.",
        "w_gravite": "Field severity", "w_confiance": "Verdict confidence", "w_recurrence": "Field recurrence",
        "w_norm": "Effective weights after normalisation: severity {g:.0%} · confidence {c:.0%} · recurrence {r:.0%}",
        "sev_title": "Severity by variable", "sev_intro": "Coefficient from 0 to 1 per field (1 = highest priority). Edit directly in the table.",
        "sev_col": "Severity (0-1)", "reset": "Restore default values",
        "cols": {"Priorité": "Priority", "Matricule": "Employee ID", "Champ": "Field", "ValeurSourceA": "System A value",
                 "ValeurDestB": "System B value", "Statut": "Status", "Source_verdict": "Decided by",
                 "Confiance": "Confidence", "Cause_probable": "Probable cause", "Règle": "Rule",
                 "Explication": "Explanation", "CodeEmploi": "Job code", "TypeAffectation": "Assignment type"},
        "src": {"règle": "rule", "IA": "AI", "expert": "expert"},
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


def styled(d):
    """DataFrame avec la colonne Statut affichée « ● Libellé » dans la couleur du verdict."""
    fmt = {"Statut": lambda v: f"● {LABEL.get(v, v)}"}
    if "Confiance" in d.columns:
        fmt["Confiance"] = "{:.0%}"
    if "Source_verdict" in d.columns:
        fmt["Source_verdict"] = lambda v: TR[lang]["src"].get(v, v)
    s = d.style.format(fmt)
    return s.map(lambda v: f"color: {HEX[v]}; font-weight: 600" if v in HEX else "", subset=["Statut"])


def show(d, **cfg):
    """Tableau stylé avec en-têtes traduits ; cfg = configuration de colonnes supplémentaire."""
    conf = {c: st.column_config.Column(n) for c, n in TR[lang]["cols"].items() if c in d.columns}
    conf.update(cfg)
    st.dataframe(styled(d), width="stretch", hide_index=True, column_config=conf)


COLS = ["Priorité", "Matricule", "Champ", "ValeurSourceA", "ValeurDestB", "Statut", "Source_verdict", "Confiance", "Cause_probable"]

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
    present = llm.installed_models()
    labels = {m: f"{name} ({m})" + ("" if m in present else t("not_installed")) for name, m, _ in llm.PROFILES}
    model = st.selectbox(t("llm_model"), [m for _, m, _ in llm.PROFILES], format_func=labels.get, help=t("llm_help"))
    llm_ok = model in present
    st.caption(dict((m, n) for _, m, n in llm.PROFILES)[model])
    if not present:
        st.caption(t("ollama_off"))
    elif not llm_ok:
        st.caption(t("ollama_pull", m=model))
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
weights = {k: st.session_state.get(f"w_{k}", W_DEF[k]) / 100 for k in W_DEF}
sev_user = st.session_state.get("sev", {})
df = df.assign(Priorité=ia.priorite(df, weights, sev_user))
wsum = sum(weights.values()) or 1.0
wn = {k: v / wsum for k, v in weights.items()}

# ------------------------------------------------------------------ dashboard
ORDER = ["OK", "ECART_JUSTIFIE", "ERREUR", "A_REVUE_HUMAINE"]
c = df.Statut.value_counts()
total = len(df)
n = {s: int(c.get(s, 0)) for s in ORDER}
a_investiguer = df[df.Statut.isin(["ERREUR", "A_REVUE_HUMAINE"])].sort_values("Priorité", ascending=False)


def donut():
    """Camembert en anneau interactif : survol = mise en avant + infobulle."""
    data = pd.DataFrame({t("verdict"): [LABEL[s] for s in ORDER], t("count"): [n[s] for s in ORDER]})
    data[t("share")] = data[t("count")] / max(total, 1)
    hover = alt.selection_point(fields=[t("verdict")], on="pointerover", clear="pointerout")
    arc = (alt.Chart(data).mark_arc(innerRadius=62, outerRadius=100, cornerRadius=4, padAngle=0.02)
           .encode(theta=alt.Theta(f"{t('count')}:Q", stack=True),
                   color=alt.Color(f"{t('verdict')}:N", sort=[LABEL[s] for s in ORDER], legend=None,
                                   scale=alt.Scale(domain=[LABEL[s] for s in ORDER], range=[HEX[s] for s in ORDER])),
                   opacity=alt.condition(hover, alt.value(1), alt.value(0.35)),
                   tooltip=[f"{t('verdict')}:N", f"{t('count')}:Q", alt.Tooltip(f"{t('share')}:Q", format=".1%")])
           .add_params(hover))
    centre = (alt.Chart(pd.DataFrame({"t": [f"{total}"]})).mark_text(size=28, fontWeight="bold", dy=-8)
              .encode(text="t:N"))
    sous = (alt.Chart(pd.DataFrame({"t": [t("checks")]})).mark_text(size=12, dy=16, opacity=0.7)
            .encode(text="t:N"))
    return (arc + centre + sous).properties(height=224, padding={"top": 12, "bottom": 12, "left": 4, "right": 4})


def section(titre, top=24):
    st.markdown(f"<div style='margin:{top}px 0 8px;font-size:1.75rem;font-weight:700;line-height:1.2'>{titre}</div>",
                unsafe_allow_html=True)


section(t("dashboard"), 20)
with st.container(border=True):
    g, d = st.columns(2, gap="large", vertical_alignment="center")
    with g:
        gc, gl = st.columns([1, 1], vertical_alignment="center")
        with gc:
            st.altair_chart(donut(), width="stretch")
        with gl:
            rows = "".join(
                f'<div style="display:flex;align-items:center;gap:10px;margin:7px 0;font-size:1.05rem">'
                f'<span style="color:{HEX[s]};font-size:1.5rem;line-height:1">&#9679;</span>'
                f'<span>{LABEL[s]} <b>{n[s]}</b></span></div>' for s in ORDER)
            st.markdown(f'<div style="display:flex;flex-direction:column;justify-content:center">{rows}</div>',
                        unsafe_allow_html=True)

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
            ia_rows = df[df.Source_verdict == "IA"]
            conf = f"{ia_rows.Confiance.astype(float).mean():.0%}" if len(ia_rows) else "n/a"
            st.markdown(t("top1", c=top.Champ, m=top.Matricule, p=top.Priorité) + "  \n"
                        + t("top_field", c=vc.index[0], n=int(vc.iloc[0])) + "  \n"
                        + t("by_ai", a=par_ia, b=total - n["OK"], c=conf))


def csv_bytes(d):  # séparateur ; et BOM UTF-8 : s'ouvre correctement dans Excel en français
    return d.drop(columns=["RefAlt", "Nature"], errors="ignore").to_csv(index=False, sep=";").encode("utf-8-sig")


section(t("investigate"))
with st.container(border=True):
    d1, d2, d3, d4 = st.columns(4)
    d1.download_button(t("dl_xlsx"), corroboria.to_excel_bytes(df), "rapport_corroboration.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    d2.download_button(t("dl_all"), csv_bytes(df), "corroboration_complet.csv", "text/csv")
    d3.download_button(t("dl_err"), csv_bytes(df[df.Statut.isin(["ERREUR", "A_REVUE_HUMAINE"])]),
                       "corroboration_erreurs.csv", "text/csv")
    d4.download_button(t("dl_just"), csv_bytes(df[df.Statut == "ECART_JUSTIFIE"]),
                       "corroboration_justifies.csv", "text/csv")
    if lang == "en":
        st.caption(t("free_text"))

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([f"{dot('ERREUR')} {t('tab_inv')}", f"{dot('ECART_JUSTIFIE')} {t('tab_just')}",
                                                  t("tab_field"), t("tab_all"), t("tab_gloss"), t("tab_set")])

    with tab1:
        err = a_investiguer
        if err.empty:
            st.success(t("no_err"))
        else:
            f1, f2 = st.columns(2)
            champs = f1.multiselect(t("f_field"), sorted(err.Champ.unique()))
            mats = f2.multiselect(t("f_emp"), sorted(err.Matricule.unique()))
            if champs:
                err = err[err.Champ.isin(champs)]
            if mats:
                err = err[err.Matricule.isin(mats)]
            show(err[COLS], Priorité=st.column_config.ProgressColumn(
                TR[lang]["cols"].get("Priorité", "Priorité"), min_value=0, max_value=100, format="%d / 100",
                help=t("prio_help", g=wn["gravite"], c=wn["confiance"], r=wn["recurrence"])))

            st.subheader(t("why"))
            if len(err):
                i = st.selectbox(t("pick"), err.index, format_func=lambda i:
                                 t("row", m=err.Matricule[i], c=err.Champ[i], p=err.Priorité[i]))
                r = df.loc[i]
                a, b = st.columns(2)
                a.metric(t("val_a"), r.ValeurSourceA)
                b.metric(t("val_b"), r.ValeurDestB)
                st.markdown(t("verdict_line", d=dot(r.Statut), l=LABEL[r.Statut],
                              o=TR[lang]["src"].get(r.Source_verdict, r.Source_verdict), c=r.Confiance))
                st.markdown(t("rule_line", x=r.Règle))
                st.markdown(t("expl_line", x=r.Explication))
                key = f"llm_{model}_{i}"
                if key not in st.session_state:
                    st.session_state[key] = llm.cached(r, model)
                if st.button(t("btn_llm", m=model), disabled=not llm_ok, help=t("btn_llm_h")):
                    with st.spinner(t("llm_spin")):
                        st.session_state[key] = llm.explain_row(r, model)
                    if st.session_state[key] is None:
                        st.warning(t("llm_none"))
                if st.session_state.get(key):
                    st.success(t("llm_expl", m=model, x=st.session_state[key]))
                if r.Cause_probable:
                    st.markdown(t("cause", x=r.Cause_probable))
                with st.expander(t("all_checks")):
                    show(df[df.Matricule == r.Matricule][["Champ", "ValeurSourceA", "ValeurDestB", "Statut"]])
                st.markdown(t("expert"))
                v = st.radio(t("correct"), ["ECART_JUSTIFIE", "ERREUR"], horizontal=True,
                             format_func=LABEL.get, index=0 if r.Statut == "ERREUR" else 1)
                if st.button(t("save_corr")):
                    with open(ia.BASE / "corrections.csv", "a", encoding="utf-8") as f:
                        f.write(f"{r.Matricule},{r.Champ},{v}\n")
                    st.session_state.ver += 1
                    st.rerun()

    with tab2:
        just = df[df.Statut == "ECART_JUSTIFIE"]
        st.caption(t("just_cap"))
        show(just[COLS[1:6] + ["Source_verdict", "Confiance", "Règle", "Explication"]])

    with tab3:
        res = (df.groupby(["Champ", "Statut"]).size().unstack(fill_value=0)
                 .reindex(columns=ORDER, fill_value=0).rename(columns=LABEL))
        st.bar_chart(res, color=[HEX[s] for s in ORDER], horizontal=True)
        st.dataframe(res, width="stretch")

    with tab4:
        show(df)

    with tab5:
        st.caption(t("gloss_cap"))
        st.dataframe(corroboria.glossary_fields(), width="stretch", hide_index=True)
        st.subheader(t("codes"))
        st.dataframe(pd.DataFrame(corroboria.GLOSSARY_CODES, columns=[t("code"), t("meaning")]),
                     width="stretch", hide_index=True)

    with tab6:
        st.subheader(t("set_title"))
        st.caption(t("set_intro"))

        def reset_settings():
            for k, v in W_DEF.items():
                st.session_state[f"w_{k}"] = v
            st.session_state.sev = {}

        sc = st.columns(3)
        for col, k in zip(sc, W_DEF):
            col.slider(t(f"w_{k}"), 0, 100, W_DEF[k], 5, format="%d %%", key=f"w_{k}")
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
