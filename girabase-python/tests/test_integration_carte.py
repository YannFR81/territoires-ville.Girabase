"""Girabase 1.2 : localisation sur la carte IGN intégrée à la fenêtre de calcul (sans réseau)."""
import json
import os
import shutil
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")
from PySide6.QtCore import QSettings                     # noqa: E402

from girabase.carto.site import SiteCarto, site_depuis_texte   # noqa: E402

RACINE = Path(__file__).resolve().parent.parent
DONNEES = RACINE / "tests" / "donnees" / "bdtopo_lombers_d71_d41.json"
CLIC = (43.816139, 2.169778)


class FauxClient:
    def obtenir_json(self, url, rappel, essai=1):
        if "troncon_de_route" in url:
            rappel(json.loads(DONNEES.read_text(encoding="utf-8")), "")
        elif "commune" in url:
            rappel({"features": [{"properties": {"nom_officiel": "Lombers", "code_insee": "81147"}}]}, "")
        else:
            rappel(None, "hors ligne")


@pytest.fixture
def principale(tmp_path, monkeypatch):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(tmp_path / "reglages"))
    monkeypatch.setattr(QtWidgets.QInputDialog, "getItem",
                        staticmethod(lambda *a, **k: ("Rase campagne", True)))
    from girabase.gui.fenetre import FenetrePrincipale
    w = FenetrePrincipale()
    w.show()
    app.processEvents()
    yield w
    w.modifie_flag = False
    if w.fen_carte is not None:
        w.fen_carte.modifie = False
        w.fen_carte.close()
    w.close()


def _carte(w):
    w.localiser_sur_carte()
    fen = w.fen_carte
    fen.client = FauxClient()
    fen.carte.centrer(*CLIC, 18)
    return fen


def test_bouton_de_l_onglet_site(principale):
    principale.site.bt_carte.click()
    assert principale.fen_carte is not None and principale.fen_carte.isVisible() and principale.fen_carte.liee
    assert principale.fen_carte.bt_envoyer.text().endswith("Envoyer dans Girabase")


def test_nouveau_projet_depuis_la_carte(principale, tmp_path):
    fen = _carte(principale)
    fen.analyser_carrefour(*CLIC)
    fen.bt_envoyer.click()
    g = principale.g
    assert [b.nom for b in g.branches] == ["D71 Nord", "D41 Ouest", "D71 Sud", "D41 Est"]
    assert [b.angle for b in g.branches] == [0, 81, 186, 270]
    assert (g.R, g.Bf, g.LA) == (5.0, 2.0, 7.0) and g.milieu.libelle == "Rase campagne"
    assert "Lombers (81147)" in g.localisation and "BD TOPO®" in g.localisation
    assert principale.onglets.currentWidget() is principale.trafics      # étape suivante : les trafics
    assert principale.modifie_flag and not fen.modifie
    # Enregistrement : le site cartographique est écrit à côté du projet, et relu à l'ouverture
    principale.chemin = tmp_path / "lombers.gbs"
    assert principale.enregistrer()
    assert (tmp_path / "lombers.gsite").exists()
    principale.ouvrir(str(tmp_path / "lombers.gbs"))
    assert principale.site_carto is not None and len(principale.site_carto.branches) == 4


def test_mise_a_jour_du_projet_ouvert_trafics_conserves(principale, tmp_path, monkeypatch):
    src = tmp_path / "rc.gbs"
    shutil.copy(RACINE / "exemples" / "exemple_rase_campagne.gbs", src)
    principale.ouvrir(str(src))
    avant = [row[:] for row in principale.g.periodes[0].matrice_uvp()]
    largeurs = [b.le4 for b in principale.g.branches]
    assert principale.g.n == 4
    monkeypatch.setattr(principale, "_demander_mode", lambda n: "maj")
    fen = _carte(principale)
    fen.analyser_carrefour(*CLIC)
    fen.envoyer_dans_girabase()
    g = principale.g
    assert [b.angle for b in g.branches] == [0, 81, 186, 270] and g.branches[0].nom == "D71 Nord"
    assert g.periodes[0].matrice_uvp() == avant                       # trafics conservés
    assert [b.le4 for b in g.branches] == largeurs                     # largeurs de Girabase conservées
    assert principale.chemin == src and principale.modifie_flag


