"""Cas de référence calculé par GIRABASE 4 d'origine.

Données et résultats relevés sur les captures d'écran du guide utilisateur CERTU/CEREMA
« Girabase Version 4.0 » (révision du 03/06/2015) : figure 2.1 (site), 2.2 (dimensionnement),
2.4 (trafics) et 2.6 (résultats et conseils de fonctionnement).
"""
from pathlib import Path

import pytest

from girabase import formats as F
from girabase import gbs
from girabase.calcul import calculer_periode
from girabase.conseils import erreurs, remarques_fonctionnement
from girabase.constantes import M, Milieu
from girabase.modele import Branche, Giratoire

# (réserve uvp/h, réserve %, file moyenne, file maximale, attente moyenne s, attente totale h) — figure 2.6
ATTENDU = [
    ("-659", "-122 %", "330 véh", "629 véh", "2193 s", "731 h"),
    ("-25", "-5 %", "21 véh", "62 véh", "145 s", "21,6 h"),
    ("2", "0 %", "21 véh", "65 véh", "101 s", "21,0 h"),
    ("-124", "-16 %", "62 véh", "171 véh", "290 s", "71,9 h"),
]


def giratoire_guide() -> Giratoire:
    g = Giratoire(nom="Marcellin/Mendès France", localisation="LYON", milieu=Milieu.PERIURBAIN,
                  R=4, Bf=2, LA=6.2)
    for nom, angle in (("Boulevard Yves Farge", 0), ("Rue des Marguerites", 70),
                       ("Boulevard Vivier Merle", 180), ("Rue des Tarentelles", 288)):
        g.branches.append(Branche(nom, angle, le4=3.5, li=3.0, ls=4.0))
    p = g.nouvelle_periode("Heure de pointe du matin")
    p.uvp = [[50, 300, 250, 600], [15, 0, 400, 120], [300, 400, 0, 50], [159, 486, 248, 0]]
    p.pietons = [10, 30, 10, 20]
    return g


def test_donnees_valides():
    assert erreurs(giratoire_guide()) == []


@pytest.mark.parametrize("k", range(4))
def test_resultats_identiques_au_logiciel_origine(k):
    g = giratoire_guide()
    rb = calculer_periode(g, g.periodes[0]).branches[k]
    assert (F.rc(rb), F.rc_pct(rb), F.lk(rb), F.lkm(rb), F.tma(rb), F.tta(rb)) == ATTENDU[k]


def test_conseils_identiques_au_logiciel_origine():
    g = giratoire_guide()
    rems = remarques_fonctionnement(g, calculer_periode(g, g.periodes[0]))
    par_branche = {k: [r.texte for r in rems if r.branche == k] for k in range(4)}
    assert par_branche[0][0].startswith(M["RCnegative"]) and M["RC2"] in par_branche[0][0]
    assert par_branche[0][1:] == [M["TMA2"], M["LK4"]]
    assert par_branche[1][0].startswith(M["RCnegative"]) and M["RC6"] in par_branche[1][0]
    assert par_branche[1][1:] == [M["TMA2"], M["LK3"]]
    assert par_branche[2][0].startswith(M["RCfaible"]) and M["RC2"] in par_branche[2][0]
    assert par_branche[2][1:] == [M["TMA1"], M["LK3"]]
    assert par_branche[3][0].startswith(M["RCnegative"])
    assert par_branche[3][1:] == [M["TMA2"], M["LK4"]]


def test_fichier_exemple_fourni():
    chemin = Path(__file__).resolve().parent.parent / "exemples" / "exemple_guide_certu.gbs"
    g = gbs.lire(chemin)
    res = calculer_periode(g, g.periodes[0])
    assert [F.rc(b) for b in res.branches] == [a[0] for a in ATTENDU]
