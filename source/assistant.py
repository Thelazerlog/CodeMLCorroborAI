"""Assistant (chatbot) : questions courantes sur les résultats, définitions du glossaire et pilotage des filtres du tableau.

Le code comprend la question (mots-clés), calcule sur les données et répond : les chiffres viennent toujours des données, jamais
d'un modèle. Pour expliquer une ligne, l'assistant ouvre le bandeau « Explication IA locale » (LLM local, appelé à la demande).
Il est en lecture seule : il ne change ni un statut ni une règle.

repondre(question, df, lang, ctx) -> {"texte": str, "actions": {...}} ; les actions sont appliquées par l'application :
  statuts (liste de verdicts à afficher), champs, employe, reset, seuil, ouvrir (index de la ligne à expliquer).
"""
import re
import unicodedata

import corroboria
import llm

REVUES = ["A_REVUE_JUSTIFIE", "A_REVUE_ERREUR"]
STATUTS = [(r"anomal|erreur|error", "ERREUR"), (r"systemati", "ECART_SYSTEMATIQUE"), (r"justifi(?!e?s? systemati)", "ECART_JUSTIFIE"), (r"relire|revue|review", "A_REVUE"),
           (r"conforme|compliant|\bok\b", "OK")]
LABEL = {"fr": {"ERREUR": "vraie anomalie", "ECART_JUSTIFIE": "écart justifié", "ECART_SYSTEMATIQUE": "écart justifié (100 % des données)", "A_REVUE_JUSTIFIE": "à relire (écart justifié)", "A_REVUE_ERREUR": "à relire (vraie anomalie)", "OK": "conforme"},
         "en": {"ERREUR": "true anomaly", "ECART_JUSTIFIE": "justified gap", "ECART_SYSTEMATIQUE": "justified gap (100% of the data)", "A_REVUE_JUSTIFIE": "to review (justified gap)", "A_REVUE_ERREUR": "to review (true anomaly)", "OK": "compliant"}}
SYNONYMES = {r"courriel|email|e-mail|\bmail\b|adresse": ["contactEmail"], r"contrat|type d'employe|type of employee|employee type": ["contractTypeCode"],
             r"\bheures?\b|\bhours?\b": ["weeklyHoursOverride", "dailyHoursOverride"], r"\bpostes?\b|\broles?\b|\bposition": ["positionName", "positionId", "positionCode"],
             r"\bsites?\b|emplacement|location": ["siteName", "siteCode"], r"date d'embauche|embauche|hire": ["onboardDate"],
             r"\bprenom|first name": ["givenName"], r"\bnom de famille|last name|surname": ["surname"],
             r"situation d'emploi|absence": ["detailedStatus", "statusReasonCode", "expectedReturnDate"],
             r"departement|direction|division": ["divisionId", "divisionName", "divisionCode"],
             r"affectation|assignment": ["isPrimaryAssignment", "isTemporaryAssignment", "Enregistrement"],
             r"date d'entree|date d'effet": ["assignmentStartDate", "termStartDate"]}

