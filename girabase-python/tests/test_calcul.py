"""Tests du moteur : valeurs calculées à la main depuis la note de calcul et le code VB."""
import math

import pytest

from girabase.calcul import (_kae, calculer_periode, capacite_cvh, flux, parametres_branche, parametres_giratoire,
                             periode_inversee, periode_multipliee, periode_saturee)
from girabase.constantes import Milieu, UniteAngle
from girabase.modele import Branche, Giratoire, uvp_cellule


def test_parametres_giratoire_rase_campagne(gir4):
    pg = parametres_giratoire(gir4)
    assert pg.RU == pytest.approx(15.75)
    assert pg.LAU == pytest.approx(8.75)
    assert pg.LEU == pytest.approx(8.75 / (1.2 * (1 + 1 / 31.5)), rel=1e-6)
    assert pg.LImax == pytest.approx(4.75 * math.sqrt(15.75 + 8.75 / 2), rel=1e-6)
    assert pg.KI == pytest.approx(8 / 8.75 * math.sqrt(20 / 24.5), rel=1e-6)
    assert pg.KE == pytest.approx(1 - (15.75 / 24.5) ** 2 * 0.75 / 8.75, rel=1e-6)
    assert (pg.Tg, pg.Tf1) == pytest.approx((4.75, 2.25))


def test_mini_giratoire_coefficients_rase_campagne():
    g = Giratoire(milieu=Milieu.CENTRE_VILLE, R=0, Bf=2, LA=8)
    pg = parametres_giratoire(g)
    assert pg.RU == pytest.approx(3.5)
    assert pg.LAU == pytest.approx(6.5)              # LA + Bf - 3,5
    assert pg.Tg == pytest.approx(4.75) and pg.Te == pytest.approx(0.7)


def test_parametres_branche():
    g = Giratoire(milieu=Milieu.PERIURBAIN, R=10, Bf=0, LA=8)
    pg = parametres_giratoire(g)
    b = Branche("A", le4=7, le15=4, evasee=True, li=2, ls=7, rampe=True)
    pb = parametres_branche(b, pg)
    assert pb.LE == pytest.approx(5.5)
    assert pb.Tf == pytest.approx(2.05 * 1.35, rel=1e-6)
    assert pb.TTP == pytest.approx(4.0)
    slb = 7 - 5
    assert pb.KS == pytest.approx(10 / 18 - (2 + 0.5 * slb) / pg.LImax, rel=1e-5)
    # LE plafonnée par LEU
    large = parametres_branche(Branche("B", le4=11, li=2, ls=4), pg)
    assert large.LEg == pytest.approx(pg.LEU)


def test_trafic_genant_et_capacite_calcul_manuel(gir4):
    res = calculer_periode(gir4, gir4.periodes[0])
    b1 = res.branches[0]
    # Trafic passant devant B1 : B3->B2 (180), B4->B2 (90), B4->B3 (140)
    assert b1.QTournant == 410
    # KAE : sortie B2 à 90° -> 0,6 ; sortie B3 à 180° -> 0,1
    qte = round(0.6 * 180) + round(0.6 * 90) + round(0.1 * 140)
    qti = 410 - qte
    pg = res.params
    qtg = round(pg.KE * qte + pg.KI * qti)
    qs = 250 + 600 + 100
    qsg = round(res.params_branches[0].KS * qs * (1 - qs / (410 + qs)))
    assert b1.QG == qtg + qsg == 507
    cvh = 3600 / 2.25 * math.exp(-507 / 3600 * (4.75 - 2.25 / 2)) * (4 / 3.5) ** 0.7
    assert b1.C == pytest.approx(cvh, rel=1e-5)
    assert b1.RC == pytest.approx(b1.C - 950, rel=1e-6)


