"""Traduction à l'affichage (français -> anglais) des textes produits par le moteur : règles, causes probables, explications.

Le moteur reste en français (c'est la langue des rapports et des fichiers sources) ; seul l'affichage de l'application est traduit.
Les valeurs des systèmes, les noms de champs et les codes ne sont jamais traduits. Un texte inconnu est rendu tel quel.
"""
import re

# (motif, remplacement) appliqués dans l'ordre sur le texte entier ; \1, \2… = groupes capturés
MOTIFS = [
    # --- règles
    (r"^(Date de début d'affectation|Date d'effet du détail du poste) : source = date d'effet du poste \(DateEntréePoste\) ; B = règle transformée \(la plus récente entre DateEntréePoste et la date d'effet du dernier détail du poste\)$",
     lambda m: ("Assignment start date" if m.group(1).startswith("Date de début") else "Effective date of the position detail")
     + ": source = position effective date (DateEntréePoste); B = transformed rule (the latest of DateEntréePoste and the effective date of the position's last detail)"),
    (r"^B reflète la règle transformée \(date d'effet du dernier détail du poste, postérieure à DateEntréePoste\)$",
     "B reflects the transformed rule (effective date of the position's last detail, later than DateEntréePoste)"),
    (r"^Date d'expiration du poste : la plus ancienne entre DateSortiePoste et la fin de l'unité adm\. \(date d'effet du détail suivant - 1 jour si l'unité change ; sinon aucune\)$",
     "Position expiry date: earliest of DateSortiePoste and the end of the admin. unit (effective date of the next detail - 1 day if the unit changes; otherwise none)"),
    (r"^Date de fin du détail du poste \(même règle\) : la plus ancienne entre DateSortiePoste et la fin de l'unité adm\. \(date d'effet du détail suivant - 1 jour si l'unité change ; sinon aucune\)$",
     "End date of the position detail (same rule): earliest of DateSortiePoste and the end of the admin. unit (effective date of the next detail - 1 day if the unit changes; otherwise none)"),
    (r"^A = temporaire ; S = ni l'un ni l'autre$", "A = temporary; S = neither"),
    (r"^P = primaire$", "P = primary"),
    (r"^Code Remphor via motif, seulement si absence complète$", "Remphor code via reason, only if full absence"),
    (r"^DateRetourAnticipée seulement si absence complète$", "DateRetourAnticipée only if full absence"),
    (r"^Concaténation emploi \+ '-' \+ description$", "Concatenation: job + '-' + description"),
    (r"^Concaténation unité adm\. \+ '-' \+ description$", "Concatenation: admin. unit + '-' + description"),
    (r"^Complétude$", "Completeness"),
    (r"^Date d'embauche$", "Hire date"),
    (r"^Encodage$", "Encoding"),
    (r"^Gabarit courriel$", "Email template"),
    (r"^Heures norme poste$", "Position standard hours"),
    (r"^LibelléSite$", "SiteLabel"),
    (r"^Nom sans accents$", "Name without accents"),
    (r"^Prénom sans accents$", "First name without accents"),
    (r"^Règle situation d'emploi \(accès\)$", "Employment status rule (access)"),
    (r"^Règle type d'employé \(PERM/FT/EMPTP\)$", "Employee type rule (PERM/FT/EMPTP)"),
    (r"^Cohérence motif$", "Reason consistency"),
    (r"^Règle apprise$", "Learned rule"),
    # --- causes probables
    (r"^(\d+) écarts distincts sur (.*) : propagation incomplète probable$", r"\1 distinct discrepancies on \2: likely incomplete propagation"),
    (r"^(\d+) écarts distincts sur (.*) : même problème sur plusieurs lignes$", r"\1 distinct discrepancies on \2: same problem on several rows"),
    (r"^B contient toujours « (.*) » \((\d+) lignes\) : valeur par défaut probable$", r"B always contains « \1 » (\2 rows): likely default value"),
    (r"^écart isolé$", "isolated discrepancy"),
    (r"^Non précisée$", "Unspecified"),
    # --- explications du moteur
    (r"^Valeurs conformes \(aucune date de fin attendue\)$", "Matching values (no end date expected)"),
    (r"^Valeurs conformes à la règle du mapping$", "Values match the mapping rule"),
    (r"^Valeurs conformes$", "Matching values"),
    (r"^Courriel conforme à la règle$", "Email matches the rule"),
    (r"^Valeur attendue « (.*) », trouvée « (.*) »$", r"Expected value « \1 », found « \2 »"),
    (r"^Affectation (.*) \(poste (.*)\) absente du système B$", r"Assignment \1 (position \2) missing from system B"),
    (r"^Affectation absente du système A$", "Assignment missing from system A"),
    (r"^Courriel ne respecte pas le gabarit attendu \((.*)\)$", r"Email does not follow the expected template (\1)"),
    (r"^Gabarit respecté \(initiale \+ nom \+ 3 derniers chiffres\) mais préfixe d'environnement de dév\. et nom anonymisé différent : artefact de non-production$",
     "Template followed (initial + surname + last 3 digits) but dev environment prefix and different anonymised name: non-production artefact"),
    (r"^Libellé différent mais correspondance emploi→nom stable dans tout B : probable artefact d'anonymisation, à confirmer$",
     "Different label but the job→name mapping is stable throughout B: probable anonymisation artefact, to be confirmed"),
    (r"^Source vide ; détail du poste = (.*?)( : valeur reprise du détail)?$",
     lambda m: f"Source empty; position detail = {m.group(1)}" + (": value taken from the detail" if m.group(2) else "")),
    (r"^Libellé en UTF-8 mal décodé \(Ã¨ = è\) : valeur correcte, défaut d'encodage$", "Label in badly decoded UTF-8 (Ã¨ = è): value is correct, encoding defect"),
    (r"^Code de gestion des accès du motif ≠ code dans l'extraction source$", "Access management code of the reason ≠ code in the source extract"),
    (r"^Verdict corrigé par un expert fonctionnel\.$", "Verdict corrected by a functional expert."),
    (r"^Règle apprise \((\d+) corrections d'experts concordantes\)\.$", r"Learned rule (\1 matching expert corrections)."),
    (r"^\[règle initiale : (.*?)\] (.*)$", lambda m: f"[initial rule: {m.group(1)}] " + en(m.group(2))),
]

