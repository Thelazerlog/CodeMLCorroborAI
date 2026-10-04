"""Serveur de démonstration pour les captures du guide : même application, mais journal et règles dans un dossier TEMPORAIRE,
pré-rempli avec 3 corrections concordantes d'un expert (de quoi proposer une règle). Les vrais fichiers ne sont jamais touchés.

    python -m streamlit run scripts/guide/serveur_demo.py --server.port 8621 --server.headless true
"""
import runpy
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))

import corroboria  # noqa: E402
import retours  # noqa: E402

DEMO = Path(tempfile.gettempdir()) / "corroboria_demo_guide"
DEMO.mkdir(exist_ok=True)
retours.JOURNAL, retours.REGLES = DEMO / "corrections.csv", DEMO / "regles_apprises.json"

if not retours.JOURNAL.exists():  # 3 libellés de poste que l'expert juge erronés (graine de la démonstration)
    import ia  # noqa: E402

    brut = ia.enrich(corroboria.run())
    cibles = brut[(brut.Champ == "positionName") & (brut.Statut != "OK")].head(3)
    for r in cibles.itertuples():
        retours.ajouter(r.Matricule, r.Champ, "ERREUR", motif="erreur_confirmee", commentaire="le numéro d'emploi diffère : ce n'est pas le même poste",
                        auteur="expert.fonctionnel", valeur_a=r.ValeurSourceA, valeur_b=r.ValeurDestB, regle=r.Règle, ancien=r.Statut)

runpy.run_path(str(RACINE / "app.py"), run_name="__main__")