def test_temps_attente_trois_regimes():
    from girabase.calcul import ResultatBranche  # noqa: F401
    g = Giratoire(milieu=Milieu.RASE_CAMPAGNE, R=15, Bf=1.5, LA=8)
    for k, a in enumerate([0, 120, 240]):
        g.branches.append(Branche(f"B{k + 1}", angle=a, le4=4, li=3, ls=4.5))
    p = g.nouvelle_periode("P")
    p.pietons = [0, 0, 0]
    for q in (200, 700, 1300):
        p.uvp = [[0, q, 0], [0, 0, 0], [0, 0, 0]]
        rb = calculer_periode(g, p).branches[0]
        csa = q / rb.C
        sq = q / 3600
        e = math.exp(-sq * 2.25)
        if csa < 0.9:
            attendu = (e / (1 - csa) - 1) / sq
        elif csa > 1.1:
            attendu = 1800 * (csa - 1)
        else:
            csb = (10 * e - 1) / sq
            attendu = csb + 5 * (180 - csb) * (csa - 0.9)
        assert rb.TMA == pytest.approx(max(0, attendu), rel=1e-6)
        lk = rb.TMA * min(q, rb.C) / 3600
        assert rb.LK == pytest.approx(lk, rel=1e-5)


def test_kae_degres_et_grades():
    g = Giratoire(milieu=Milieu.RASE_CAMPAGNE)
    assert _kae(g, 0, 60, 1) == pytest.approx(1.0)
    assert _kae(g, 0, 90, 1) == pytest.approx(0.6)
    assert _kae(g, 0, 120, 2) == pytest.approx(0.1)
    assert _kae(g, 0, 90, 3) == pytest.approx(0.1)        # au-delà de la 2e branche
    assert _kae(g, 270, 0, 1) == pytest.approx(0.6)       # passage par 360°
    g.unite_angle = UniteAngle.GRADE
    assert _kae(g, 0, 100, 1) == pytest.approx(0.6)       # 100 gr = 90°


def test_tourne_a_droite_retire_le_mouvement(gir4):
    sans = calculer_periode(gir4, gir4.periodes[0])
    gir4.branches[0].tad = True                            # B1 -> B2 par voie directe (300 uvp)
    avec = calculer_periode(gir4, gir4.periodes[0])
    assert avec.branches[0].QE == 950
    assert avec.branches[0].QEntrant == 650
    assert avec.branches[0].RC > sans.branches[0].RC
    # Le mouvement B1->B2 ne gêne plus l'entrée B2 (sortant) : sa capacité augmente
    assert avec.branches[1].QG < sans.branches[1].QG


def test_pietons_reduisent_la_capacite(gir4):
    p = gir4.periodes[0]
    c0 = calculer_periode(gir4, p).branches[0].C
    p.pietons = [300, 0, 0, 0]
    rb = calculer_periode(gir4, p).branches[0]
    assert 0 < rb.Cp < 0.2
    assert rb.C == pytest.approx(rb.Cvh * (1 - rb.Cp))
    assert rb.C < c0


def test_periode_incomplete_pas_de_resultat(gir4):
    p = gir4.periodes[0]
    p.uvp[1][1] = None                                     # demi-tour non saisi
    res = calculer_periode(gir4, p)
    assert not res.complete
    assert all(b.C == 0 for b in res.branches)


def test_saturation(gir4):
    p = gir4.periodes[0]
    p.uvp[2][0] = 1100                                     # B3 très chargée
    res = calculer_periode(gir4, p)
    k = 2
    assert res.branches[k].RC < 0
    sat = periode_saturee(gir4, p, k)
    assert sat.branche_saturee == k
    coef = res.branches[k].C / res.branches[k].QE
    assert sat.uvp[k][0] == round(1100 * coef)
    res2 = calculer_periode(gir4, sat)
    # Moins de trafic entrant de B3 : moins de gêne pour B4 (B3 -> B1 passe devant B4)
    assert res2.branches[3].QG < res.branches[3].QG
    assert res2.branches[k].RC_pct == 0