T = {"fr": {
    "aide": "Je réponds aux questions courantes et je pilote le tableau. **Clique sur une question** ci-dessous, ou écris la tienne "
            "(« Montre-moi les anomalies de l'employé X », « Combien d'écarts justifiés sur les courriels ? », « Que veut dire WHX ? »…).",
    "inconnu": "Je ne sais répondre qu'aux questions courantes (comptages, employé ou champ le plus touché, définitions, "
               "affichage du tableau, explication d'une ligne). Dis « aide » pour des exemples.",
    "reset": "Filtres réinitialisés : le tableau montre à nouveau les lignes « à relire ».",
    "seuil": "Seuil de confiance réglé à {n} %.", "seuil_non": "Donne un seuil entre 0 et 100, par exemple « mets le seuil à 95 ».",
    "total": "Il y a **{n}** ligne(s){ctx}.", "total_0": "Aucune ligne{ctx}.",
    "ctx_champ": " sur {c}", "ctx_emp": " pour l'employé {e}",
    "detail": "Répartition par champ : {d}.", "proposer": "Dis « montre-moi » pour les afficher dans le tableau.",
    "ventil": "Par statut{ctx} : {d}.",
    "top_emp": "Employés avec le plus de lignes « {s} » : {d}.", "top_champ": "Champs avec le plus de lignes « {s} » : {d}.",
    "rien": "Aucune ligne « {s} » pour le moment.",
    "montre": "J'ai filtré le tableau : **{n}** ligne(s){ctx}. Descends à « Données sélectionnées ».",
    "montre_0": "Aucune ligne ne correspond{ctx}. J'ai quand même réglé les filtres.",
    "montre_vague": "Dis-moi quoi afficher : un statut (anomalies, écarts justifiés, à relire), un employé (matricule) ou un champ.",
    "explique": "J'ouvre l'explication de la ligne **{c}** de l'employé **{e}** dans le bandeau en bas de l'écran.",
    "explique_non": "Je ne trouve pas d'écart pour {ctx}. Précise un employé (matricule) et un champ.",
    "def_champ": "**{c}**\n{f}", "def_code": "**{c}** : {m}", "def_non": "Je ne trouve pas ce terme dans le glossaire. Essaie un nom de champ (ex. positionName) ou un code (ex. WHX).",
    "bilan": "**{n}** contrôles : {d}. Conformité : **{p}**. Champ le plus touché par les anomalies : {c}. À vérifier : {r} sur {t}.",
    "progres": "Il reste **{r}** ligne(s) « à relire » à vérifier sur {t} (barre de revue humaine du tableau de bord).",
    "effet": "Effet des retours d'experts : {a} ligne(s) corrigée(s) par un expert, {b} verdict(s) changé(s) par les règles apprises, {c} par le modèle, {d} au total.",
    "sep": " ; ", "all": "tous les statuts"},
    "en": {
    "aide": "I answer common questions and drive the table. **Click a question** below, or type your own "
            "(\"Show me the anomalies of employee X\", \"How many justified gaps on emails?\", \"What does WHX mean?\"...).",
    "inconnu": "I only know common questions (counts, most affected employee or field, definitions, table display, "
               "row explanation). Say \"help\" for examples.",
    "reset": "Filters reset: the table shows the \"to review\" rows again.",
    "seuil": "Confidence threshold set to {n}%.", "seuil_non": "Give a threshold between 0 and 100, for example \"set the threshold to 95\".",
    "total": "There are **{n}** row(s){ctx}.", "total_0": "No row{ctx}.",
    "ctx_champ": " on {c}", "ctx_emp": " for employee {e}",
    "detail": "By field: {d}.", "proposer": "Say \"show me\" to display them in the table.",
    "ventil": "By status{ctx}: {d}.",
    "top_emp": "Employees with the most \"{s}\" rows: {d}.", "top_champ": "Fields with the most \"{s}\" rows: {d}.",
    "rien": "No \"{s}\" row for now.",
    "montre": "I filtered the table: **{n}** row(s){ctx}. Scroll down to \"Selected data\".",
    "montre_0": "No row matches{ctx}. I still set the filters.",
    "montre_vague": "Tell me what to display: a status (anomalies, justified gaps, to review), an employee (ID) or a field.",
    "explique": "Opening the explanation of row **{c}** for employee **{e}** in the banner at the bottom of the screen.",
    "explique_non": "I cannot find a gap for {ctx}. Specify an employee (ID) and a field.",
    "def_champ": "**{c}**\n{f}", "def_code": "**{c}**: {m}", "def_non": "I cannot find this term in the glossary. Try a field name (e.g. positionName) or a code (e.g. WHX).",
    "bilan": "**{n}** checks: {d}. Compliance: **{p}**. Field most affected by anomalies: {c}. To check: {r} out of {t}.",
    "progres": "**{r}** \"to review\" row(s) left to check out of {t} (human review bar of the dashboard).",
    "effet": "Effect of expert feedback: {a} row(s) corrected by an expert, {b} verdict(s) changed by learned rules, {c} by the model, {d} in total.",
    "sep": "; ", "all": "all statuses"}}


def norm(s):
    s = unicodedata.normalize("NFD", str(s)).encode("ascii", "ignore").decode().lower()
    return s.replace("’", "'")


def entites(q, df):
    """Statuts, champs et employé cités dans la question (q normalisée)."""
    statuts = [c for motif, code in STATUTS if re.search(motif, q) for c in (REVUES if code == "A_REVUE" else [code])]
    if "ECART_JUSTIFIE" in statuts and "ECART_SYSTEMATIQUE" not in statuts:   # « écarts justifiés » couvre aussi les systématiques
        statuts.append("ECART_SYSTEMATIQUE")
    champs = []
    for c in sorted(df.Champ.unique(), key=len, reverse=True):
        base = re.sub(r"\s*\(.*\)$", "", c)
        if norm(base) in q and base not in champs:
            champs.append(base)
    if not champs:
        for motif, noms in SYNONYMES.items():
            if re.search(motif, q):
                champs += [n for n in noms if n in set(df.Champ.map(lambda x: re.sub(r"\s*\(.*\)$", "", x))) and n not in champs]
    matricules = set(df.Matricule.astype(str))
    emp = next((m for m in re.findall(r"\b\d{5,9}\b", q) if m in matricules), None)
    return statuts, champs, emp


