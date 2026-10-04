"""Génère les captures d'écran du guide d'utilisation (docs/img_guide/*.png) en pilotant l'application avec Chrome (Selenium).

Prérequis : Chrome et `pip install selenium`.
Usage :
    python -m streamlit run app.py --server.port 8620 --server.headless true            # application
    python -m streamlit run source/scripts/guide/serveur_demo.py --server.port 8621 --server.headless true   # démo des corrections
    python source/scripts/guide/capture_guide.py            # utilise http://localhost:8620 et http://localhost:8621
Les fichiers réels (corrections.csv, regles_apprises.json) ne sont jamais modifiés : la démo des corrections utilise un dossier temporaire.
"""
import os
import sys
import tempfile
import time
from pathlib import Path

import pandas as pd
from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

ROOT = Path(__file__).resolve().parents[3]
IMG = ROOT / "docs" / "img_guide"
IMG.mkdir(parents=True, exist_ok=True)
URL = os.environ.get("CORRO_URL", "http://localhost:8620/")
URL_DEMO = os.environ.get("CORRO_URL_DEMO", "http://localhost:8621/")
CHROME = os.environ.get("CHROME_BIN", r"C:\Program Files\Google\Chrome\Application\chrome.exe")

JS_BOITE = """
const txt = arguments[0];
const leaf = [...document.querySelectorAll('[data-testid="stMain"] *')].find(e => e.children.length == 0 && e.textContent.trim() == txt);
if (!leaf) return null;
let e = leaf;
while (e) { const cs = getComputedStyle(e); if (parseFloat(cs.borderTopWidth) > 0 && e.getBoundingClientRect().width > 500 && e.getBoundingClientRect().height > 100) return e; e = e.parentElement; }
return null;
"""
JS_HOTE = "return [...document.querySelectorAll('*')].find(e => e.shadowRoot && e.shadowRoot.querySelector('.corro')) || null;"


def demarrer(taille=(1500, 1400)):
    o = Options()
    o.add_argument("--headless=new")
    o.add_argument(f"--window-size={taille[0]},{taille[1]}")
    o.add_argument("--hide-scrollbars")
    o.add_argument("--force-device-scale-factor=1")
    o.add_argument("--lang=fr-FR")
    o.binary_location = CHROME
    for essai in range(3):
        try:
            return webdriver.Chrome(options=o)
        except Exception:
            time.sleep(3)
    raise RuntimeError("Chrome ne démarre pas")


class Session:
    def __init__(self, url, taille=(1500, 1400)):
        self.d = demarrer(taille)
        self.d.get(url)
        time.sleep(4)
        # attendre que la page soit entièrement dessinée (message d'accueil + bouton) et que le serveur ne soit plus « en cours d'exécution »
        self.attendre("return document.querySelector('[data-testid=\"stMain\"]') && document.querySelector('[data-testid=\"stMain\"]').innerText.includes('Charge tes fichiers') "
                      "&& !document.querySelector('[data-testid=\"stStatusWidget\"]')", 120)
        time.sleep(2)

    def js(self, code, *args):
        return self.d.execute_script(code, *args)

    def attendre(self, cond_js, delai=90, pas=1.0):
        fin = time.time() + delai
        while time.time() < fin:
            if self.js("return !!(function(){" + cond_js + "})()"):
                return True
            time.sleep(pas)
        return False

    def lancer(self):
        self.attendre("return [...document.querySelectorAll('button')].find(x => x.innerText.includes('Lancer la corro'))", 90)
        self.js("[...document.querySelectorAll('button')].find(x => x.innerText.includes('Lancer la corro')).click()")
        if not self.attendre(JS_HOTE.replace("return ", "return ") , 120):
            self.attendre("return document.querySelector('[data-testid=\"stMain\"]').innerText.includes('Tableau de bord')", 120)
        time.sleep(3)

    def pause(self, s=3.5):
        time.sleep(s)

    def pastille(self, nom):
        """Clique une pastille de la section « Données sélectionnées »."""
        self.js("""
          const g = [...document.querySelectorAll('[data-testid="stButtonGroup"]')].find(g => g.innerText.includes('Par champ'));
          [...g.querySelectorAll('button')].find(b => b.innerText.trim() == arguments[0]).click();""", nom)
        self.pause()

    def hote(self):
        return self.js(JS_HOTE)

    def boite(self, titre):
        return self.js(JS_BOITE, titre)

    def faire_defiler(self, el):
        self.js("arguments[0].scrollIntoView({block: 'center'})", el)
        time.sleep(0.8)

    def surligner(self, el, couleur="#e63946"):
        self.js(f"arguments[0].style.outline = '3px solid {couleur}'; arguments[0].style.outlineOffset = '2px'", el)

    def retirer_surlignage(self, el):
        self.js("arguments[0].style.outline = ''", el)

    def photo(self, nom, el=None):
        chemin = IMG / f"{nom}.png"
        if el is None:
            self.d.save_screenshot(str(chemin))
        else:
            self.faire_defiler(el)
            el.screenshot(str(chemin))
        print("  ->", chemin.name)

    def fin(self):
        self.d.quit()


