"""LLM local (Ollama) : rédige les justifications en langage clair.

Le LLM ne change jamais un verdict : il reçoit des faits déjà établis (règle, valeurs A/B, verdict,
signaux de l'IA) et ne fait que les reformuler. Si Ollama est absent ou trop lent, on retombe sur
l'explication par gabarit. Aucune donnée ne quitte la machine (localhost uniquement).
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

BASE = Path(__file__).parent
CACHE = BASE / "outputs" / "llm_cache.json"
HOST = os.environ.get("OLLAMA_HOST_URL", "http://localhost:11434")
MODEL = os.environ.get("CORROBORIA_MODEL", "qwen2.5:3b")  # modèle par défaut
# profils proposés dans l'application : (libellé, identifiant Ollama, indication)
PROFILES = [("Équilibré", "qwen2.5:3b", "profil actuel, environ 20 à 30 s par explication sans GPU"),
            ("Rapide", "qwen2.5:1.5b", "environ 2 fois plus rapide, français moins soigné"),
            ("Précis", "qwen2.5:7b", "meilleure qualité, environ 2 à 3 fois plus lent")]
PROFILES_EN = {"qwen2.5:3b": ("Balanced", "current profile, about 20 to 30 s per explanation without a GPU"),
               "qwen2.5:1.5b": ("Fast", "about 2 times faster, less polished French"),
               "qwen2.5:7b": ("Accurate", "better quality, about 2 to 3 times slower")}


def profils(lang="fr"):
    """Profils (libellé, identifiant Ollama, indication) dans la langue de l'interface."""
    if lang != "en":
        return PROFILES
    return [(PROFILES_EN.get(m, (n, d))[0], m, PROFILES_EN.get(m, (n, d))[1]) for n, m, d in PROFILES]


TIMEOUT = 150

SYSTEM = (
    "Tu aides une personne non technique à comprendre un écart entre deux systèmes : A (RH, source de vérité) et "
    "B (Temps, cible). Le verdict est DÉJÀ décidé : ne le remets pas en cause. Tu disposes d'une FICHE DU CHAMP "
    "(explications officielles), de la LECTURE des valeurs, de l'analyse du moteur et de la RAISON DU VERDICT. "
    "Appuie-toi UNIQUEMENT sur ces éléments.\n"
    "Écris 4 phrases courtes, en français simple, sans jargon (jamais de nom de colonne sans l'expliquer) :\n"
    "1) « Ce que c'est : » ce que représente le champ, en mots courants, d'après la fiche.\n"
    "2) « Ce qu'on voit : » ce que contient chaque système (nomme les deux valeurs, en traduisant les codes d'après "
    "la lecture) et POURQUOI ils diffèrent, en reprenant l'analyse du moteur et la cause probable.\n"
    "3) « À vérifier : » UNE vérification concrète (quelle donnée regarder, dans quel système), cohérente avec la "
    "règle et la cause probable.\n"
    "4) « Pourquoi ce verdict : » en 2 ou 3 phrases, reprends les 3 volets de la RAISON DU VERDICT : (a) le STATUT exact, "
    "(b) la DÉCISION : explique comment la règle ou le modèle a conclu (probabilité d'erreur, facteurs, et si le champ est à "
    "100 % en écart justifié, dis que cela renforce l'idée d'un écart systématique), (c) la CONFIANCE : donne le pourcentage "
    "et dis s'il atteint ou non le seuil, et ce que cela implique pour le statut. Cite les chiffres exacts fournis.\n"
    "N'invente aucune règle, aucun code, aucune valeur, aucun numéro absent des valeurs fournies. Si la fiche ne permet "
    "pas de conclure, dis-le simplement. Écris UNE seule fois ces 4 phrases, puis arrête-toi.\n\n"
    "Exemples de FORME (autres champs, à ne pas recopier) :\n"
    "- Ce que c'est : le nombre d'heures par semaine prévu pour le poste. Ce qu'on voit : le système A indique 35 heures "
    "alors que le système B indique 40 heures. À vérifier : dans le détail du poste, le nombre d'heures par semaine prévu, "
    "pour savoir lequel des deux est juste. Pourquoi ce verdict : vraie anomalie, car la règle des heures attend la "
    "valeur du poste (35) et le système B en contient une autre.\n"
    "- Ce que c'est : le type d'employé (permanent, occasionnel, stagiaire…). Ce qu'on voit : le système A indique "
    "« permanent temps plein » (JWN) et le système B « occasionnel » (WHX). À vérifier : la catégorie d'emploi de cet "
    "employé dans le système RH, puis le code attendu pour cette catégorie. Pourquoi ce verdict : à relire (écart "
    "justifié), car le modèle penchait pour un écart acceptable avec 62 % de confiance, sous le seuil de 90 % : un humain doit trancher.")

