"""GPU NVIDIA pour le LLM local : détection (nvidia-smi) et option envoyée à Ollama (simulées, sans GPU ni Ollama)."""
import io
import json
import subprocess

import pandas as pd

import llm

ROW = pd.Series({"Champ": "contractTypeCode", "Règle": "r", "ValeurSourceA": "JWN", "ValeurDestB": "XFLR", "Statut": "ERREUR",
                 "Source_verdict": "règle", "Confiance": 1.0, "Explication": "e", "Cause_probable": ""})


def test_gpu_detecte_via_nvidia_smi(monkeypatch):
    monkeypatch.setattr(llm.shutil, "which", lambda _: "nvidia-smi")
    monkeypatch.setattr(llm.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(
        a, 0, stdout="NVIDIA GeForce RTX 4070, 12282 MiB\n", stderr=""))
    assert llm.gpu_info() == ["NVIDIA GeForce RTX 4070 (12282 MiB)"]


def test_aucun_gpu(monkeypatch):
    monkeypatch.setattr(llm.shutil, "which", lambda _: None)
    monkeypatch.setattr(llm.os.path, "exists", lambda _: False)
    assert llm.gpu_info() == []


def _capture(monkeypatch, tmp_path):
    sent = {}

    class Rep(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    def fake_urlopen(req, timeout=None):
        sent.update(json.loads(req.data))
        return Rep(json.dumps({"message": {"content": "ok"}}).encode())

    monkeypatch.setattr(llm.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(llm, "CACHE", tmp_path / "cache.json")
    return sent


def test_cpu_force_num_gpu_zero(monkeypatch, tmp_path):
    sent = _capture(monkeypatch, tmp_path)
    assert llm.explain_row(ROW, "m", device="cpu") == "ok"
    assert sent["options"]["num_gpu"] == 0


def test_auto_laisse_ollama_choisir_le_gpu(monkeypatch, tmp_path):
    sent = _capture(monkeypatch, tmp_path)
    llm.explain_row(ROW, "m2", device="auto")
    assert "num_gpu" not in sent["options"]


def test_explication_en_anglais_prompt_et_cache_distincts(monkeypatch, tmp_path):
    envoye = {}

    class Rep:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return json.dumps({"message": {"content": "What it is: x. What we see: y. To check: z."}}).encode()

    def faux(req, timeout=0):
        envoye.update(json.loads(req.data))
        return Rep()
    monkeypatch.setattr(llm, "CACHE", tmp_path / "c.json")
    monkeypatch.setattr(llm.urllib.request, "urlopen", faux)
    assert llm.explain_row(ROW, "m", lang="en").startswith("What it is")
    assert "IN ENGLISH" in envoye["messages"][0]["content"] and envoye["messages"][1]["content"].endswith("Answer in English.")
    assert llm.cached(ROW, "m", "en") and llm.cached(ROW, "m", "fr") is None   # le cache distingue les langues


def test_raison_du_verdict_a_relire_cite_confiance_et_seuil():
    r = ROW.copy()
    r["Statut"], r["Confiance"], r["Source_verdict"] = "A_REVUE_JUSTIFIE", 0.62, "IA"
    r["Explication"] = "[règle initiale : ECART_JUSTIFIE] x | IA : cas incertain (P(erreur) = 41%). Facteurs : a = 1."
    txt = llm.raison(r, 90)
    assert "écart justifié" in txt and "62%" in txt and "90 %" in txt and "41 %" in txt
    assert "RAISON DU VERDICT" in llm._prompt(r, 90) and "Pourquoi ce verdict" in llm.SYSTEM and "Why this verdict" in llm.SYSTEM_EN


def test_nettoyer_conserve_l_explication_du_verdict():
    assert llm.nettoyer("Ce que c'est : a. À vérifier : c. À vérifier : z. Pourquoi ce verdict : d.").endswith("Pourquoi ce verdict : d.")


def test_nettoyer_supprime_la_phrase_coupee():
    brut = "Ce que c'est : a. À vérifier : c. Pourquoi ce verdict : écart justifié. Confiance de 88 %. La cause probable est que"
    assert llm.nettoyer(brut).endswith("Confiance de 88 %.")


def test_cache_ignore_une_explication_tronquee(monkeypatch, tmp_path):
    monkeypatch.setattr(llm, "CACHE", tmp_path / "c.json")
    cle = __import__("hashlib").sha1(("m" + llm.SYSTEM + llm._prompt(ROW)).encode("utf-8")).hexdigest()
    (tmp_path / "c.json").write_text(json.dumps({cle: "Ce que c'est : a. La cause probable est que"}), encoding="utf-8")
    assert llm.cached(ROW, "m") is None
    (tmp_path / "c.json").write_text(json.dumps({cle: "Ce que c'est : a."}), encoding="utf-8")
    assert llm.cached(ROW, "m") == "Ce que c'est : a."