def _masque(df, statuts, champs, emp):
    m = df.Statut.notna()
    if statuts:
        m &= df.Statut.isin(statuts)
    if champs:
        m &= df.Champ.map(lambda x: re.sub(r"\s*\(.*\)$", "", x)).isin(champs)
    if emp:
        m &= df.Matricule.astype(str) == emp
    return m


def _contexte(L, champs, emp):
    return (T[L]["ctx_champ"].format(c=", ".join(champs)) if champs else "") + (T[L]["ctx_emp"].format(e=emp) if emp else "")


def _compte(serie, n=3):
    vc = serie.value_counts().head(n)
    return ", ".join(f"{i} ({v})" for i, v in vc.items())


def _definition(q, df, L):
    codes = {c.lower(): (c, m) for c, m in corroboria.GLOSSARY_CODES}
    for mot in re.findall(r"[a-z]{3,}", q):
        if mot in codes:
            c, m = codes[mot]
            return {"texte": T[L]["def_code"].format(c=c, m=m), "actions": {}}
    _, champs, _ = entites(q, df)
    brut = [c for c in df.Champ.unique() if norm(re.sub(r"\s*\(.*\)$", "", c)) in q]
    for c in (brut or champs)[:1]:
        base = re.sub(r"\s*\(.*\)$", "", c)
        return {"texte": T[L]["def_champ"].format(c=base, f=llm.fiche(base)), "actions": {}}
    return {"texte": T[L]["def_non"], "actions": {}}


SUGGESTIONS = {
    "fr": ["Combien de vraies anomalies ?", "Quel employé a le plus d'anomalies ?", "Quel champ est le plus touché ?", "Montre-moi les anomalies de l'employé {e}",
           "Explique la ligne de l'employé {e} sur {c}", "C'est quoi {c} ?", "Que veut dire WHX ?", "Où en suis-je ?", "Mets le seuil à 95",
           "Réinitialise les filtres"],
    "en": ["How many true anomalies?", "Which employee has the most anomalies?", "Which field is most affected?", "Show me the anomalies of employee {e}",
           "Explain the row of employee {e} on {c}", "What is {c}?", "What does WHX mean?", "Where am I?", "Set the threshold to 95", "Reset the filters"]}


def suggestions(df, lang="fr"):
    """Questions proposées sous forme de boutons : toutes comprises par l'assistant, avec des valeurs réelles (employé, champ)."""
    an = df[df.Statut == "ERREUR"]
    e = str(an.Matricule.value_counts().index[0]) if len(an) else str(df.Matricule.iloc[0])
    c = re.sub(r"\s*\(.*\)$", "", an.Champ.value_counts().index[0]) if len(an) else "positionName"
    return [s.format(e=e, c=c) for s in SUGGESTIONS.get(lang, SUGGESTIONS["fr"])]


def repondre(question, df, lang="fr", ctx=None):
    out = _repondre(question, df, lang, ctx)
    if out["texte"] in (T.get(lang, T["fr"])["aide"], T.get(lang, T["fr"])["inconnu"], T.get(lang, T["fr"])["montre_vague"]):
        out["suggestions"] = suggestions(df, lang)  # les exemples sont des boutons cliquables dans l'application
    return out


