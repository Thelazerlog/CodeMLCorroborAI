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
TIMEOUT = 150

SYSTEM = (
    "Tu aides une personne non technique à comprendre un écart entre deux systèmes : A (RH, source de vérité) et "
    "B (Temps, cible). Le verdict est DÉJÀ décidé : ne le remets pas en cause. Tu disposes d'une FICHE DU CHAMP "
    "(explications officielles), de la LECTURE des valeurs et de l'analyse du moteur. Appuie-toi UNIQUEMENT sur ces éléments.\n"
    "Écris 3 phrases courtes, en français simple, sans jargon (jamais de nom de colonne sans l'expliquer) :\n"
    "1) « Ce que c'est : » ce que représente le champ, en mots courants, d'après la fiche.\n"
    "2) « Ce qu'on voit : » ce que contient chaque système (nomme les deux valeurs, en traduisant les codes d'après "
    "la lecture) et POURQUOI ils diffèrent, en reprenant l'analyse du moteur et la cause probable.\n"
    "3) « À vérifier : » UNE vérification concrète (quelle donnée regarder, dans quel système), cohérente avec la "
    "règle et la cause probable.\n"
    "N'invente aucune règle, aucun code, aucune valeur, aucun numéro absent des valeurs fournies. Si la fiche ne permet "
    "pas de conclure, dis-le simplement. Écris UNE seule fois ces 3 phrases, puis arrête-toi.\n\n"
    "Exemples de FORME (autres champs, à ne pas recopier) :\n"
    "- Ce que c'est : le nombre d'heures par semaine prévu pour le poste. Ce qu'on voit : le système A indique 35 heures "
    "alors que le système B indique 40 heures. À vérifier : dans le détail du poste, le nombre d'heures par semaine prévu, "
    "pour savoir lequel des deux est juste.\n"
    "- Ce que c'est : le type d'employé (permanent, occasionnel, stagiaire…). Ce qu'on voit : le système A indique "
    "« permanent temps plein » (JWN) et le système B « occasionnel » (WHX). À vérifier : la catégorie d'emploi de cet "
    "employé dans le système RH, puis le code attendu pour cette catégorie.")

GLOSSAIRE_IA = BASE / "glossaire_ia.json"
STATUT_FR = {"OK": "conforme", "ECART_JUSTIFIE": "écart justifié (différence expliquée)",
             "ERREUR": "vraie anomalie", "A_REVUE_HUMAINE": "à relire (confiance faible)"}


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


OPTIONS = {"temperature": 0, "num_predict": 200, "repeat_penalty": 1.2}


def nettoyer(texte):
    """Garde la première réponse si le petit modèle se répète, et une seule vérification « À vérifier »."""
    if not texte:
        return texte
    t = texte.strip().lstrip("-•* ").strip()
    blocs = re.split(r"(?=Ce que c'est\s*:)", t)
    t = next((b for b in blocs if b.strip()), t).strip()
    parts = re.split(r"(?=À vérifier\s*:)", t)
    if len(parts) > 2:
        t = (parts[0] + parts[1]).strip()
    return re.sub(r"\n\s*[-•*]\s*", "\n", t).strip()


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


def _prompt(row):
    champ = row["Champ"]
    cod = codes_ligne(row)
    return (f"FICHE DU CHAMP\n{fiche(champ)}\n" + (f"Codes de la ligne : {cod}\n" if cod else "")
            + f"\nLECTURE DES VALEURS\n- Système A : {lecture(champ, row['ValeurSourceA'])}\n"
            f"- Système B : {lecture(champ, row['ValeurDestB'])}\n\n"
            f"VERDICT DÉJÀ DÉCIDÉ : {STATUT_FR.get(row['Statut'], row['Statut'])} "
            f"(origine : {row['Source_verdict']}, confiance {row['Confiance']:.0%})\n"
            f"Règle appliquée par le moteur : {row['Règle']}\n"
            f"Analyse du moteur : {_analyse(row)}\n"
            f"Cause probable : {_cause(row)}")


def explain_row(row, model=None, device="auto"):
    """Explication LLM d'UNE ligne du rapport (appel à la demande, mis en cache). None si indisponible.

    device = "auto" : Ollama utilise le GPU NVIDIA s'il y en a un (sinon le CPU) ; "cpu" : force le CPU (num_gpu = 0)."""
    model = model or MODEL
    prompt = _prompt(row)
    key = hashlib.sha1((model + SYSTEM + prompt).encode("utf-8")).hexdigest()
    cache = _load()
    if key in cache:
        return cache[key]
    try:
        req = urllib.request.Request(
            f"{HOST}/api/chat", method="POST", headers={"Content-Type": "application/json"},
            data=json.dumps({"model": model, "stream": False, "options": {**OPTIONS, **({"num_gpu": 0} if device == "cpu" else {})},
                             "messages": [{"role": "system", "content": SYSTEM},
                                          {"role": "user", "content": prompt}]}).encode("utf-8"))
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            text = nettoyer(json.load(r)["message"]["content"])
    except Exception:
        return None
    cache[key] = text
    CACHE.parent.mkdir(exist_ok=True)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    return text


def cached(row, model=None):
    """Explication déjà en cache pour cette ligne et ce modèle (sans appeler le modèle)."""
    key = hashlib.sha1(((model or MODEL) + SYSTEM + _prompt(row)).encode("utf-8")).hexdigest()
    return _load().get(key)
