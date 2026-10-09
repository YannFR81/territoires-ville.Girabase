"""Lecture / écriture du format .gbs de Girabase 4."""
import datetime as dt

import pytest

from girabase import gbs
from girabase.calcul import calculer_periode
from girabase.constantes import Milieu, UniteAngle

# Fichier tel que l'écrit l'instruction VB6 « Write # » de GIRATOIRE.Ecrire
EXEMPLE_VB = (
    '"Girabase","Version 4"\r\n'
    '"Variante 2",#2019-05-14#\r\n'
    '"Giratoire RD 612 / RD 81",0\r\n'
    '4,2,0\r\n'
    '15,1.5,8\r\n'
    '"Commune de Test\r\nPR 12+500"\r\n'
    '"BRANCHES"\r\n'
    '"RD 612 Nord",0,#FALSE#,#FALSE#\r\n'
    '#FALSE#,4,4,3,4.5\r\n'
    '"ZA",95,#TRUE#,#TRUE#\r\n'
    '#TRUE#,6,3.5,2.5,4\r\n'
    '"RD 612 Sud",180,#FALSE#,#FALSE#\r\n'
    '#FALSE#,3.5,3.5,.5,0\r\n'
    '"Chemin",270,#FALSE#,#FALSE#\r\n'
    '#FALSE#,0,0,0,3.5\r\n'
    '"TRAFICS"\r\n'
    '"HPM",#TRUE#,255\r\n'
    '"0010 0000 0005 0000"\r\n'
    '"0000 0300 0450 0020"\r\n'
    '"0250 0000 0100 0010"\r\n'
    '"0500 0120 0000 0030"\r\n'
    '"VIDE VIDE VIDE VIDE"\r\n'
    '"HPS",#FALSE#,16711680\r\n'
    '"0010 0010 0010 0010"\r\n'
    '"0000 0280 0400 0015"\r\n"0200 0000 0090 0010"\r\n"0450 0100 0000 0025"\r\nVIDE\r\n'
)


def _exemple_complet():
    # Dernière ligne de la 2e période (VL) : remplacée par une chaîne VIDE valide, puis PL et 2R
    t = EXEMPLE_VB.replace("VIDE\r\n", '"VIDE VIDE VIDE VIDE"\r\n')
    t += '"0000 0010 0020 0001"\r\n"0005 0000 0004 0000"\r\n"0010 0002 0000 0001"\r\n"VIDE VIDE VIDE VIDE"\r\n'
    t += '"0000 0003 0005 0000"\r\n"0001 0000 0000 0000"\r\n"0006 0000 0000 0000"\r\n"VIDE VIDE VIDE VIDE"\r\n'
    return t


def test_lecture_fichier_vb():
    g = gbs.lire_texte(_exemple_complet())
    assert g.nom == "Giratoire RD 612 / RD 81"
    assert g.variante == "Variante 2"
    assert g.date_modif == dt.date(2019, 5, 14)
    assert g.milieu is Milieu.RASE_CAMPAGNE
    assert g.unite_angle is UniteAngle.DEGRE
    assert (g.R, g.Bf, g.LA) == (15, 1.5, 8)
    assert g.localisation == "Commune de Test\nPR 12+500"
    assert [b.angle for b in g.branches] == [0, 95, 180, 270]
    za = g.branches[1]
    assert za.rampe and za.tad and za.evasee and za.le15 == 3.5
    assert g.branches[2].li == 0.5 and g.branches[2].sortie_nulle
    assert g.branches[3].entree_nulle
    hpm, hps = g.periodes
    assert hpm.mode_uvp and hpm.pietons == [10, 0, 5, 0]
    assert hpm.uvp[0] == [0, 300, 450, 20] and hpm.uvp[3] == [None] * 4
    assert hpm.couleur == "#ff0000"
    assert not hps.mode_uvp and hps.couleur == "#0000ff"
    assert hps.vl[0] == [0, 280, 400, 15] and hps.dr[2] == [6, 0, 0, 0]
    # uvp = VL + 2 PL + Int(2R / 2)
    assert hps.matrice_uvp()[0] == [0, 280 + 20 + 1, 400 + 40 + 2, 15 + 2]


def test_aller_retour(tmp_path):
    g = gbs.lire_texte(_exemple_complet())
    chemin = tmp_path / "essai.gbs"
    gbs.ecrire(g, chemin)
    brut = chemin.read_bytes()
    assert brut.startswith(b'"Girabase","Version 4"\r\n')
    assert b"#TRUE#" in brut and b'"BRANCHES"' in brut
    g2 = gbs.lire(chemin)
    assert g2.nom == g.nom and g2.localisation == g.localisation
    assert [vars(b) for b in g2.branches] == [vars(b) for b in g.branches]
    for p1, p2 in zip(g.periodes, g2.periodes):
        assert p1.matrices_saisie() == p2.matrices_saisie()
        assert p1.pietons == p2.pietons and p1.couleur == p2.couleur
    r1 = calculer_periode(g, g.periodes[0])
    r2 = calculer_periode(g2, g2.periodes[0])
    assert [b.C for b in r1.branches] == [b.C for b in r2.branches]


def test_accents_cp1252(tmp_path):
    g = gbs.lire_texte(_exemple_complet())
    g.nom = "Giratoire de l'Écluse — Rivières"
    chemin = tmp_path / "accents.gbs"
    gbs.ecrire(g, chemin)
    assert "Écluse".encode("cp1252") in chemin.read_bytes()
    assert gbs.lire(chemin).nom == "Giratoire de l'Écluse — Rivières"


def test_fichier_invalide():
    with pytest.raises(gbs.ErreurFichierGbs):
        gbs.lire_texte('"Autre chose","Version 1"\r\n')
    mauvais = _exemple_complet().replace('"ZA",95', '"ZA",0')
    with pytest.raises(gbs.ErreurFichierGbs):
        gbs.lire_texte(mauvais)
