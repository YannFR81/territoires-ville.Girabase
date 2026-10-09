"""Fenêtre de localisation : parcours complet à la souris et au clavier, sans réseau.

Les services de l'IGN sont remplacés par l'extrait BD TOPO du giratoire D71 / D41 à Lombers.
"""
import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")
from PySide6 import QtGui                                 # noqa: E402
from PySide6.QtCore import QPoint, QSettings, Qt          # noqa: E402
from PySide6.QtTest import QTest                         # noqa: E402

from girabase import gbs                                 # noqa: E402
from girabase.carto.projections import format_dms, point_azimut, vers_local   # noqa: E402

DONNEES = Path(__file__).resolve().parent / "donnees" / "bdtopo_lombers_d71_d41.json"
CLIC = (43.816139, 2.169778)


@pytest.fixture(scope="module")
def app():
    a = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    a.setOrganizationName("Girabase-Py-tests")
    a.setApplicationName("Girabase-tests")
    QSettings().clear()
    return a


class FauxClient:
    """Remplace ClientIGN : réponses locales et immédiates."""

    def __init__(self, fichier=DONNEES):
        self.urls = []
        self.fichier = fichier

    def obtenir_json(self, url, rappel, essai=1):
        self.urls.append(url)
        if "troncon_de_route" in url:
            rappel(json.loads(self.fichier.read_text(encoding="utf-8")), "")
        elif "commune" in url:
            rappel({"features": [{"properties": {"nom_officiel": "Lombers", "code_insee": "81147",
                                                 "code_insee_du_departement": "81"}}]}, "")
        else:
            rappel(None, "hors ligne")


@pytest.fixture
def fen(app):
    from girabase.carto.gui.fenetre import FenetreLocalisation
    QSettings().clear()
    f = FenetreLocalisation()
    f.client = FauxClient()
    f.resize(1500, 900)
    f.show()
    f.carte.centrer(*CLIC, 19)
    app.processEvents()
    yield f
    f.modifie = False
    f.close()


def _ecran(fen, lat, lon) -> QPoint:
    from girabase.carto.gui.carte import geo_vers_scene
    return fen.carte.mapFromScene(geo_vers_scene(lat, lon))


def _cliquer(fen, lat, lon):
    QTest.mouseClick(fen.carte.viewport(), Qt.LeftButton, Qt.NoModifier, _ecran(fen, lat, lon))


def test_centre_et_axes_a_la_souris(fen):
    fen.choisir_mode("centre")
    _cliquer(fen, *CLIC)
    s = fen.site
    e, n = vers_local(*CLIC, s.lat, s.lon)
    assert abs(e) < 0.3 and abs(n) < 0.3                          # précision du clic au niveau 19
    assert fen.carte.mode == "axe"                                # enchaîne sur le tracé des axes
    assert fen.lbl_commune.text() == "Lombers (81147)"
    assert len(fen.troncons) == 9
    for az in (342, 72, 155, 261):
        _cliquer(fen, *point_azimut(s.lat, s.lon, az, 40))
    noms = [b.nom for b, _ in s.ordre_girabase()]
    assert noms == ["D71 Nord", "D41 Ouest", "D71 Sud", "D41 Est"]
    assert [round(a) for _, a in s.ordre_girabase()] == [0, 81, 187, 270]
    assert fen.table.rowCount() == 4 and fen.table.item(0, 1).text() == "D71 Nord"
    assert fen.table.item(1, 3).text() == "Route de Graulhet"


def test_glisser_une_poignee(fen):
    fen.placer_centre(*CLIC)
    fen.site.ajouter_branche(90)
    fen._tout_rafraichir()
    b = fen.site.branches[0]
    assert b.nom == "Branche 1 Est"
    poignee = point_azimut(*CLIC, 90, fen.site.Rg + 35)
    vp = fen.carte.viewport()
    QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier, _ecran(fen, *poignee))
    QTest.mouseMove(vp, _ecran(fen, *point_azimut(*CLIC, 150, 40)))
    QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier, _ecran(fen, *point_azimut(*CLIC, 180, 40)))
    assert b.azimut == pytest.approx(180, abs=0.5)
    assert b.nom == "Branche 1 Sud"                              # orientation mise à jour


