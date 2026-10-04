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
