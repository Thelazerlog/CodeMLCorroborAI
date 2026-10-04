"""Démonstration en ligne de commande : un cas conforme, un écart justifié automatiquement, une vraie anomalie.

    python source/demo.py

Chaque cas montre les deux valeurs, le verdict, la règle appliquée, l'origine (règle déterministe ou IA locale), la confiance et
l'explication. Les fichiers fournis (data/) sont lus en lecture seule.
"""
import textwrap

import corroboria
import ia


def montrer(titre, r):
    print(f"\n=== {titre} " + "=" * max(0, 66 - len(titre)))
    print(f"Employé {r.Matricule} · champ {r.Champ}")
    print(f"  Système A (RH)    : {r.ValeurSourceA}")
    print(f"  Système B (Temps) : {r.ValeurDestB}")
    print(f"  Verdict           : {r.Statut}  (origine : {r.Source_verdict}, confiance {r.Confiance:.0%})")
    print(f"  Règle appliquée   : {r.Règle}")
    print("  Justification     :")
    print(textwrap.indent(textwrap.fill(str(r.Explication), 86), "      "))
    if r.Cause_probable:
        print(f"  Cause probable    : {r.Cause_probable}")
    if r.Priorité:
        print(f"  Priorité          : {r.Priorité}/100")


def main():
    df = ia.enrich(corroboria.run())
    n = df.Statut.value_counts()
    print(f"{len(df)} contrôles : {n.get('OK', 0)} conformes, {n.get('ECART_JUSTIFIE', 0)} écarts justifiés, "
          f"{n.get('ERREUR', 0)} vraies anomalies, {n.get('A_REVUE_HUMAINE', 0)} à relire.")
    montrer("CAS 1 - conforme", df[(df.Statut == "OK") & (df.Champ == "givenName")].iloc[0])
    montrer("CAS 2 - écart justifié automatiquement (règle)", df[df.Champ == "detailedStatus (encodage)"].iloc[0])
    montrer("CAS 3 - écart justifié automatiquement (IA locale)", df[(df.Statut == "ECART_JUSTIFIE") & (df.Champ == "contactEmail")].iloc[0])
    montrer("CAS 4 - vraie anomalie", df[df.Statut == "ERREUR"].sort_values("Priorité", ascending=False).iloc[0])


if __name__ == "__main__":
    main()