def test_glisser_le_centre(fen):
    fen.placer_centre(*CLIC)
    vp = fen.carte.viewport()
    QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier, _ecran(fen, *CLIC))
    cible = point_azimut(*CLIC, 45, 10)
    QTest.mouseMove(vp, _ecran(fen, *cible))
    QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier, _ecran(fen, *cible))
    e, n = vers_local(*cible, fen.site.lat, fen.site.lon)
    assert abs(e) < 0.3 and abs(n) < 0.3


def test_detection_et_anneau_au_clavier(fen):
    fen.detecter_giratoire()
    s = fen.site
    assert format_dms(s.lat, s.lon) == "43°48'58.1\"N 2°10'11.2\"E"
    assert [b.nom for b, _ in s.ordre_girabase()] == ["D71 Nord", "D41 Ouest", "D71 Sud", "D41 Est"]
    fen.sp["R"].setValue(4.5)
    fen.sp["LA"].setValue(7.5)
    assert (s.R, s.LA) == (4.5, 7.5) and fen.lbl_rg.text() == "14,00 m"
    fen.caler_anneau()                                            # 10,73 + 3,75 − 7,5 − 2 = 4,98 → 5
    assert s.R == 5.0
    assert fen.cb_cc.currentText() == "CC44" and fen.lbl_l93.text().startswith("X = 633 19")


def test_edition_du_tableau(fen):
    fen.detecter_giratoire()
    it = fen.table.item(2, 4)                                     # azimut de la branche 3 (D71 Sud)
    it.setText("170")
    QtWidgets.QApplication.processEvents()
    b = next(b for b in fen.site.branches if b.numero == "D71" and b.nom.endswith("Sud"))
    assert b.azimut == 170
    fen.table.item(0, 7).setText("4,25")
    QtWidgets.QApplication.processEvents()
    assert fen.site.ordre_girabase()[0][0].le4 == 4.25
    fen.selection = fen.table.item(3, 0).data(Qt.UserRole)
    fen.definir_branche1()
    assert fen.site.ordre_girabase()[0][0].nom == "D41 Est"


def test_recherche_de_coordonnees(fen, monkeypatch):
    monkeypatch.setattr(QtWidgets.QMessageBox, "question", staticmethod(lambda *a, **k: QtWidgets.QMessageBox.Yes))
    fen.saisie.setText("633197.48 6302254.01")                   # Lambert-93
    fen.rechercher()
    assert format_dms(fen.site.lat, fen.site.lon) == "43°48'58.1\"N 2°10'11.2\"E"
    fen.saisie.setText("1633212.25 3179908.97")                  # CC44
    fen.rechercher()
    assert format_dms(fen.site.lat, fen.site.lon) == "43°48'58.1\"N 2°10'11.2\"E"
    assert len(fen.site.branches) == 4                            # analyse du carrefour aux coordonnées


def test_exports(fen, tmp_path, monkeypatch):
    fen.detecter_giratoire()
    kml = tmp_path / "giratoire.kml"
    projet = tmp_path / "giratoire.gbs"
    site = tmp_path / "giratoire.gsite"
    monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: (str({".kml": kml, ".gbs": projet,
                                                           ".gsite": site}[Path(a[2]).suffix]), "")))
    monkeypatch.setattr(QtWidgets.QInputDialog, "getItem", staticmethod(lambda *a, **k: ("Rase campagne", True)))
    monkeypatch.setattr(QtWidgets.QMessageBox, "information", staticmethod(lambda *a, **k: None))
    fen.exporter_kml()
    assert "<name>1. D71 Nord</name>" in kml.read_text(encoding="utf-8")
    fen.creer_gbs()
    g = gbs.lire(projet)
    assert [b.angle for b in g.branches] == [0, 81, 186, 270] and g.milieu.libelle == "Rase campagne"
    assert "Lombers (81147)" in g.localisation
    fen.enregistrer_sous()
    assert site.exists() and not fen.modifie
    fen.nouveau()
    assert not fen.site.centre_defini
    fen.ouvrir(str(site))
    assert [b.nom for b, _ in fen.site.ordre_girabase()] == ["D71 Nord", "D41 Ouest", "D71 Sud", "D41 Est"]
    assert fen.lbl_commune.text() == "Lombers (81147)"


