"""Géométrie du schéma de principe du giratoire (en mètres, repère direct, centre en 0,0).

La branche n° 1 est sur l'axe des X ; les angles croissent dans le sens trigonométrique
(sens de giration, circulation à droite). Dans le repère local d'une branche (u vers
l'extérieur, v à gauche de u), la voie d'entrée est du côté +v et la sortie du côté -v.

Les primitives produites servent à la fois au dessin à l'écran et à l'export DXF.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from .constantes import LONGUEUR_BRANCHE_DESSIN
from .modele import Giratoire

Point = tuple[float, float]

CALQUES = {
    "GIRA_ILOT_CENTRAL": 3,      # vert
    "GIRA_BANDE_FRANCH": 8,      # gris
    "GIRA_ANNEAU": 7,            # blanc/noir
    "GIRA_BORDS_BRANCHES": 7,
    "GIRA_ILOTS_SEPARATEURS": 3,
    "GIRA_AXES": 1,              # rouge
    "GIRA_TEXTES": 2,            # jaune
    "GIRA_FLUX": 5,              # bleu
}


@dataclass
class Primitive:
    type: str                         # "cercle", "ligne", "polyligne", "texte", "arc"
    calque: str
    points: list[Point] = field(default_factory=list)
    rayon: float = 0.0
    texte: str = ""
    hauteur: float = 1.5
    ferme: bool = False
    style: str = "continu"            # "continu", "tirets", "axe"
    angle_debut: float = 0.0          # radians (arcs)
    angle_fin: float = 0.0
    epaisseur: float = 0.0            # flux : largeur représentative (m)


def _rot(x: float, y: float, theta: float) -> Point:
    c, s = math.cos(theta), math.sin(theta)
    return (x * c - y * s, x * s + y * c)


def longueur_ilot(li: float) -> float:
    return max(3 * li, 6.0) if li > 0 else 0.0


def schema(g: Giratoire, longueur_branche: float = LONGUEUR_BRANCHE_DESSIN) -> list[Primitive]:
    prims: list[Primitive] = []
    rg = g.Rg
    if g.R > 0:
        prims.append(Primitive("cercle", "GIRA_ILOT_CENTRAL", [(0, 0)], rayon=g.R))
    if g.Bf > 0:
        prims.append(Primitive("cercle", "GIRA_BANDE_FRANCH", [(0, 0)], rayon=g.R + g.Bf, style="tirets"))
    prims.append(Primitive("cercle", "GIRA_ANNEAU", [(0, 0)], rayon=rg))

    for k, b in enumerate(g.branches):
        th = g.angle_rad(k)
        lilot = longueur_ilot(b.li) if not (b.entree_nulle or b.sortie_nulle) else 0.0
        xfin = rg + max(longueur_branche, lilot + 4)
        li2 = b.li / 2 if lilot else 0.0

        def P(x: float, y: float) -> Point:
            return _rot(x, y, th)

        # Axe de la branche
        prims.append(Primitive("ligne", "GIRA_AXES", [P(rg, 0), P(xfin, 0)], style="axe"))
        if not b.entree_nulle:
            ye = b.le4 + li2
            x0 = math.sqrt(max(rg * rg - ye * ye, 0.0))
            pts = [P(x0, ye)]
            if lilot:
                pts.append(P(rg + lilot, b.le4))
            pts.append(P(xfin, b.le4))
            prims.append(Primitive("polyligne", "GIRA_BORDS_BRANCHES", pts))
        if not b.sortie_nulle:
            ys = b.ls + li2
            x0 = math.sqrt(max(rg * rg - ys * ys, 0.0))
            pts = [P(x0, -ys)]
            if lilot:
                pts.append(P(rg + lilot, -b.ls))
            pts.append(P(xfin, -b.ls))
            prims.append(Primitive("polyligne", "GIRA_BORDS_BRANCHES", pts))
        if lilot:
            x0 = math.sqrt(max(rg * rg - li2 * li2, 0.0))
            prims.append(Primitive("polyligne", "GIRA_ILOTS_SEPARATEURS",
                                   [P(x0, li2), P(rg + lilot, 0), P(x0, -li2)], ferme=False))
        # Textes
        prims.append(Primitive("texte", "GIRA_TEXTES", [P(xfin + 3, 0)], texte=b.nom, hauteur=1.6))
        prims.append(Primitive("texte", "GIRA_TEXTES", [P(rg - 2.5, 0)], texte=str(k + 1), hauteur=1.4))
    return prims


def emprise(g: Giratoire, longueur_branche: float = LONGUEUR_BRANCHE_DESSIN) -> float:
    """Demi-côté du carré englobant le schéma (m)."""
    lmax = max([longueur_branche] + [longueur_ilot(b.li) + 4 for b in g.branches])
    return g.Rg + lmax + 10


def primitives_flux(g: Giratoire, entrants: list[int], sortants: list[int], anneau: list[int],
                    largeur_max: Optional[float] = None,
                    longueur_branche: float = LONGUEUR_BRANCHE_DESSIN) -> list[Primitive]:
    """Diagramme de flux : épaisseur proportionnelle au trafic (uvp/h)."""
    qmax = max(entrants + sortants + anneau + [1])
    if largeur_max is None:
        largeur_max = max(1.0, min(g.LA * 0.8, 6.0))
    k_ep = largeur_max / qmax
    rf = g.R + g.Bf + g.LA / 2
    prims: list[Primitive] = []
    n = g.n
    for k in range(n):
        b = g.branches[k]
        th = g.angle_rad(k)
        k2 = (k + 1) % n
        b2 = g.branches[k2]
        th2 = g.angle_rad(k2) + (2 * math.pi if k2 == 0 else 0)
        li2 = b.li / 2 if not (b.entree_nulle or b.sortie_nulle) else 0.0
        li2b = b2.li / 2 if not (b2.entree_nulle or b2.sortie_nulle) else 0.0
        a_dep = th + (li2 + b.le4 / 2) / rf
        a_fin = th2 - (li2b + b2.ls / 2) / rf
        if anneau[k] > 0 and a_fin > a_dep:
            prims.append(Primitive("arc", "GIRA_FLUX", [(0, 0)], rayon=rf, angle_debut=a_dep,
                                   angle_fin=a_fin, epaisseur=max(0.2, anneau[k] * k_ep),
                                   texte=str(anneau[k])))
        xfin = g.Rg + longueur_branche * 0.8
        if entrants[k] > 0:
            ye = li2 + b.le4 / 2
            prims.append(Primitive("ligne", "GIRA_FLUX", [_rot(rf, ye, th), _rot(xfin, ye, th)],
                                   epaisseur=max(0.2, entrants[k] * k_ep), texte=str(entrants[k])))
        if sortants[k] > 0:
            ys = -(li2 + b.ls / 2)
            prims.append(Primitive("ligne", "GIRA_FLUX", [_rot(rf, ys, th), _rot(xfin, ys, th)],
                                   epaisseur=max(0.2, sortants[k] * k_ep), texte=str(sortants[k])))
    return prims
