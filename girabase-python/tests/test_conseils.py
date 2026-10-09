"""Contrôles de validité et conseils."""
from girabase.calcul import calculer_periode
from girabase.conseils import (demi_angles_branche, erreurs, recommandations_saisie, remarques_conception,
                               remarques_fonctionnement, remarques_trafics)
from girabase.constantes import M, Milieu


def textes(rems):
    return " | ".join(r.texte for r in rems)


def test_cas_de_base_valide(gir4):
    assert erreurs(gir4) == []


def test_milieu_obligatoire(gir4):
    gir4.milieu = None
    assert "environnement" in textes(erreurs(gir4))


def test_mini_giratoire_interdit_en_rase_campagne(gir4):
    gir4.R, gir4.Bf, gir4.LA = 0, 2, 8
    t = textes(erreurs(gir4))
    assert M["RNulEnRC"] in t


def test_rayon_exterieur_minimal(gir4):
    gir4.R, gir4.Bf, gir4.LA = 3, 0, 6
    assert "supérieure à 12" in textes(erreurs(gir4))


def test_chevauchement_branches(gir4):
    gir4.branches[1].angle = 20
    assert "se chevauchent" in textes(erreurs(gir4))
    assert demi_angles_branche(4, 3, 4.5, 4.0) is None


def test_rapport_evasement(gir4):
    b = gir4.branches[0]
    b.evasee, b.le4, b.le15 = True, 9, 3
    assert M["RapportLE"] in textes(erreurs(gir4))


def test_trafic_sur_entree_nulle(gir4):
    gir4.branches[3].le4 = 0
    gir4.branches[3].li = 0
    assert "largeur d'entrée est nulle" in textes(erreurs(gir4))


def test_recommandations(gir4):
    gir4.LA = 10
    gir4.branches[0].le4 = 2
    t = textes(recommandations_saisie(gir4))
    assert M["LATropGrand"] in t
    assert M["LE2Roues"] in t


def test_conseils_entree_saturee(gir4):
    p = gir4.periodes[0]
    p.uvp[2][0] = 1100
    res = calculer_periode(gir4, p)
    f = remarques_fonctionnement(gir4, res)
    sat = [r for r in f if r.branche == 2 and r.texte.startswith(M["RCnegative"])]
    assert sat, textes(f)
    assert M["RC11"] in textes([r for r in f if r.branche == 2])      # mouvement >= 1000


def test_conseils_surdimensionnement():
    from girabase.modele import Branche, Giratoire
    g = Giratoire(milieu=Milieu.PERIURBAIN, R=20, Bf=0, LA=9)
    for k, a in enumerate([0, 120, 240]):
        g.branches.append(Branche(f"B{k + 1}", angle=a, le4=7, li=3, ls=4))
    p = g.nouvelle_periode("Creuse")
    p.uvp = [[0, 100, 100], [100, 0, 100], [100, 100, 0]]
    p.pietons = [0, 0, 0]
    res = calculer_periode(g, p)
    assert M["RC12"] in textes(remarques_fonctionnement(g, res))


def test_remarques_trafics_et_conception(gir4):
    gir4.branches[0].tad = True
    p = gir4.periodes[0]
    p.uvp[0][1] = 50
    res = calculer_periode(gir4, p)
    assert M["QTropPetitPourTAD"] in textes(remarques_trafics(gir4, res))
    gir4.R = 30
    assert M["RTropGrand"] in textes(remarques_conception(gir4, res))