def titre_section(s, texte):
    return s.js("""
      return [...document.querySelectorAll('[data-testid="stMain"] *')].find(e => e.children.length == 0 && e.textContent.trim() == arguments[0]) || null;""", texte)


def section(s, titre):
    """Titre de section + son encadré (le titre est juste au-dessus de l'encadré)."""
    return s.js("""
      const t = [...document.querySelectorAll('[data-testid="stMain"] *')].find(e => e.children.length == 0 && e.textContent.trim() == arguments[0]);
      if (!t) return null;
      const bloc = t.closest('[data-testid="stElementContainer"]');
      return bloc ? bloc.nextElementSibling : null;""", titre)


def principal():
    # ------------------------------------------------------------------ 1. accueil et chargement
    s = Session(URL)
    s.photo("01_accueil")
    side = s.d.find_element(By.CSS_SELECTOR, '[data-testid="stSidebar"]')
    s.photo("02_barre_laterale_avant", side)
    bouton = s.js("return [...document.querySelectorAll('button')].find(x => x.innerText.includes('Lancer la corro'))")
    s.surligner(bouton)
    s.photo("03_bouton_lancer", side)
    s.retirer_surlignage(bouton)
    s.lancer()
    s.pause(4)

    # ------------------------------------------------------------------ 2. tableau de bord
    s.d.set_window_size(1500, 1500)
    s.js("window.scrollTo(0,0); document.querySelector('[data-testid=\"stMain\"]').scrollTo(0,0)")
    s.pause(1)
    s.photo("04_vue_generale")
    boite1 = section(s, "Tableau de bord")
    s.photo("05_tableau_de_bord", boite1)
    # anneau, curseur, barre de revue
    curseur = s.js("return document.querySelector('[data-testid=\"stSlider\"]')")
    s.surligner(curseur)
    s.photo("06_curseur_seuil", boite1)
    s.retirer_surlignage(curseur)
    barre = s.js("return [...document.querySelectorAll('[data-testid=\"stMain\"] *')].find(e => e.children.length == 0 && e.textContent.includes('Revue humaine')).parentElement.parentElement")
    s.surligner(barre)
    s.photo("07_barre_revue_humaine", boite1)
    s.retirer_surlignage(barre)
    graphes = s.js("""
      const n = [...document.querySelectorAll('[data-testid="stMain"] *')].find(e => e.children.length == 0 && e.textContent.trim() == 'Confiance du modèle');
      let e = n; while (e) { const cs = getComputedStyle(e); if (parseFloat(cs.borderTopWidth) > 0 && e.getBoundingClientRect().width > 500) return e; e = e.parentElement; } return null;""")
    s.photo("08_histogramme_et_camemberts", graphes)

    # ------------------------------------------------------------------ 3. données sélectionnées
    sec = section(s, "Données sélectionnées")
    s.photo("09_donnees_selectionnees_defaut", sec)
    groupe = s.js("return [...document.querySelectorAll('[data-testid=\"stButtonGroup\"]')].find(g => g.innerText.includes('Par champ'))")
    s.surligner(groupe)
    s.photo("10_pastilles", sec)
    s.retirer_surlignage(groupe)
    s.pastille("Vraie anomalie")
    s.pastille("À relire")                                    # décoche « À relire » (la sélection de départ)
    sec = section(s, "Données sélectionnées")
    s.photo("11_vraies_anomalies", sec)
    hote = s.hote()
    s.photo("12_tableau_detail", hote)
    # colonnes du tableau : surlignages ciblés
    cloche = s.js("const r = arguments[0].shadowRoot; return r.querySelector('button.bell')", hote)
    s.surligner(cloche)
    s.photo("13_cloche", hote)
    s.retirer_surlignage(cloche)
    cases = s.js("const r = arguments[0].shadowRoot; return r.querySelector('td.ver input')", hote)
    s.surligner(cases)
    s.photo("14_cases_ok", hote)
    s.retirer_surlignage(cases)
    statut = s.js("const r = arguments[0].shadowRoot; return r.querySelector('td.statut')", hote)
    s.surligner(statut)
    s.photo("15_statut_modifiable", hote)
    s.retirer_surlignage(statut)

    # confirmation d'un changement de statut (annulée : rien n'est écrit)
    s.js("""
      const sel = arguments[0].shadowRoot.querySelector('td.statut select');
      sel.value = sel.value === 'ERREUR' ? 'ECART_JUSTIFIE' : 'ERREUR';
      sel.dispatchEvent(new Event('change', {bubbles: true}));""", hote)
    s.attendre("return document.querySelector('[role=\"dialog\"]')", 30)
    s.pause(1.5)
    s.photo("16_confirmation_statut")
    s.js("[...document.querySelectorAll('[role=\"dialog\"] button')].find(b => b.innerText.includes('Annuler')).click()")
    s.pause(3)

    # ------------------------------------------------------------------ 4. filtres
    s.js("""
      const sel = [...document.querySelectorAll('[data-testid="stSelectbox"]')].find(x => x.innerText.includes('Employé'));
      sel.scrollIntoView({block: 'center'});""")
    emp = s.js("""
      const sb = [...document.querySelectorAll('[data-testid="stSelectbox"]')].find(x => x.innerText.includes('Employé'));
      return sb;""")
    s.d.execute_script("arguments[0].querySelector('input').focus()", emp)
    entree = emp.find_element(By.CSS_SELECTOR, "input")
    entree.send_keys("3712987")
    time.sleep(1)
    entree.send_keys("\n")
    s.pause(4)
    sec = section(s, "Données sélectionnées")
    s.photo("17_filtre_employe", sec)
    s.js("[...document.querySelectorAll('button')].find(b => b.innerText.includes('Réinitialiser les filtres')).click()")
    s.pause(4)

    # clic sur un camembert (cause probable) -> filtre
    graphes = s.js("""
      const n = [...document.querySelectorAll('[data-testid="stMain"] *')].find(e => e.children.length == 0 && e.textContent.trim() == 'Confiance du modèle');
      let e = n; while (e) { const cs = getComputedStyle(e); if (parseFloat(cs.borderTopWidth) > 0 && e.getBoundingClientRect().width > 500) return e; e = e.parentElement; } return null;""")
    s.faire_defiler(graphes)
    vegas = s.d.find_elements(By.CSS_SELECTOR, '[data-testid="stVegaLiteChart"]')
    cause = vegas[2]
    w, h = cause.size["width"], cause.size["height"]
    ActionChains(s.d).move_to_element_with_offset(cause, int(-w / 2 + 62 + 12 + 20), -15).click().perform()
    s.pause(4)
    sec = section(s, "Données sélectionnées")
    s.photo("18_clic_camembert", graphes)
    s.photo("19_filtre_cause", sec)
    s.js("[...document.querySelectorAll('button')].find(b => b.innerText.includes('Réinitialiser les filtres')).click()")
    s.pause(4)

    # ------------------------------------------------------------------ 5. autres vues
    s.pastille("Tout")
    sec = section(s, "Données sélectionnées")
    s.photo("20_vue_tout_export", sec)
    s.pastille("Tout")
    for pastille, nom in (("Conforme", "21_lignes_conformes"), ("Écart justifié", "22_ecarts_justifies")):
        s.pastille(pastille)
        sec = section(s, "Données sélectionnées")
        s.photo(nom, sec)
        s.pastille(pastille)
    s.pastille("Par champ")
    s.photo("23_par_champ", section(s, "Données sélectionnées"))
    s.pastille("Par champ")
    s.pastille("Glossaire")
    s.photo("24_glossaire", section(s, "Données sélectionnées"))
    s.pastille("Glossaire")
    s.pastille("Paramètres")
    s.photo("25_parametres", section(s, "Données sélectionnées"))
    s.pastille("Paramètres")
    s.pastille("Corrections")
    s.photo("26_corrections_vide", section(s, "Données sélectionnées"))
    s.pastille("Corrections")

    # ------------------------------------------------------------------ 6. bandeau IA (cloche) : explication du LLM local
    s.pastille("Vraie anomalie")
    s.pastille("À relire")
    hote = s.hote()
    s.js("arguments[0].shadowRoot.querySelector('button.bell').click()", hote)
    print("  attente de l'explication du LLM local (jusqu'à 5 min)…")
    s.attendre("return document.querySelector('.st-key-bandeau_ia')", 300, 2)
    s.pause(3)
    s.d.set_window_size(1500, 1000)
    time.sleep(1)
    s.photo("27_bandeau_explication")
    # bulle de l'assistant (fermée) : on ferme tout
    s.js("[...document.querySelectorAll('.st-key-bandeau_ia button')].find(b => b.innerText.includes('Fermer')).click()")
    s.pause(3)
    s.photo("28_bulle_assistant")

    # ------------------------------------------------------------------ 7. assistant
    s.js("document.querySelector('.st-key-chat_bulle button').click()")
    s.pause(4)
    s.photo("29_assistant_ouvert")
    s.js("[...document.querySelectorAll('.st-key-chat_zone button')].find(b => b.innerText.includes('Combien de vraies anomalies')).click()")
    s.pause(4)
    s.photo("30_assistant_reponse")
    s.js("""
      const area = document.querySelector('.st-key-bandeau_ia textarea');
      const set = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set;
      set.call(area, "Montre-moi les anomalies de l'employé 3712987"); area.dispatchEvent(new Event('input', {bubbles: true}));""")
    time.sleep(0.8)
    s.js("document.querySelector('.st-key-bandeau_ia textarea').dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true}))")
    s.pause(5)
    s.photo("31_assistant_pilotage")
    s.js("""
      const area = document.querySelector('.st-key-bandeau_ia textarea');
      const set = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set;
      set.call(area, "Explique la ligne de l'employé 3712987 sur contractTypeCode"); area.dispatchEvent(new Event('input', {bubbles: true}));""")
    time.sleep(0.8)
    s.js("document.querySelector('.st-key-bandeau_ia textarea').dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true}))")
    s.attendre("return document.querySelector('.st-key-bandeau_texte')", 300, 2)
    s.pause(4)
    s.photo("32_assistant_et_explication")
    s.js("[...document.querySelectorAll('.st-key-bandeau_ia button')].find(b => b.innerText.includes('Fermer')).click()")
    s.pause(3)

    # ------------------------------------------------------------------ 8. langue et barre latérale (modèles, GPU)
    s.d.set_window_size(1500, 1400)
    s.js("window.scrollTo(0,0); document.querySelector('[data-testid=\"stMain\"]').scrollTo(0,0)")
    side = s.d.find_element(By.CSS_SELECTOR, '[data-testid="stSidebar"]')
    s.photo("33_barre_laterale_llm", side)
    s.js("document.querySelector('.st-key-lang_en label').click()")
    s.pause(6)
    s.photo("34_interface_anglaise")
    s.js("document.querySelector('.st-key-lang_en label').click()")
    s.pause(4)
    s.fin()

    # ------------------------------------------------------------------ 9. fichier invalide : message d'erreur clair
    s = Session(URL, (1500, 1000))
    faux = Path(tempfile.mkdtemp()) / "mauvaise_extraction.xlsx"
    pd.DataFrame({"colonne_inattendue": [1, 2, 3]}).to_excel(faux, index=False)
    entree = s.d.find_elements(By.CSS_SELECTOR, '[data-testid="stFileUploaderDropzoneInput"]')[0]
    entree.send_keys(str(faux))
    time.sleep(4)
    s.js("[...document.querySelectorAll('button')].find(x => x.innerText.includes('Lancer la corro')).click()")
    time.sleep(10)
    s.photo("35_fichier_invalide")
    s.fin()

    print("terminé :", len(list(IMG.glob("*.png"))), "captures dans", IMG)



def demo():
    """Corrections d'experts et règles apprises (serveur de démonstration : dossier temporaire, vrais fichiers intacts)."""
    s = Session(URL_DEMO, (1500, 1400))
    s.lancer()
    s.pause(4)
    s.pastille("Corrections")
    sec = section(s, "Données sélectionnées")
    s.photo("36_regle_proposee", sec)
    s.js("[...document.querySelectorAll('button')].find(b => b.innerText.includes('Valider la règle')).click()")
    s.pause(14)
    s.pastille("Corrections")
    s.pastille("Corrections")
    s.photo("37_regle_validee", section(s, "Données sélectionnées"))
    s.js("[...document.querySelectorAll('button')].find(b => b.innerText.includes('Mesurer l')).click()")
    s.pause(18)
    s.photo("38_effet_des_retours", section(s, "Données sélectionnées"))
    s.fin()
    print("démonstration terminée")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        demo()
    else:
        principal()
        demo()