def test_ouverture_cadree_sur_le_giratoire(app, tmp_path):
    """Un site ouvert au lancement est cadré une fois la fenêtre affichée (anneau et étiquettes visibles)."""
    from girabase.carto.gui.fenetre import FenetreLocalisation
    from girabase.carto.site import SiteCarto
    s = SiteCarto(lat=CLIC[0], lon=CLIC[1], R=4)
    for az in (342, 72, 155, 261):
        s.ajouter_branche(az)
    chemin = tmp_path / "site.gsite"
    s.enregistrer(chemin)
    f = FenetreLocalisation(str(chemin))
    f.client = FauxClient()
    f.resize(1500, 900)
    f.show()
    for _ in range(5):
        app.processEvents()
    vp = f.carte.viewport().rect()
    for az in (342, 72, 155, 261):
        assert vp.contains(_ecran(f, *point_azimut(*CLIC, az, s.Rg + 52)))     # étiquettes dans la vue
    assert f.carte.niveau >= 18.5
    f.modifie = False
    f.close()


# --- Parcours « France entière → zoom → pointer le carrefour » ------------------------------------------
def test_demarrage_sur_la_france(app):
    from girabase.carto.gui.fenetre import FenetreLocalisation
    QSettings().clear()
    f = FenetreLocalisation()
    f.client = FauxClient()
    f.resize(1500, 900)
    f.show()
    for _ in range(5):
        app.processEvents()
    lat, lon = f.carte.centre_geo()
    assert f.carte.niveau <= 7 and 45 < lat < 48 and 1 < lon < 4
    assert f.carte.fond.code == "plan" and not f.carte.voile.isVisible()
    assert f.carte.consigne.startswith("Choisissez l'emplacement")
    f.close()


def test_photo_et_routes_ign_au_zoom_fort(fen):
    c = fen.carte
    c.centrer(*CLIC, 12)
    assert c.fond.code == "plan" and not c.routes_visibles
    c.centrer(*CLIC, 17)
    assert c.fond.code == "ortho" and c.routes_visibles and c.voile.isVisible()
    assert c.voile.brush().color().alpha() == 128                 # photo à 50 %
    fen.sl_opacite.setValue(80)
    assert c.voile.brush().color().alpha() == 51
    fen.ck_routes_ign.setChecked(False)
    assert not c.routes_visibles
    assert "Pointez le carrefour" in c.consigne
    fen.cb_fond.setCurrentIndex(fen.cb_fond.findData("auto_osm"))
    c.centrer(*CLIC, 12)
    assert c.fond.code == "osm"


def test_pointer_un_giratoire_existant(fen):
    fen.choisir_mode("carrefour")
    _cliquer(fen, *point_azimut(*CLIC, 60, 6))                   # clic à 6 m du centre
    s = fen.site
    assert format_dms(s.lat, s.lon) == "43°48'58.1\"N 2°10'11.2\"E"
    assert (s.R, s.Bf, s.LA) == (5.0, 2.0, 7.0)                   # anneau estimé : Rg ≈ 14 m
    assert [b.nom for b, _ in s.ordre_girabase()] == ["D71 Nord", "D41 Ouest", "D71 Sud", "D41 Est"]
    assert fen.carte.mode == "deplacer" and fen.carte.consigne == ""
    assert fen.lbl_commune.text() == "Lombers (81147)" and fen.lbl_l93_titre.text() == "RGF93 Lambert-93"


def test_pointer_de_trop_loin_rapproche_la_carte(fen):
    fen.carte.centrer(*CLIC, 10)
    fen.analyser_carrefour(*CLIC)
    assert not fen.site.centre_defini and fen.carte.niveau >= 17


def test_pointer_un_carrefour_plan(fen):
    fen.client.fichier = DONNEES.parent / "bdtopo_realmont_d612_d86.json"
    fen.carte.centrer(43.77535, 2.18812, 18)
    fen.choisir_mode("carrefour")
    _cliquer(fen, 43.77535, 2.18812)
    s = fen.site
    assert format_dms(s.lat, s.lon) == "43°46'30.9\"N 2°11'16.9\"E"
    assert len(s.branches) == 4 and s.rayon_axe_bdtopo is None and s.R == 6.0
    assert {b.numero for b in s.branches} == {"", "D86", "D612"}


