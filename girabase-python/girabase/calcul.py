"""Moteur de calcul de capacité Girabase 4 — portage fidèle du code VB6 du CERTU.

Sources : GIRATOIRE.cls (CalculParamGiratoire, MajComplément), BRANCHE.cls
(CalculParamBranche, getCVH), TRAFIC.cls (CalculTraficEntrant, TraficGenant, KAE,
RéserveCapacité, TempsAttente, LongueurStockage).

Les grandeurs déclarées ``Single`` dans le code d'origine sont arrondies en simple
précision (``_sng``) et les affectations à des ``Integer`` utilisent l'arrondi
bancaire de VB (``round`` de Python), pour reproduire les mêmes valeurs entières de
trafic gênant que le logiciel d'origine.
"""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass, field
from typing import Optional

from .constantes import COEF_LEU, COEF_RAMPE, TE, TF1, TG, Milieu, UniteAngle
from .modele import Branche, Giratoire, Periode


def _sng(x: float) -> float:
    """Arrondi en simple précision (type Single de VB6)."""
    return struct.unpack("f", struct.pack("f", x))[0]


def _cint(x: float) -> int:
    """Affectation VB à un Integer : arrondi au pair le plus proche."""
    return int(round(x))


@dataclass
class ParametresGiratoire:
    RU: float      # rayon utile de l'îlot infranchissable
    LAU: float     # largeur utile de l'anneau
    LEU: float     # largeur d'entrée utile maximale
    LImax: float   # largeur d'îlot au-delà de laquelle le trafic sortant ne gêne plus
    KI: float      # coefficient de gêne du trafic tournant à l'intérieur de l'anneau
    KE: float      # coefficient de gêne du trafic tournant à l'extérieur de l'anneau
    Tg: float      # créneau critique
    Te: float      # exposant de largeur d'entrée
    Tf1: float     # créneau complémentaire


@dataclass
class ParametresBranche:
    Tf: float      # créneau complémentaire retenu (majoré si rampe)
    LE: float      # largeur d'entrée (moyenne 4 m / 15 m si évasée)
    LEg: float     # largeur d'entrée retenue par Girabase = min(LEU, LE)
    KS: float      # coefficient de gêne du trafic sortant
    TTP: float     # temps de traversée piéton


@dataclass
class ResultatBranche:
    index: int
    nom: str
    entree_nulle: bool
    sortie_nulle: bool
    QE: int = 0            # trafic entrant total (y compris tourne-à-droite direct)
    QS: int = 0            # trafic sortant total
    QEntrant: int = 0      # trafic entrant sur l'anneau (hors voie directe de TAD)
    QTournant: int = 0     # trafic tournant au droit de l'entrée
    QSortant: int = 0      # trafic sortant pris en compte dans la gêne
    QG: int = 0            # trafic gênant
    Cvh: float = 0.0       # capacité avant prise en compte des piétons
    Cp: float = 0.0        # perte de capacité due aux piétons (fraction)
    C: float = 0.0         # capacité de l'entrée (uvp/h)
    RC: float = 0.0        # réserve de capacité (uvp/h)
    TMA: float = 0.0       # temps moyen d'attente (s)
    TTA: float = 0.0       # temps total d'attente (s)
    LK: float = 0.0        # longueur moyenne de stockage (véhicules)
    LKM: float = 0.0       # longueur maximale de stockage (véhicules)
    saturee: bool = False  # entrée limitée à sa capacité (période "saturer la branche")

    @property
    def RC_pct(self) -> Optional[float]:
        """Réserve de capacité en % de la capacité."""
        if self.entree_nulle or self.C == 0:
            return None
        rc = 0.0 if self.saturee else self.RC
        return 100.0 * rc / self.C

    @property
    def rc_affichee(self) -> float:
        return 0.0 if self.saturee else self.RC


@dataclass
class ResultatPeriode:
    periode: Periode
    complete: bool
    params: Optional[ParametresGiratoire] = None
    params_branches: list[ParametresBranche] = field(default_factory=list)
    branches: list[ResultatBranche] = field(default_factory=list)

    @property
    def total_entrant(self) -> int:
        return sum(b.QE for b in self.branches)

    def branches_saturees(self) -> list[int]:
        return [b.index for b in self.branches if not b.entree_nulle and b.RC < 0 and not b.saturee]