SYSTEM_EN = (
    "You help a non-technical person understand a discrepancy between two systems: A (HR, source of truth) and "
    "B (Time, target). The verdict is ALREADY decided: do not question it. You have a FIELD SHEET (official explanations, "
    "in French), a READING of the values, the engine's analysis and the REASON FOR THE VERDICT. "
    "Rely ONLY on these elements.\n"
    "Write the whole answer IN ENGLISH (translate the French material), as 4 short sentences in plain language, no jargon "
    "(never a column name without explaining it):\n"
    "1) 'What it is:' what the field represents, in everyday words, based on the sheet.\n"
    "2) 'What we see:' what each system contains (name both values, translating the codes using the reading) and WHY "
    "they differ, using the engine's analysis and the probable cause.\n"
    "3) 'To check:' ONE concrete check (which data to look at, in which system), consistent with the rule and the probable cause.\n"
    "4) 'Why this verdict:' in 2 or 3 sentences, cover the 3 parts of the REASON FOR THE VERDICT: (a) the exact STATUS, "
    "(b) the DECISION: explain how the rule or the model concluded (error probability, factors, and if the field is 100% "
    "justified gaps, say this supports a systematic gap), (c) the CONFIDENCE: give the percentage and say whether it reaches "
    "the threshold and what that implies for the status. Quote the exact figures supplied.\n"
    "Do not invent any rule, code, value or number absent from the supplied values. If the sheet is not enough to "
    "conclude, say so simply. Write these 4 sentences ONCE, then stop.\n\n"
    "Example of FORM (other field, do not copy): What it is: the number of hours per week planned for the position. "
    "What we see: system A shows 35 hours while system B shows 40 hours. To check: in the position detail, the planned "
    "hours per week, to know which of the two is right. Why this verdict: true anomaly, because the hours rule expects "
    "the position's value (35) and system B holds a different one.")

GLOSSAIRE_IA = BASE / "glossaire_ia.json"
STATUT_FR = {"OK": "conforme", "ECART_JUSTIFIE": "écart justifié (différence expliquée)",
             "ERREUR": "vraie anomalie", "A_REVUE_HUMAINE": "à relire (confiance faible)",
             "ECART_SYSTEMATIQUE": "écart justifié systématique (présent sur 100 % des lignes de ce champ)",
             "A_REVUE_JUSTIFIE": "à relire (écart justifié)", "A_REVUE_ERREUR": "à relire (vraie anomalie)"}