def test_pointer_hors_carrefour(fen):
    fen.client.fichier = DONNEES.parent / "bdtopo_realmont_d612_d141.json"
    fen.carte.centrer(43.7650, 2.1800, 18)
    fen.analyser_carrefour(43.7650, 2.1800)
    assert fen.site.centre_defini and not fen.site.branches and fen.carte.mode == "axe"


def test_menu_clic_droit(fen):
    def executer(menu, pos):
        next(a for a in menu.actions() if a.text().startswith("◎")).trigger()
    fen._executer_menu = executer
    QTest.mouseClick(fen.carte.viewport(), Qt.RightButton, Qt.NoModifier, _ecran(fen, *CLIC))
    assert [b.nom for b, _ in fen.site.ordre_girabase()][0] == "D71 Nord"


# --- Panneau latéral : outils en tête, encarts repliables, effacer -------------------------------------
def test_outils_dans_le_panneau(fen):
    boutons = {b.property("mode"): b for b in fen.modes.buttons()}
    assert set(boutons) == {"deplacer", "carrefour", "centre", "axe"}
    for b in boutons.values():                                    # plus dans la barre d'outils du haut
        parent = b.parent()
        while parent is not None and not isinstance(parent, QtWidgets.QToolBar):
            parent = parent.parent()
        assert parent is None
    boutons["axe"].click()
    assert fen.carte.mode == "axe" and boutons["axe"].isChecked() and not boutons["deplacer"].isChecked()
    assert isinstance(fen.ck_routes_ign, QtGui.QAction) and fen.ck_routes_ign.isChecked()   # menu « Couches »


def test_encarts_repliables(fen, app):
    e = fen.encarts
    assert list(e) == ["localisation", "anneau", "branches", "exports"]
    assert not e["localisation"].ouvert and e["anneau"].ouvert       # Localisation repliée par défaut
    fen.detecter_giratoire()
    assert e["localisation"].resume.isVisibleTo(fen)
    lignes = e["localisation"].resume.texte_complet().split("\n")
    assert lignes == ["Giratoire D71 / D41 — Lombers (81147)",
                      "43°48'58.1\"N 2°10'11.2\"E   L93 X 633 198,14  Y 6 302 252,55"]
    fen.tout_ouvrir(False)
    app.processEvents()
    assert all(not x.ouvert and not x.corps.isVisibleTo(fen) for x in e.values())
    assert e["branches"].resume.texte_complet().startswith("4 branches · n° 1 : D71 Nord\n1. D71 Nord 0°")
    assert e["anneau"].resume.texte_complet().startswith("R 5,00 m · Bf 2,00 m · LA 7,00 m   →   Rg 14,00 m")
    hauteur_repliee = fen.findChild(QtWidgets.QWidget, "panneau").sizeHint().height()
    fen.tout_ouvrir(True)
    app.processEvents()
    hauteur_depliee = fen.findChild(QtWidgets.QWidget, "panneau").sizeHint().height()
    assert hauteur_repliee < 500 < 800 < hauteur_depliee          # tout tient à l'écran une fois replié
    e["exports"].entete.click()                                   # clic sur le titre : replie
    assert not e["exports"].ouvert
    assert QSettings().value("loc/encart/exports") in (False, "false")
    e["exports"].resume.clique.emit()                             # clic sur le résumé : déplie
    assert e["exports"].ouvert


def test_effacer_le_giratoire(fen, monkeypatch):
    monkeypatch.setattr(QtWidgets.QMessageBox, "question", staticmethod(lambda *a, **k: QtWidgets.QMessageBox.Yes))
    fen.detecter_giratoire()
    fen.sp["LA"].setValue(8)
    assert fen.site.centre_defini and len(fen.site.branches) == 4 and fen.bt_effacer.isEnabled()
    fen.bt_effacer.click()
    s = fen.site
    assert not s.centre_defini and not s.branches and s.commune.nom == ""
    assert s.LA == 8 and fen.table.rowCount() == 0                  # anneau saisi conservé
    assert fen.carte.mode == "carrefour" and not fen.bt_effacer.isEnabled()
    assert fen.lbl_dms.text().startswith("— pointez")