# ---------------------------------------------------------------------------
# Paramètres géométriques
# ---------------------------------------------------------------------------
def parametres_giratoire(g: Giratoire) -> ParametresGiratoire:
    if g.milieu is None:
        raise ValueError("Le type de site (milieu) n'est pas défini.")
    R, Bf, LA = _sng(g.R), _sng(g.Bf), _sng(g.LA)
    if R == 0:
        # Mini-giratoire : coefficients de rase campagne (e-mail CERTU du 6/9/99)
        cle = Milieu.RASE_CAMPAGNE
        RU = _sng(3.5)
        LAU = _sng(LA + Bf - 3.5)
    else:
        cle = Milieu(g.milieu)
        RU = _sng(R + 0.5 * Bf)          # Modificatif 29/12/98
        LAU = _sng(LA + 0.5 * Bf)
    Tg, Te, Tf1 = _sng(TG[cle]), _sng(TE[cle]), _sng(TF1[cle])
    LEU = _sng(LAU / (COEF_LEU * (1 + 1 / 2 / RU)))           # §2.1.1
    LImax = _sng(Tg * math.sqrt(RU + LAU / 2))                 # §2.1.4
    KI = _sng(8 / LAU * math.sqrt(20 / (RU + LAU)))            # §2.2.1 modifié 12/03/99
    if LAU > 8:
        KE = _sng(1 - (RU / (RU + LAU)) ** 2 * (LAU - 8) / LAU)
    else:
        KE = _sng(1.0)
    KI = min(KE, KI)                                           # §2.3.3
    return ParametresGiratoire(RU=RU, LAU=LAU, LEU=LEU, LImax=LImax, KI=KI, KE=KE, Tg=Tg, Te=Te, Tf1=Tf1)


def parametres_branche(b: Branche, pg: ParametresGiratoire) -> ParametresBranche:
    Tf = _sng(pg.Tf1 * COEF_RAMPE) if b.rampe else pg.Tf1      # §1.3
    le4, le15, li, ls = _sng(b.le4), _sng(b.le15), _sng(b.li), _sng(b.ls)
    LE = _sng((le4 + le15) / 2) if b.evasee else le4           # §1.2
    LEg = min(pg.LEU, LE)                                      # §2.1.2
    SLB = max(_sng(ls - 5.0), 0.0)                             # surlargeur de sortie §2.1.3
    KS = _sng(pg.RU / (pg.RU + pg.LAU) - (li + 0.5 * SLB) / pg.LImax)
    KS = max(0.0, KS)                                          # ajout CERTU 08/03/99
    TTP = min(le4, 4.0)                                        # §2.5.3 (vitesse piéton 1 m/s)
    return ParametresBranche(Tf=Tf, LE=LE, LEg=LEg, KS=KS, TTP=TTP)


def capacite_cvh(pb: ParametresBranche, pg: ParametresGiratoire, qg: float) -> tuple[float, float]:
    """Capacité Cvh pour un trafic gênant qg (BRANCHE.getCVH). Retourne (Cvh, exposant)."""
    qg_s = _sng(qg / 3600)
    exposant = -qg_s * (pg.Tg - pb.Tf / 2)                     # §2.5.1
    ci = 3600 / pb.Tf * math.exp(exposant)
    return ci * (pb.LEg / 3.5) ** pg.Te, exposant              # §2.5.2


def courbe_capacite(pb: ParametresBranche, pg: ParametresGiratoire,
                    qg_max: int = 2700, pas: int = 10) -> list[tuple[int, float]]:
    return [(q, capacite_cvh(pb, pg, q)[0]) for q in range(0, qg_max + 1, pas)]


# ---------------------------------------------------------------------------
# Trafic gênant
# ---------------------------------------------------------------------------
def _kae(g: Giratoire, angle_entree: int, angle_sortie: int, j: int) -> float:
    """Coefficient d'affectation du trafic tournant à l'extérieur de l'anneau (§2.3.2)."""
    if j not in (1, 2):
        return _sng(0.1)
    if angle_sortie < angle_entree:
        angle_sortie += 2 * g.unite_angle.demi_tour
    ecart = abs(angle_entree - angle_sortie)
    if g.unite_angle is UniteAngle.GRADE:
        ecart = _cint(ecart * 0.9)        # formules en degrés (corrigé v1.0.24)
    if ecart < 70:
        return _sng(1.0)
    if ecart > 115:
        return _sng(0.1)
    return _sng((120 - ecart) / 50)


