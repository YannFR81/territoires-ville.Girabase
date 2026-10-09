"""Parcours de l'interface en mode hors écran (détecte les exceptions dans les gestionnaires Qt)."""
import os
import shutil
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

EXEMPLES = Path(__file__).resolve().parent.parent / "exemples"


@pytest.fixture(scope="module")
def app():
    a = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield a


@pytest.fixture
def fenetre(app, tmp_path, monkeypatch):
    erreurs = []
    monkeypatch.setattr(sys, "excepthook", lambda *e: erreurs.append(e))
    from PySide6.QtCore import QSettings
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(tmp_path))
    from girabase.gui.fenetre import FenetrePrincipale
    src = tmp_path / "rc.gbs"
    shutil.copy(EXEMPLES / "exemple_rase_campagne.gbs", src)
    w = FenetrePrincipale(str(src))
    w.show()
    app.processEvents()
    yield w, erreurs
    w.modifie_flag = False
    w.close()


def _attendre(app, w):
    for _ in range(5):
        app.processEvents()
    w.minuteur.stop()
    w.recalculer()
    app.processEvents()


def test_ouverture_et_calcul(app, fenetre):
    w, err = fenetre
    assert w.erreurs == []
    assert len(w.resultats) == 2 and all(r.complete for r in w.resultats)
    assert w.resultats_tab.table.rowCount() == 4
    assert w.resultats_tab.table.item(2, 4).text() == "34 %"          # HPM
    w.resultats_tab.combo.setCurrentIndex(1)
    app.processEvents()
    assert w.resultats_tab.table.item(2, 4).text() == "13 %"          # HPS
    assert not err


def test_saisie_geometrie_et_trafic(app, fenetre):
    w, err = fenetre
    t = w.geometrie.table
    t.item(0, 5).setText("7")                       # entrée 1 à 2 voies
    _attendre(app, w)
    assert w.g.branches[0].le4 == 7
    rc_avant = w.resultats[0].branches[0].RC
    w.onglets.setCurrentWidget(w.trafics)
    w.trafics.table.item(0, 2).setText("900")
    _attendre(app, w)
    assert w.g.periodes[0].uvp[0][2] == 900
    assert w.resultats[0].branches[0].RC < rc_avant
    assert w.modifie_flag and not err


def test_operations_periodes(app, fenetre, monkeypatch):
    w, err = fenetre
    from PySide6.QtWidgets import QInputDialog, QMessageBox
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("Inversée", True))
    w._action_trafic("inverser")
    _attendre(app, w)
    assert [p.nom for p in w.g.periodes] == ["HPM", "HPS", "Inversée"]
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("Copie", True))
    w._action_trafic("dupliquer")
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    w._action_trafic("supprimer")
    _attendre(app, w)
    assert "Copie" not in [p.nom for p in w.g.periodes]
    assert not err


def test_saturation(app, fenetre):
    w, err = fenetre
    p = w.g.periodes[0]
    p.uvp[2][0] = 1300
    w._sur_modif(False)
    _attendre(app, w)
    assert w.resultats[0].branches[2].RC < 0
    w._saturer(0, 2)
    app.processEvents()
    noms = [p.nom for p in w.g.periodes]
    assert "HPM SBrRD x Sud" in noms
    res = w.resultats_tab.resultat_courant()
    assert res.periode.branche_saturee == 2
    w._supprimer_saturee(w.resultats_tab.index)
    assert "HPM SBrRD x Sud" not in [p.nom for p in w.g.periodes]
    assert not err


def test_nombre_de_branches_et_angles(app, fenetre):
    w, err = fenetre
    w.site.nb.setValue(5)
    _attendre(app, w)
    assert w.g.n == 5 and all(p.nb_branches == 5 for p in w.g.periodes)
    assert w.trafics.table.rowCount() == 6
    w.site.nb.setValue(4)
    _attendre(app, w)
    w._basculer_angles()
    _attendre(app, w)
    assert w.g.branches[2].angle == 200
    w._basculer_angles()
    assert w.g.branches[2].angle == 180
    assert not err


def test_enregistrer_rouvrir_et_exports(app, fenetre, tmp_path):
    w, err = fenetre
    w.g.nom = "Essai réouverture"
    assert w.enregistrer()
    from girabase import gbs
    assert gbs.lire(w.chemin).nom == "Essai réouverture"
    from girabase.gui.rapport import exporter_pdf
    pdf = tmp_path / "note.pdf"
    assert exporter_pdf(w.g, w.resultats, str(pdf)) >= 3
    assert pdf.stat().st_size > 50_000
    from girabase.dxf_export import exporter_dxf
    exporter_dxf(w.g, tmp_path / "s.dxf")
    assert (tmp_path / "s.dxf").exists()
    assert not err


def test_nouveau_projet_bloque_sans_milieu(app, fenetre):
    w, err = fenetre
    w.modifie_flag = False
    w.nouveau()
    _attendre(app, w)
    assert any("environnement" in e.texte for e in w.erreurs)
    w.site.groupe_milieu.button(1).click()
    w.g.periodes[0].completer_par_zero(w.g.branches)
    w.g.periodes[0].uvp[0][2] = 400
    _attendre(app, w)
    assert w.erreurs == [] and w.resultats[0].complete
    assert not err