def _hints():
    try:
        return json.loads(GLOSSAIRE_IA.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _glossaire():
    """Glossaire du mapping (Mapping.xlsx) et codes ; vides si les fichiers sont absents."""
    try:
        import corroboria
        return corroboria.glossary_fields(), dict(corroboria.GLOSSARY_CODES)
    except Exception:
        return None, {}


def _base(champ):
    return re.sub(r"\s*\(.*\)$", "", str(champ)).strip()  # « detailedStatus (encodage) » -> « detailedStatus »


def fiche(champ):
    """Fiche du champ : description, colonne du système A, règle du mapping et explication en langage courant."""
    base = _base(champ)
    g, _ = _glossaire()
    lignes = []
    if g is not None:
        m = g[g["Champ système B"].astype(str).str.contains(re.escape(base), regex=True)]
        for _, r in m.iterrows():
            desc = "" if str(r["Description"]) in ("nan", "") else f" = « {r['Description']} »"
            col = "" if str(r["Champ système A"]) in ("-", "nan") else f" (colonne « {r['Champ système A']} » du système A)"
            regle = str(r["Règle"])
            if len(regle) > 300:
                regle = regle[:300].rsplit(" ", 1)[0] + " […]"
            lignes.append(f"- Champ {base}{desc}{col}. Règle du mapping : {regle}")
    h = _hints().get(base)
    if h:
        lignes.append(f"- Pour comprendre : {h}")
    if not lignes:
        lignes.append(f"- Champ {base} : aucune fiche disponible, reste prudent.")
    return "\n".join(lignes)


def lecture(champ, valeur):
    """Traduction d'une valeur brute en mots (code connu, numéro-description, courriel)."""
    v = str(valeur).strip()
    base = _base(champ)
    _, codes = _glossaire()
    if v in codes:
        return f"{v} = {codes[v]}"
    if base in ("positionName", "divisionName") and "-" in v:
        num, desc = v.split("-", 1)
        return f"{v} = numéro {num}, description « {desc} »"
    if base == "contactEmail" and "@" in v:
        loc = v.split("@")[0]
        m = re.match(r"^(dev-\d+-v\d+_)(.*)$", loc)
        if m:
            return f"{v} = adresse d'un environnement de développement (préfixe « {m.group(1)} »), identifiant « {m.group(2)} »"
        return f"{v} = identifiant « {loc} »"
    return v


def codes_ligne(row):
    """Codes qui apparaissent dans la ligne, avec leur signification."""
    _, codes = _glossaire()
    vus = [c for c in (str(row["ValeurSourceA"]).strip(), str(row["ValeurDestB"]).strip()) if c in codes]
    return "; ".join(f"{c} = {codes[c]}" for c in dict.fromkeys(vus))


OPTIONS = {"temperature": 0, "num_predict": 700, "repeat_penalty": 1.2}


def nettoyer(texte):
    """Garde la première réponse si le petit modèle se répète, et une seule vérification « À vérifier »."""
    if not texte:
        return texte
    t = texte.strip().lstrip("-•* ").strip()
    blocs = re.split(r"(?=(?:Ce que c'est|What it is)\s*:)", t)
    t = next((b for b in blocs if b.strip()), t).strip()
    fin = re.search(r"(?:Pourquoi ce verdict|Why this verdict)\s*:", t)
    corps, verdict = (t[:fin.start()], t[fin.start():]) if fin else (t, "")
    parts = re.split(r"(?=(?:À vérifier|To check)\s*:)", corps)
    if len(parts) > 2:
        corps = (parts[0] + parts[1]).strip()
    if verdict:
        verdict = re.match(r"(?:Pourquoi ce verdict|Why this verdict)\s*:.*?(?=(?:Pourquoi ce verdict|Why this verdict)\s*:|\Z)", verdict, re.S).group(0)
        t = corps.rstrip() + " " + verdict.strip()
    else:
        t = corps
    t = re.sub(r"\n\s*[-•*]\s*", "\n", t).strip()
    fins = list(re.finditer(r"[.!?»)](?=\s|$)", t))
    if t and t[-1] not in ".!?»)" and fins:   # réponse coupée en plein milieu : on garde les phrases complètes
        t = t[:fins[-1].end()].strip()
    return t


def installed_models():
    """Modèles présents dans Ollama (liste vide si le serveur est arrêté)."""
    try:
        with urllib.request.urlopen(f"{HOST}/api/tags", timeout=2) as r:
            return [m["name"] for m in json.load(r).get("models", [])]
    except Exception:
        return []


def gpu_info():
    """GPU NVIDIA détectés via nvidia-smi (Windows et Linux) : liste de « nom (mémoire) », vide s'il n'y en a pas."""
    exe = shutil.which("nvidia-smi") or next((p for p in (
        r"C:\Windows\System32\nvidia-smi.exe", r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe",
        "/usr/bin/nvidia-smi", "/usr/local/nvidia/bin/nvidia-smi") if os.path.exists(p)), None)
    if not exe:
        return []
    try:
        out = subprocess.run([exe, "--query-gpu=name,memory.total", "--format=csv,noheader"], capture_output=True,
                             text=True, timeout=5, creationflags=0x08000000 if sys.platform == "win32" else 0)
        gpus = []
        for line in out.stdout.strip().splitlines():
            name, _, mem = line.partition(",")
            gpus.append(f"{name.strip()} ({mem.strip()})" if mem else name.strip())
        return gpus if out.returncode == 0 else []
    except Exception:
        return []


def processor(model=None):
    """« GPU » ou « CPU » si le modèle est chargé en mémoire dans Ollama, sinon None (d'après /api/ps)."""
    try:
        with urllib.request.urlopen(f"{HOST}/api/ps", timeout=2) as r:
            for m in json.load(r).get("models", []):
                if m.get("name") == (model or MODEL):
                    return "GPU" if m.get("size_vram", 0) > 0 else "CPU"
    except Exception:
        pass
    return None


def available(model=None):
    return (model or MODEL) in installed_models()


def _load():
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _analyse(row):
    """Analyse du moteur sans le jargon du modèle IA (facteurs, probabilités) ni le préfixe technique."""
    a = re.sub(r"^\[règle initiale : [^\]]*\]\s*", "", str(row["Explication"]))
    return a.split(" | IA :")[0].strip()


def _cause(row):
    c = str(row.get("Cause_probable") or "").strip()
    return c.replace("propagation incomplète probable", "même problème sur plusieurs lignes") if c else "aucune"


ORIGINES = {"règle": "règle déterministe du mapping", "IA": "modèle d'IA local (scikit-learn)",
            "expert": "correction d'un expert fonctionnel", "règle apprise": "règle apprise à partir de corrections d'experts"}


STATUT_COURT = {"OK": "conforme", "ECART_JUSTIFIE": "écart justifié", "ECART_SYSTEMATIQUE": "écart justifié (100 % des données)",
                "ERREUR": "vraie anomalie", "A_REVUE_JUSTIFIE": "à relire (écart justifié)", "A_REVUE_ERREUR": "à relire (vraie anomalie)",
                "A_REVUE_HUMAINE": "à relire"}


def raison(row, seuil=None, part=None):
    """Pourquoi la ligne a ce verdict, en 3 volets construits par le code (le LLM ne fait que les reformuler) :
    STATUT, DÉCISION (règle ou modèle, facteurs, part du champ en écart justifié) et CONFIANCE (par rapport au seuil).
    part = (nombre de lignes du champ en écart justifié, nombre de lignes du champ)."""
    st, conf = row["Statut"], float(row["Confiance"])
    origine = ORIGINES.get(row["Source_verdict"], str(row["Source_verdict"]))
    analyse = _analyse(row)
    expl = str(row["Explication"])
    revue = st in ("A_REVUE_JUSTIFIE", "A_REVUE_ERREUR", "A_REVUE_HUMAINE")
    statut = f"{STATUT_COURT.get(st, st)}"

    # --- décision
    if row["Source_verdict"] == "IA" or "IA :" in expl:
        m = re.search(r"IA : (.*?) \(P\(erreur\) = (\d+)%\)\. Facteurs : (.*?)\.?$", expl.split(" | ")[-1].strip())
        if m:
            decision = (f"le modèle d'IA local a jugé « {m.group(1)} » : il estime à {m.group(2)} % la probabilité d'une vraie erreur, "
                        f"surtout d'après ces facteurs : {m.group(3)}.")
        else:
            decision = f"décision du modèle d'IA local. Analyse : {analyse}"
    else:
        decision = f"{origine} « {row['Règle']} » : {analyse}"
    if part and part[1] >= 3 and part[0] == part[1]:
        decision += (f" De plus, 100 % des lignes de ce champ ({part[0]} sur {part[1]}) sont des écarts justifiés : "
                     "la différence est systématique, ce qui plaide pour un artefact connu et non pour une erreur isolée.")
    elif part and part[1] >= 3 and part[0] > 0:
        decision += f" Dans ce champ, {part[0]} lignes sur {part[1]} sont des écarts justifiés."
    if row["Source_verdict"] in ("expert", "règle apprise"):
        decision = f"{origine} ; l'expert a la priorité sur le moteur. " + decision

    # --- confiance
    if seuil is None:
        confiance = f"la confiance du verdict est de {conf:.0%}."
    elif revue:
        confiance = (f"la confiance est de {conf:.0%}, donc SOUS le seuil de {seuil} % réglé dans l'application : "
                     "le verdict n'est pas assez sûr, un humain doit trancher.")
    elif conf * 100 >= seuil:
        confiance = f"la confiance est de {conf:.0%}, au moins égale au seuil de {seuil} % : le verdict est retenu tel quel."
    else:
        confiance = f"la confiance est de {conf:.0%} (seuil de {seuil} %)."
    return f"STATUT : {statut}. DÉCISION : {decision} CONFIANCE : {confiance}"


def _prompt(row, seuil=None, part=None):
    champ = row["Champ"]
    cod = codes_ligne(row)
    return (f"FICHE DU CHAMP\n{fiche(champ)}\n" + (f"Codes de la ligne : {cod}\n" if cod else "")
            + f"\nLECTURE DES VALEURS\n- Système A : {lecture(champ, row['ValeurSourceA'])}\n"
            f"- Système B : {lecture(champ, row['ValeurDestB'])}\n\n"
            f"VERDICT DÉJÀ DÉCIDÉ : {STATUT_FR.get(row['Statut'], row['Statut'])} "
            f"(origine : {row['Source_verdict']}, confiance {row['Confiance']:.0%})\n"
            f"Règle appliquée par le moteur : {row['Règle']}\n"
            f"Analyse du moteur : {_analyse(row)}\n"
            f"Cause probable : {_cause(row)}\n"
            f"RAISON DU VERDICT : {raison(row, seuil, part)}")


def _complet(texte):
    """Une explication en cache coupée en plein milieu (ancienne limite de longueur) n'est jamais réutilisée."""
    return str(texte).rstrip().endswith((".", "!", "?", "»", ")"))


def explain_row(row, model=None, device="auto", lang="fr", seuil=None, part=None):
    """Explication LLM d'UNE ligne du rapport (appel à la demande, mis en cache). None si indisponible.

    device = "auto" : Ollama utilise le GPU NVIDIA s'il y en a un (sinon le CPU) ; "cpu" : force le CPU (num_gpu = 0)."""
    model = model or MODEL
    prompt = _prompt(row, seuil, part)
    system = SYSTEM_EN if lang == "en" else SYSTEM
    if lang == "en":
        prompt += "\n\nAnswer in English."
    key = hashlib.sha1((model + system + prompt).encode("utf-8")).hexdigest()
    cache = _load()
    if key in cache and _complet(cache[key]):
        return cache[key]
    try:
        req = urllib.request.Request(
            f"{HOST}/api/chat", method="POST", headers={"Content-Type": "application/json"},
            data=json.dumps({"model": model, "stream": False, "options": {**OPTIONS, **({"num_gpu": 0} if device == "cpu" else {})},
                             "messages": [{"role": "system", "content": system},
                                          {"role": "user", "content": prompt}]}).encode("utf-8"))
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            text = nettoyer(json.load(r)["message"]["content"])
    except Exception:
        return None
    cache[key] = text
    CACHE.parent.mkdir(exist_ok=True)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    return text


def cached(row, model=None, lang="fr", seuil=None, part=None):
    """Explication déjà en cache pour cette ligne, ce modèle et cette langue (sans appeler le modèle)."""
    system, prompt = (SYSTEM_EN, _prompt(row, seuil, part) + "\n\nAnswer in English.") if lang == "en" else (SYSTEM, _prompt(row, seuil, part))
    key = hashlib.sha1(((model or MODEL) + system + prompt).encode("utf-8")).hexdigest()
    texte = _load().get(key)
    return texte if texte and _complet(texte) else None