def test_inversion_et_multiplication(gir4):
    p = gir4.periodes[0]
    inv = periode_inversee(gir4, p)
    assert inv.uvp[0][2] == p.uvp[2][0]
    mult = periode_multipliee(gir4, p, coef_general=1.1)
    assert mult.uvp[0][2] == round(500 * 1.1)
    ent = periode_multipliee(gir4, p, coefs_entrants=[2, 1, 1, 1])
    assert ent.uvp[0][1] == 600 and ent.uvp[1][0] == 250
    sor = periode_multipliee(gir4, p, coefs_sortants=[2, 1, 1, 1])
    assert sor.uvp[1][0] == 500 and sor.uvp[0][1] == 300


def test_flux_comme_girabase(gir4):
    """Comparaison avec la récurrence de TRAFIC.CalculDiagramFlux."""
    g, p = gir4, gir4.periodes[0]
    n = g.n
    q = p.matrice_uvp()
    f = flux(g, p)
    # Récurrence VB : portion avant la branche 1, puis portion suivante = précédente + entrant - sortant
    portion = sum(q[i][j] for i in range(n) for j in range(i + 1))
    assert f.anneau[n - 1] == portion
    courant = portion
    for k in range(n - 1):
        courant = courant + f.entrants[k] - f.sortants[k]
        assert f.anneau[k] == courant
    assert sum(f.entrants) == sum(f.sortants) == p.total()


def test_uvp_par_categorie():
    assert uvp_cellule(10, 3, 5) == 10 + 6 + 2           # 5 deux-roues -> 2 uvp (troncature Girabase)
    assert uvp_cellule(None, None, None) is None
    assert uvp_cellule(None, 4, None) == 8


def test_courbe_capacite_decroissante(gir4):
    pg = parametres_giratoire(gir4)
    pb = parametres_branche(gir4.branches[0], pg)
    vals = [capacite_cvh(pb, pg, q)[0] for q in range(0, 2701, 100)]
    assert all(a > b for a, b in zip(vals, vals[1:]))
    assert vals[0] == pytest.approx(3600 / 2.25 * (4 / 3.5) ** 0.7, rel=1e-6)


def test_reference_independante_double_precision(gir4):
    """Implémentation directe en double précision : écarts limités aux arrondis Single."""
    g, p = gir4, gir4.periodes[0]
    res = calculer_periode(g, p)
    R, Bf, LA = g.R, g.Bf, g.LA
    RU, LAU = R + Bf / 2, LA + Bf / 2
    LEU = LAU / (1.2 * (1 + 1 / (2 * RU)))
    LImax = 4.75 * math.sqrt(RU + LAU / 2)
    KE = 1 - (RU / (RU + LAU)) ** 2 * (LAU - 8) / LAU if LAU > 8 else 1
    KI = min(KE, 8 / LAU * math.sqrt(20 / (RU + LAU)))
    n = g.n
    for o in range(n):
        b = g.branches[o]
        KS = max(0, RU / (RU + LAU) - b.li / LImax)
        qte = qti = qt = 0.0
        for i in range(1, n):
            for j in range(1, i + 1):
                ei, ej = (o + i) % n, (o + j) % n
                q = p.uvp[ei][ej]
                ecart = (g.branches[ej].angle - b.angle) % 360
                kae = 0.1 if j > 2 else (1 if ecart < 70 else 0.1 if ecart > 115 else (120 - ecart) / 50)
                qte += kae * q
                qti += (1 - kae) * q
                qt += q
        qs = sum(p.uvp[i][o] for i in range(n))
        qg = KE * qte + KI * qti + KS * qs * (1 - qs / (qt + qs))
        assert abs(res.branches[o].QG - qg) <= 2
        c = 3600 / 2.25 * math.exp(-qg / 3600 * (4.75 - 1.125)) * (min(LEU, b.le4) / 3.5) ** 0.7
        assert res.branches[o].C == pytest.approx(c, rel=3e-3)