def test_glisser_deplace_la_carte_dans_tous_les_modes(fen):
    fen.placer_centre(*CLIC)
    fen.choisir_mode("axe")
    vp = fen.carte.viewport()
    depart = fen.carte.centre_geo()
    a, b = _ecran(fen, *point_azimut(*CLIC, 160, 40)), _ecran(fen, *point_azimut(*CLIC, 250, 40))
    QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier, a)
    QTest.mouseMove(vp, a + QPoint(30, 10))
    QTest.mouseMove(vp, b)
    QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier, b)
    assert fen.site.branches == [] and fen.carte.centre_geo() != depart     # glissé : la carte a bougé
    fen.carte.centrer(*CLIC, 19)
    _cliquer(fen, *point_azimut(*CLIC, 160, 40))                  # simple clic : un axe
    _cliquer(fen, *point_azimut(*CLIC, 161, 45))                  # même axe : pas de doublon
    assert len(fen.site.branches) == 1


# --- Lisibilité en thème clair et en thème sombre de Windows ------------------------------------------
def test_contrastes_des_deux_themes():
    from girabase.carto.gui.theme import COUPLES, TEXTES, THEMES, contraste
    for nom, t in THEMES.items():
        for texte, fond, mini in COUPLES:
            assert contraste(t[texte], t[fond]) >= mini, (nom, texte, fond)
    for nom, t in TEXTES.items():                 # réserves de capacité et contrôles de Girabase
        for cle, couleur in t.items():
            if cle != "fond":
                assert contraste(couleur, t["fond"]) >= 4.5, (nom, cle)


def _palette_sombre():
    p = QtGui.QPalette()
    for role, couleur in ((QtGui.QPalette.Window, "#202020"), (QtGui.QPalette.Base, "#2b2b2b"),
                          (QtGui.QPalette.Button, "#3c3c3c"), (QtGui.QPalette.WindowText, "#ffffff"),
                          (QtGui.QPalette.Text, "#ffffff"), (QtGui.QPalette.ButtonText, "#ffffff")):
        p.setColor(role, QtGui.QColor(couleur))
    return p


def test_theme_sombre_de_windows(app):
    from girabase.carto.gui.fenetre import FenetreLocalisation
    from girabase.carto.gui.theme import THEMES
    clair = app.palette()
    try:
        app.setPalette(_palette_sombre())
        f = FenetreLocalisation()
        f.client = FauxClient()
        assert f._sombre and THEMES["sombre"]["outil_fond"] in f.styleSheet()
        f.show()
        app.processEvents()
        bouton = next(b for b in f.modes.buttons() if not b.isChecked())
        img = bouton.grab().toImage()
        fond = img.pixelColor(img.width() - 6, img.height() // 2)          # fond du bouton, loin du texte
        assert fond.lightness() < 100                                       # bouton sombre sous texte clair
        app.setPalette(clair)                                               # Windows repasse en clair
        app.processEvents()
        assert not f._sombre and THEMES["clair"]["outil_fond"] in f.styleSheet()
        f.close()
    finally:
        app.setPalette(clair)


# --- Licences : mention des sources et identification de l'application ---------------------------------
def test_mention_des_sources_dans_les_exports(fen, tmp_path):
    from girabase.carto.geoservices import AGENT
    from girabase.carto.kml import contenu_kml
    assert AGENT.startswith("Girabase-Python/1.2") and "github.com" in AGENT     # politique OSM / Géoplateforme
    fen.detecter_giratoire()
    s = fen.site
    assert s.sources.startswith("Sources : IGN — BD TOPO®") and "Etalab 2.0" in s.sources
    assert s.sources in s.texte_localisation()                                  # repris dans le projet .gbs
    assert "BD TOPO®" in contenu_kml(s)
    chemin = tmp_path / "s.gsite"
    s.enregistrer(chemin)
    from girabase.carto.site import SiteCarto
    assert SiteCarto.ouvrir(chemin).sources == s.sources


def test_fenetre_des_sources(fen, monkeypatch):
    from girabase.carto.gui import sources
    texte = sources.texte_sources()
    for attendu in ("Licence Ouverte", "openstreetmap.org/copyright", "30 requêtes/s", "BD TOPO®", "HTTP 429"):
        assert attendu in texte
    vus = []
    monkeypatch.setattr(sources, "dialogue_sources", lambda parent: vus.append(parent))
    fen.carte.mentions_cliquees.emit()
    assert vus == [fen]