def _matrice_calcul(g: Giratoire, p: Periode) -> tuple[list[list[int]], list[int], list[int], list[int]]:
    """CalculTraficEntrant : matrice corrigée (TAD retirés), QE, QS, QEntrant."""
    n = g.n
    uvp = p.matrice_uvp()
    QE = [sum(v or 0 for v in uvp[i]) for i in range(n)]
    QS = [sum((uvp[i][j] or 0) for i in range(n)) for j in range(n)]
    Q = [[0] * n for _ in range(n)]
    QEntrant = QE[:]
    for i in range(n):
        for j in range(n):
            v = uvp[i][j]
            if g.branches[i].tad and j == g.suivante(i):
                Q[i][j] = 0
                QEntrant[i] -= v or 0
            else:
                Q[i][j] = v or 0
    return Q, QE, QS, QEntrant


def _trafic_genant(g: Giratoire, pg: ParametresGiratoire, pb: ParametresBranche,
                   Q: list[list[int]], o: int) -> tuple[int, int, int]:
    """TRAFIC.TraficGenant pour l'entrée o. Retourne (QG, QTournant, QSortant)."""
    n = g.n
    angle = g.branches[o].angle
    qte = qti = qt = 0
    # Renumérotation : la branche étudiée devient 0, les suivantes 1..n-1 dans le sens de giration.
    # Un mouvement de ei vers ej passe devant l'entrée o si ej est "avant ou égal" à ei.
    for i in range(1, n):
        ei = (o + i) % n
        for j in range(1, i + 1):
            ej = (o + j) % n
            q = Q[ei][ej]
            w_qte = _cint(_sng(_kae(g, angle, g.branches[ej].angle, j) * q))
            qte += w_qte
            qti += q - w_qte
            qt += q
    q_tournant_genant = _cint(pg.KE * qte + pg.KI * qti)        # §2.3.3
    q_sortant = sum(Q[i][o] for i in range(n))                  # §2.4 (mod. 25/03/99)
    if qt + q_sortant > 0:
        q_sortant_genant = _cint(pb.KS * q_sortant * (1 - q_sortant / (qt + q_sortant)))
        qg = q_tournant_genant + q_sortant_genant
    else:
        qg = q_tournant_genant
    return qg, qt, q_sortant


# ---------------------------------------------------------------------------
# Calcul d'une période
# ---------------------------------------------------------------------------
def calculer_periode(g: Giratoire, p: Periode) -> ResultatPeriode:
    res = ResultatPeriode(periode=p, complete=p.est_complete(g.branches))
    pg = parametres_giratoire(g)
    res.params = pg
    res.params_branches = [parametres_branche(b, pg) for b in g.branches]
    Q, QE, QS, QEntrant = _matrice_calcul(g, p)
    for k, b in enumerate(g.branches):
        rb = ResultatBranche(index=k, nom=b.nom, entree_nulle=b.entree_nulle, sortie_nulle=b.sortie_nulle,
                             QE=QE[k], QS=QS[k], QEntrant=QEntrant[k],
                             saturee=(p.branche_saturee == k))
        res.branches.append(rb)
        if not res.complete or b.entree_nulle:
            continue
        pb = res.params_branches[k]
        rb.QG, rb.QTournant, rb.QSortant = _trafic_genant(g, pg, pb, Q, k)
        # Réserve de capacité §2.5
        rb.Cvh, exposant = capacite_cvh(pb, pg, rb.QG)
        qp = p.pietons[k] or 0
        rb.Cp = pb.TTP / 10 * (1 - math.exp(-qp / 360)) * (1800 + qp) / 2160 * math.exp(exposant)
        rb.C = rb.Cvh * (1 - rb.Cp)
        rb.RC = rb.C - rb.QEntrant
        # Temps d'attente §2.6
        qe = rb.QEntrant
        if qe == 0:
            rb.TMA = rb.TTA = 0.0
        else:
            csa = qe / rb.C
            sq = qe / 3600
            expo = -sq * pb.Tf
            if csa < 0.9:
                tma = (math.exp(expo) / (1 - csa) - 1) / sq
            elif csa > 1.1:
                tma = 1800 * (csa - 1)
            else:  # formule corrigée B. Guichet, 25/03/99
                csb = (10 * math.exp(expo) - 1) / sq
                tma = csb + 5 * (180 - csb) * (csa - 0.9)
            rb.TMA = max(0.0, tma)
            rb.TTA = rb.TMA * qe
        # Longueurs de stockage §2.7
        rb.LK = _sng(rb.TMA * min(qe, rb.C) / 3600)
        if qe < rb.C:
            rb.LKM = _sng(2 + 3 * rb.LK)
        else:
            rb.LKM = _sng(2 + (3 + 2 * rb.RC / qe) * rb.LK)
    return res