def _repondre(question, df, lang="fr", ctx=None):
    """Interprète une question courante et renvoie le texte de la réponse et les actions à appliquer à l'écran."""
    L = lang if lang in T else "fr"
    ctx = ctx or {}
    q = norm(question)
    statuts, champs, emp = entites(q, df)
    lab = LABEL[L]
    t = T[L]

    if re.search(r"(reinitial|efface|enleve|supprime|retire|remets? a zero|reset|clear)\w*.*(filtre|filter)|^(reinitial|reset)", q):
        return {"texte": t["reset"], "actions": {"reset": True}}
    if re.search(r"seuil|threshold", q):
        n = [int(x) for x in re.findall(r"\b\d{1,3}\b", q) if 0 <= int(x) <= 100]
        return ({"texte": t["seuil"].format(n=n[0]), "actions": {"seuil": n[0]}} if n else {"texte": t["seuil_non"], "actions": {}})
    if re.search(r"\bexplique|\bexpliquer|\bpourquoi|\bexplain|\bwhy\b", q):
        if emp or champs:
            cand = df[_masque(df, [s for s in ("ERREUR", *REVUES, "ECART_JUSTIFIE", "ECART_SYSTEMATIQUE") if not statuts or s in statuts], champs, emp)]
            cand = cand.sort_values("Priorité", ascending=False)
            if len(cand):
                r = cand.iloc[0]
                return {"texte": t["explique"].format(c=r.Champ, e=r.Matricule),
                        "actions": {"ouvrir": int(cand.index[0]), "statuts": [r.Statut], "champs": [re.sub(r"\s*\(.*\)$", "", r.Champ)],
                                    "employe": str(r.Matricule)}}
        return {"texte": t["explique_non"].format(ctx=_contexte(L, champs, emp).strip() or "?"), "actions": {}}
    if re.search(r"c'est quoi|qu'est.ce|que (veut dire|signifie)|definition|signification|what is|what does|meaning|que sont", q):
        return _definition(q, df, L)
    if re.search(r"\b(montre|montrer|affiche|afficher|filtre|filtrer|liste|lister|voir|show|display|list|filter)\w*", q):
        if not (statuts or champs or emp):
            return {"texte": t["montre_vague"], "actions": {}}
        n = int(_masque(df, statuts, champs, emp).sum())
        txt = (t["montre"] if n else t["montre_0"]).format(n=n, ctx=(" (" + ", ".join(lab[s] for s in statuts) + ")" if statuts else "")
                                                         + _contexte(L, champs, emp))
        return {"texte": txt, "actions": {"statuts": statuts, "champs": champs, "employe": emp}}
    if re.search(r"reste|restant|a verifier|remaining|left|to check|ou en (suis|est)|where am i|where are we|avancement|progress", q) and not (statuts or champs or emp):
        if ctx.get("total") is not None:
            return {"texte": t["progres"].format(r=ctx.get("restant", 0), t=ctx["total"]), "actions": {}}
    if re.search(r"combien|nombre de|how many|\bcount", q):
        sts = statuts or None
        m = _masque(df, sts, champs, emp)
        n = int(m.sum())
        c = _contexte(L, champs, emp)
        pref = (" (" + ", ".join(lab[s] for s in statuts) + ")") if statuts else ""
        out = (t["total"] if n else t["total_0"]).format(n=n, ctx=pref + c)
        if n and not statuts:
            out += " " + t["ventil"].format(ctx=c, d=t["sep"].join(f"{lab[s]} {int((df[m].Statut == s).sum())}"
                                                                    for s in ("OK", "ECART_JUSTIFIE", "ECART_SYSTEMATIQUE", "ERREUR", *REVUES)
                                                                    if (df[m].Statut == s).any()))
        elif n and not champs and statuts:
            out += " " + t["detail"].format(d=_compte(df[m].Champ))
        return {"texte": out + (" " + t["proposer"] if n else ""), "actions": {}}
    if re.search(r"quel(le)?s? (employe|matricule|personne)|which employee|who has|qui a", q):
        s = (statuts or ["ERREUR"])[0]
        m = _masque(df, [s], champs, None)
        return {"texte": t["top_emp"].format(s=lab[s], d=_compte(df[m].Matricule.astype(str))) if m.any() else t["rien"].format(s=lab[s]),
                "actions": {}}
    if re.search(r"quel(le)?s? (champ|colonne|type d'erreur)|which (field|column)", q):
        s = (statuts or ["ERREUR"])[0]
        m = _masque(df, [s], None, emp)
        return {"texte": t["top_champ"].format(s=lab[s], d=_compte(df[m].Champ)) if m.any() else t["rien"].format(s=lab[s]), "actions": {}}
    if re.search(r"effet|changed|change apres|apres mes corrections|after my corrections", q) and ctx.get("effet"):
        e = ctx["effet"]
        return {"texte": t["effet"].format(a=e["corriges_par_expert"], b=e["changes_par_regles_apprises"], c=e["changes_par_le_modele"],
                                           d=e["total_changes"]), "actions": {}}
    if re.search(r"resume|bilan|synthese|summary|overview|ou en (suis|est)|where am i|where are we|progress|avancement", q):
        n = len(df)
        d = t["sep"].join(f"{lab[s]} {int((df.Statut == s).sum())}" for s in ("OK", "ECART_JUSTIFIE", "ECART_SYSTEMATIQUE", "ERREUR", *REVUES)
                          if (df.Statut == s).any())
        an = df[df.Statut == "ERREUR"]
        return {"texte": t["bilan"].format(n=n, d=d, p=f"{(df.Statut == 'OK').mean():.0%}", c=(an.Champ.value_counts().index[0] if len(an) else "-"),
                                           r=ctx.get("restant", "?"), t=ctx.get("total", "?")), "actions": {}}
    if re.search(r"\baide\b|\bhelp\b|que peux|what can|exemple|bonjour|hello|salut|\bhi\b", q):
        return {"texte": t["aide"], "actions": {}}
    return {"texte": t["inconnu"], "actions": {}}