def test_projet_sans_site_reouvert_sur_ses_coordonnees(principale):
    principale.g.localisation = "Lombers (81147)\n43°48'58.1\"N 2°10'11.2\"E — WGS84 43.816126, 2.169786"
    principale.localiser_sur_carte()
    s = principale.fen_carte.site
    assert s.centre_defini and abs(s.lat - 43.816126) < 1e-9
    assert site_depuis_texte("pas de coordonnées") is None


def test_aide_guide_et_sources(principale, monkeypatch):
    from girabase.gui import guide
    texte = guide.texte_guide()
    assert texte.startswith("# Guide d'utilisation de Girabase")
    images = [l.split("](")[1].rstrip(")") for l in texte.splitlines() if l.startswith("![")]
    assert len(images) >= 10 and all((guide.dossier_guide() / i).exists() for i in images)
    tb = QtWidgets.QTextBrowser()
    tb.setMarkdown(texte)
    assert guide.reduire_images(tb) == len(images)                 # captures ramenées à la fenêtre d'aide
    vus = []
    monkeypatch.setattr(QtWidgets.QDialog, "exec", lambda self: vus.append(self.windowTitle()))
    principale.guide()
    principale.sources_et_licences()
    assert vus == ["Girabase — Guide d'utilisation", "Sources des données et licences"]


def test_questions_devant_la_carte(principale, monkeypatch):
    parents = []
    monkeypatch.setattr(QtWidgets.QInputDialog, "getItem",
                        staticmethod(lambda parent, *a, **k: (parents.append(parent), ("Périurbain", True))[1]))
    fen = _carte(principale)
    fen.analyser_carrefour(*CLIC)
    fen.envoyer_dans_girabase()
    assert parents == [fen]                                  # pas derrière la carte
    assert principale.g.milieu.libelle == "Périurbain" and principale._parent_questions is principale


def test_carte_suit_le_projet_ouvert(principale, tmp_path):
    fen = _carte(principale)
    fen.analyser_carrefour(*CLIC)
    fen.envoyer_dans_girabase()
    assert principale.fen_carte.site.centre_defini
    # Nouveau projet sans localisation : la carte ne montre plus l'ancien giratoire
    principale.modifie_flag = False
    principale.nouveau()
    principale.localiser_sur_carte()
    assert not fen.site.centre_defini and not fen.site.branches
    # Projet dont la localisation contient des coordonnées : la carte s'y place
    principale.g.localisation = "43°48'58.1\"N 2°10'11.2\"E — WGS84 43.816126, 2.169786"
    principale.ouvrir(str(RACINE / "exemples" / "exemple_rase_campagne.gbs"))
    principale.g.localisation = "WGS84 44.000000, 2.000000"
    principale.localiser_sur_carte()
    assert fen.site.centre_defini and abs(fen.site.lat - 44.0) < 1e-9
    # Deuxième appel sur le même projet : le travail en cours sur la carte est conservé
    fen.site.R = 12.5
    principale.localiser_sur_carte()
    assert fen.site.R == 12.5


def test_carte_ne_perd_pas_un_dessin_non_envoye_sans_accord(principale, monkeypatch):
    fen = _carte(principale)
    fen.analyser_carrefour(*CLIC)
    assert fen.modifie
    monkeypatch.setattr(QtWidgets.QMessageBox, "question", staticmethod(lambda *a, **k: QtWidgets.QMessageBox.No))
    principale.modifie_flag = False
    principale.nouveau()
    principale.localiser_sur_carte()
    assert fen.site.centre_defini and len(fen.site.branches) == 4        # dessin conservé


def test_mention_des_sources_par_defaut():
    site = SiteCarto(lat=43.816126, lon=2.169786, fond="ortho")
    assert "IGN" in site.texte_localisation() and "Etalab 2.0" in site.texte_localisation()
    assert "OpenStreetMap" in SiteCarto(lat=43.8, lon=2.1, fond="osm").mention()
    assert SiteCarto(sources="Sources : X").mention() == "Sources : X"
    assert "IGN" not in SiteCarto().texte_localisation()               # rien de localisé : pas de mention