def calculer(g: Giratoire) -> list[ResultatPeriode]:
    return [calculer_periode(g, p) for p in g.periodes]


# ---------------------------------------------------------------------------
# Opérations sur les périodes (inversion, multiplication, saturation)
# ---------------------------------------------------------------------------
def _dupliquer(g: Giratoire, src: Periode, nom: str, transfo) -> Periode:
    dst = src.copie(nom)
    for cle, mat_src in src.matrices_saisie().items():
        mat_dst = getattr(dst, cle)
        for i in range(g.n):
            for j in range(g.n):
                if g.branches[i].entree_nulle or g.branches[j].sortie_nulle:
                    mat_dst[i][j] = None
                else:
                    mat_dst[i][j] = transfo(mat_src, i, j)
    return dst


def periode_inversee(g: Giratoire, src: Periode, nom: Optional[str] = None) -> Periode:
    """Trafic de P vers N -> trafic de N vers P (piétons conservés)."""
    return _dupliquer(g, src, nom or f"Inversion de {src.nom}", lambda m, i, j: m[j][i])


def periode_multipliee(g: Giratoire, src: Periode, coef_general: Optional[float] = None,
                       coefs_entrants: Optional[list[float]] = None,
                       coefs_sortants: Optional[list[float]] = None,
                       nom: Optional[str] = None) -> Periode:
    """Multiplication d'une matrice : coefficient global, par branche d'entrée ou de sortie."""
    def coef(i: int, j: int) -> float:
        if coefs_entrants is not None:
            return _sng(coefs_entrants[i])
        if coefs_sortants is not None:
            return _sng(coefs_sortants[j])
        return _sng(coef_general if coef_general is not None else 1.0)

    def transfo(m, i, j):
        v = m[i][j]
        return None if v is None else _cint(v * coef(i, j))

    return _dupliquer(g, src, nom or f"Multiplication de {src.nom}", transfo)


def periode_saturee(g: Giratoire, src: Periode, k: int) -> Periode:
    """Saturer la branche k : son trafic entrant est ramené à sa capacité (C / QE)."""
    res = calculer_periode(g, src)
    rb = res.branches[k]
    if rb.QE == 0:
        raise ValueError("La branche n'a pas de trafic entrant.")
    coefs = [1.0] * g.n
    coefs[k] = _sng(rb.C / rb.QE)
    p = periode_multipliee(g, src, coefs_entrants=coefs, nom=f"{src.nom} SBr{g.branches[k].nom}")
    p.branche_saturee = k
    p.periode_origine = src.nom
    return p


# ---------------------------------------------------------------------------
# Diagramme de flux
# ---------------------------------------------------------------------------
@dataclass
class Flux:
    entrants: list[int]     # trafic entrant sur l'anneau par branche (hors TAD direct)
    sortants: list[int]     # trafic sortant de l'anneau par branche (hors TAD direct)
    anneau: list[int]       # anneau[k] : trafic entre la branche k et la suivante


def flux(g: Giratoire, p: Periode) -> Flux:
    """Trafics par section (cases vides comptées nulles, TAD directs exclus)."""
    n = g.n
    uvp = p.matrice_uvp()
    entrants, sortants, anneau = [0] * n, [0] * n, [0] * n
    for i in range(n):
        for j in range(n):
            q = uvp[i][j] or 0
            if q == 0 or (g.branches[i].tad and j == g.suivante(i)):
                continue
            entrants[i] += q
            sortants[j] += q
            nb_sections = (j - i) % n or n
            for s in range(nb_sections):
                anneau[(i + s) % n] += q
    return Flux(entrants, sortants, anneau)