# vocabulaire des explications de l'IA (« IA : … (P(erreur) = 12%). Facteurs : … »)
FACTEURS = {"similarité des textes": "text similarity", "ratio de longueur": "length ratio", "valeur numérique": "numeric value",
            "écart relatif": "relative difference", "écart en jours": "difference in days", "valeur vide d'un côté": "empty on one side",
            "correspondance A→B stable dans tout le fichier": "A→B mapping stable across the whole file",
            "une valeur contient l'autre": "one value contains the other", "même structure (lettres/chiffres)": "same structure (letters/digits)",
            "même motif interne de chiffres répétés (ex. code répété dans le libellé/courriel)": "same internal repeated-digit pattern (e.g. code repeated in the label/email)",
            "valeur de référence secondaire disponible (détail du poste)": "secondary reference value available (position detail)",
            "B égale à la valeur de référence secondaire": "B equals the secondary reference value", "gravité du champ": "field severity"}
VERDICTS_IA = {"probablement une vraie erreur": "probably a real error", "probablement un écart acceptable": "probably an acceptable discrepancy",
               "cas incertain, à valider par un humain": "uncertain case, to be validated by a human"}

STATUTS = {"OK": "OK", "ECART_JUSTIFIE": "JUSTIFIED_DISCREPANCY", "ERREUR": "TRUE_ANOMALY", "A_REVUE_HUMAINE": "TO_REVIEW"}


def _ia(texte):
    """« IA : <verdict> (P(erreur) = x%). Facteurs : a = 0.1, b = 0.2. » -> anglais."""
    m = re.match(r"^IA : (.*?) \(P\(erreur\) = (\d+%)\)\. Facteurs : (.*)\.$", texte)
    if not m:
        return texte
    verdict = VERDICTS_IA.get(m.group(1), m.group(1))
    fact = m.group(3)
    for fr, eng in sorted(FACTEURS.items(), key=lambda kv: -len(kv[0])):
        fact = fact.replace(fr, eng)
    return f"AI: {verdict} (P(error) = {m.group(2)}). Factors: {fact}."


def en(texte):
    """Traduit un texte du moteur en anglais ; renvoie le texte inchangé s'il est inconnu."""
    if texte is None or not isinstance(texte, str) or not texte.strip():
        return texte
    if " | " in texte:
        return " | ".join(en(p) for p in texte.split(" | "))
    if texte.startswith("IA : "):
        return _ia(texte)
    for motif, rempl in MOTIFS:
        m = re.match(motif, texte)
        if m:
            return rempl(m) if callable(rempl) else m.expand(rempl)
    return texte


def traduire(texte, lang):
    return en(texte) if lang == "en" else texte
