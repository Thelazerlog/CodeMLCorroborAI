"""LLM local (Ollama) : rédige les justifications en langage clair.

Le LLM ne change jamais un verdict : il reçoit des faits déjà établis (règle, valeurs A/B, verdict,
signaux de l'IA) et ne fait que les reformuler. Si Ollama est absent ou trop lent, on retombe sur
l'explication par gabarit. Aucune donnée ne quitte la machine (localhost uniquement).
"""
import hashlib
import json
import os
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
TIMEOUT = 90

SYSTEM = (
    "Tu rédiges la justification d'un écart de données entre le système A (RH, source de vérité) et le "
    "système B (Temps, cible). Le verdict est DÉJÀ décidé : ne le commente pas et ne dis jamais qu'il est "
    "« raisonnable ». Écris EXACTEMENT 2 phrases en français :\n"
    "1) Le constat : « Pour <champ>, le système A a <valeur A> mais le système B contient <valeur B>. » "
    "puis, en une demi-phrase, ce que dit la règle appliquée.\n"
    "2) Une action concrète : commence par « À vérifier : » puis UNE seule vérification précise, déduite "
    "de la règle ou de la cause probable fournies.\n"
    "Interdits : le mot « propagation », les généralités, toute valeur, règle ou cause absente des faits fournis.\n"
    "Exemple de FORME (autre champ, ne pas recopier) : « Pour weeklyHoursOverride, le système A a 35 mais le "
    "système B contient 40 ; la règle reprend les heures de la norme du poste. À vérifier : si la valeur 40 est "
    "une valeur par défaut appliquée à tous les postes dans le système B. »")


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


def _prompt(row):
    return (f"Champ : {row['Champ']}\nRègle appliquée : {row['Règle']}\n"
            f"Valeur système A : {row['ValeurSourceA']}\nValeur système B : {row['ValeurDestB']}\n"
            f"Verdict : {row['Statut']} (origine : {row['Source_verdict']}, confiance {row['Confiance']:.0%})\n"
            f"Analyse automatique : {row['Explication']}\n"
            f"Cause probable : {row.get('Cause_probable') or 'aucune'}")


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
            data=json.dumps({"model": model, "stream": False, "options": {"temperature": 0, "num_predict": 110, **({"num_gpu": 0} if device == "cpu" else {})},
                             "messages": [{"role": "system", "content": SYSTEM},
                                          {"role": "user", "content": prompt}]}).encode("utf-8"))
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            text = json.load(r)["message"]["content"].strip()
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
