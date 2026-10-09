"""Export du schéma de principe au format DXF R12 (1 unité = 1 m), pour AutoCAD / COVADIS.

Écriture directe du format (sans bibliothèque externe) : le DXF R12 s'ouvre et s'insère dans toutes
les versions d'AutoCAD. Le centre du giratoire est en (0,0) et la branche n° 1 suit l'axe des X :
déplacer et orienter le dessin dans AutoCAD (DEPLACER / ROTATION) pour le caler sur le plan.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Optional, Union

from .calcul import Flux
from .geometrie import CALQUES, Primitive, primitives_flux, schema
from .modele import Giratoire

_TYPES_LIGNE = {"continu": "CONTINUOUS", "tirets": "DASHED", "axe": "CENTER"}
_DEFINITIONS_LIGNE = [
    ("CONTINUOUS", "Continu", []),
    ("DASHED", "Tirets __ __ __", [1.2, -0.6]),
    ("CENTER", "Axe ____ _ ____", [2.5, -0.5, 0.5, -0.5]),
]


class _Dxf:
    def __init__(self) -> None:
        self.lignes: list[str] = []

    def g(self, code: int, valeur) -> None:
        if isinstance(valeur, float):
            valeur = f"{valeur:.6f}".rstrip("0").rstrip(".") or "0"
        self.lignes.append(f"{code:>3}")
        self.lignes.append(str(valeur))

    def texte(self) -> str:
        return "\r\n".join(self.lignes) + "\r\n"


def _entete(d: _Dxf, xmin: float, ymin: float, xmax: float, ymax: float) -> None:
    d.g(0, "SECTION"); d.g(2, "HEADER")
    d.g(9, "$ACADVER"); d.g(1, "AC1009")
    d.g(9, "$DWGCODEPAGE"); d.g(3, "ANSI_1252")
    d.g(9, "$INSBASE"); d.g(10, 0.0); d.g(20, 0.0); d.g(30, 0.0)
    d.g(9, "$EXTMIN"); d.g(10, xmin); d.g(20, ymin); d.g(30, 0.0)
    d.g(9, "$EXTMAX"); d.g(10, xmax); d.g(20, ymax); d.g(30, 0.0)
    d.g(9, "$LTSCALE"); d.g(40, 1.0)
    d.g(0, "ENDSEC")


def _tables(d: _Dxf) -> None:
    d.g(0, "SECTION"); d.g(2, "TABLES")
    d.g(0, "TABLE"); d.g(2, "LTYPE"); d.g(70, len(_DEFINITIONS_LIGNE))
    for nom, desc, motif in _DEFINITIONS_LIGNE:
        d.g(0, "LTYPE"); d.g(2, nom); d.g(70, 0); d.g(3, desc); d.g(72, 65)
        d.g(73, len(motif)); d.g(40, float(sum(abs(x) for x in motif)))
        for x in motif:
            d.g(49, float(x))
    d.g(0, "ENDTAB")
    d.g(0, "TABLE"); d.g(2, "LAYER"); d.g(70, len(CALQUES) + 1)
    for nom, couleur in [("0", 7)] + list(CALQUES.items()):
        d.g(0, "LAYER"); d.g(2, nom); d.g(70, 0); d.g(62, couleur); d.g(6, "CONTINUOUS")
    d.g(0, "ENDTAB")
    d.g(0, "TABLE"); d.g(2, "STYLE"); d.g(70, 2)
    for nom, police in (("STANDARD", "txt"), ("GIRA", "arial.ttf")):
        d.g(0, "STYLE"); d.g(2, nom); d.g(70, 0); d.g(40, 0.0); d.g(41, 1.0); d.g(50, 0.0)
        d.g(71, 0); d.g(42, 2.5); d.g(3, police); d.g(4, "")
    d.g(0, "ENDTAB")
    d.g(0, "ENDSEC")


def _commun(d: _Dxf, calque: str, style: str = "continu") -> None:
    d.g(8, calque)
    if style != "continu":
        d.g(6, _TYPES_LIGNE[style])


def _polyligne(d: _Dxf, pts, calque: str, ferme: bool = False, largeur: float = 0.0, style: str = "continu"):
    d.g(0, "POLYLINE")
    _commun(d, calque, style)
    d.g(66, 1)
    d.g(10, 0.0); d.g(20, 0.0); d.g(30, 0.0)
    d.g(70, 1 if ferme else 0)
    if largeur:
        d.g(40, largeur); d.g(41, largeur)
    for x, y in pts:
        d.g(0, "VERTEX"); d.g(8, calque); d.g(10, x); d.g(20, y); d.g(30, 0.0)
    d.g(0, "SEQEND"); d.g(8, calque)


def _texte(d: _Dxf, x: float, y: float, valeur: str, hauteur: float, calque: str) -> None:
    d.g(0, "TEXT"); d.g(8, calque)
    d.g(10, x); d.g(20, y); d.g(30, 0.0)
    d.g(40, hauteur); d.g(1, valeur.replace("\n", " ")); d.g(7, "GIRA")
    d.g(72, 1)                     # centré horizontalement
    d.g(11, x); d.g(21, y); d.g(31, 0.0)
    d.g(73, 2)                     # centré verticalement


def _entite(d: _Dxf, p: Primitive, decal: tuple[float, float]) -> None:
    dx, dy = decal
    pts = [(x + dx, y + dy) for x, y in p.points]
    if p.type == "cercle":
        d.g(0, "CIRCLE"); _commun(d, p.calque, p.style)
        d.g(10, pts[0][0]); d.g(20, pts[0][1]); d.g(30, 0.0); d.g(40, p.rayon)
    elif p.type == "ligne":
        if p.epaisseur:
            _polyligne(d, pts, p.calque, largeur=p.epaisseur)
        else:
            d.g(0, "LINE"); _commun(d, p.calque, p.style)
            d.g(10, pts[0][0]); d.g(20, pts[0][1]); d.g(30, 0.0)
            d.g(11, pts[1][0]); d.g(21, pts[1][1]); d.g(31, 0.0)
    elif p.type == "polyligne":
        _polyligne(d, pts, p.calque, ferme=p.ferme, style=p.style)
    elif p.type == "arc":
        cx, cy = pts[0]
        if p.epaisseur:
            nb = max(8, int((p.angle_fin - p.angle_debut) * 20))
            arc = [(cx + p.rayon * math.cos(p.angle_debut + (p.angle_fin - p.angle_debut) * t / nb),
                    cy + p.rayon * math.sin(p.angle_debut + (p.angle_fin - p.angle_debut) * t / nb))
                   for t in range(nb + 1)]
            _polyligne(d, arc, p.calque, largeur=p.epaisseur)
        else:
            d.g(0, "ARC"); _commun(d, p.calque, p.style)
            d.g(10, cx); d.g(20, cy); d.g(30, 0.0); d.g(40, p.rayon)
            d.g(50, math.degrees(p.angle_debut)); d.g(51, math.degrees(p.angle_fin))
    elif p.type == "texte":
        _texte(d, pts[0][0], pts[0][1], p.texte, p.hauteur, p.calque)


def contenu_dxf(g: Giratoire, flux: Optional[Flux] = None, origine: tuple[float, float] = (0.0, 0.0),
                rotation_deg: float = 0.0) -> str:
    prims = schema(g)
    if flux is not None:
        prims += primitives_flux(g, flux.entrants, flux.sortants, flux.anneau)
    if rotation_deg:
        a = math.radians(rotation_deg)
        c, s = math.cos(a), math.sin(a)
        for p in prims:
            p.points = [(x * c - y * s, x * s + y * c) for x, y in p.points]
            p.angle_debut += a
            p.angle_fin += a
    ox, oy = origine
    e = g.Rg + 40
    d = _Dxf()
    _entete(d, ox - e, oy - e, ox + e, oy + e)
    _tables(d)
    d.g(0, "SECTION"); d.g(2, "ENTITIES")
    for p in prims:
        _entite(d, p, origine)
    titre = f"{g.nom} - {g.variante} - Rg = {g.Rg:.2f} m".replace(".", ",")
    _texte(d, ox, oy - g.Rg - 25, titre, 2.0, "GIRA_TEXTES")
    _texte(d, ox, oy - g.Rg - 28.5, "Schéma de principe Girabase - ne vaut pas plan d'exécution", 1.2,
           "GIRA_TEXTES")
    d.g(0, "ENDSEC")
    d.g(0, "EOF")
    return d.texte()


def exporter_dxf(g: Giratoire, chemin: Union[str, Path], flux: Optional[Flux] = None,
                 origine: tuple[float, float] = (0.0, 0.0), rotation_deg: float = 0.0) -> None:
    texte = contenu_dxf(g, flux, origine, rotation_deg)
    Path(chemin).write_bytes(texte.encode("cp1252", errors="replace"))
