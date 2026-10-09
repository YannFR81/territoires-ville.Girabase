"""Analyse géométrique du carrefour : anneau existant, branches, orientations et angles Girabase."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from .geoservices import Troncon
from .projections import vers_local

CARDINAUX_4 = ["Nord", "Est", "Sud", "Ouest"]
CARDINAUX_8 = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"]
CARDINAUX_8_LONG = ["Nord", "Nord-Est", "Est", "Sud-Est", "Sud", "Sud-Ouest", "Ouest", "Nord-Ouest"]


def cardinal4(az: float) -> str:
    return CARDINAUX_4[int(((az % 360) + 45) // 90) % 4]


def cardinal8(az: float, long: bool = False) -> str:
    i = int(((az % 360) + 22.5) // 45) % 8
    return (CARDINAUX_8_LONG if long else CARDINAUX_8)[i]


def nom_branche(numero: str, nom_voie: str, az: float) -> str:
    """Nom proposé : « D71 Nord », ou la voie et l'orientation si la route n'est pas numérotée."""
    base = numero or nom_voie or "Branche"
    return f"{base} {cardinal4(az)}"


def angle_girabase(az_branche1: float, az: float) -> float:
    """Angle Girabase (sens de giration, inverse des aiguilles d'une montre) depuis la branche 1."""
    return (az_branche1 - az) % 360


# ---------------------------------------------------------------------------
# Anneau existant (tronçons « Rond-point » de la BD TOPO)
# ---------------------------------------------------------------------------
@dataclass
class AnneauDetecte:
    lat: float
    lon: float
    rayon_axe: float        # rayon de l'axe de la chaussée annulaire (m)
    ecart_type: float       # qualité de l'ajustement (m)
    nb_points: int


def _cercle_moindres_carres(pts: list[tuple[float, float]]) -> Optional[tuple[float, float, float, float]]:
    """Ajustement algébrique d'un cercle (méthode de Kåsa) : retourne (xc, yc, r, écart-type)."""
    n = len(pts)
    if n < 5:
        return None
    mx = sum(p[0] for p in pts) / n
    my = sum(p[1] for p in pts) / n
    u = [(x - mx, y - my) for x, y in pts]
    suu = sum(a * a for a, _ in u)
    svv = sum(b * b for _, b in u)
    suv = sum(a * b for a, b in u)
    suuu = sum(a ** 3 for a, _ in u)
    svvv = sum(b ** 3 for _, b in u)
    suvv = sum(a * b * b for a, b in u)
    svuu = sum(b * a * a for a, b in u)
    det = suu * svv - suv * suv
    if abs(det) < 1e-9:
        return None
    b1 = 0.5 * (suuu + suvv)
    b2 = 0.5 * (svvv + svuu)
    uc = (b1 * svv - b2 * suv) / det
    vc = (suu * b2 - suv * b1) / det
    r = math.sqrt(uc * uc + vc * vc + (suu + svv) / n)
    xc, yc = uc + mx, vc + my
    res = [math.hypot(x - xc, y - yc) - r for x, y in pts]
    return xc, yc, r, math.sqrt(sum(e * e for e in res) / n)


def detecter_anneau(troncons: list[Troncon], lat0: float, lon0: float,
                    distance_max: float = 80.0) -> Optional[AnneauDetecte]:
    """Centre et rayon de l'anneau existant le plus proche du point (lat0, lon0)."""
    pts = []
    for t in troncons:
        if not t.anneau:
            continue
        loc = [vers_local(lat0, lon0, la, lo) for la, lo in t.points]
        if min(math.hypot(e, n) for e, n in loc) <= distance_max:
            pts.extend(loc)
    # supprime les doublons aux jonctions des tronçons
    uniques = []
    for p in pts:
        if all(math.hypot(p[0] - q[0], p[1] - q[1]) > 0.05 for q in uniques):
            uniques.append(p)
    res = _cercle_moindres_carres(uniques)
    if res is None:
        return None
    xc, yc, r, ecart = res
    if not 2.0 <= r <= 120.0 or ecart > max(2.0, 0.15 * r):
        return None
    from .projections import depuis_local
    lat, lon = depuis_local(lat0, lon0, xc, yc)
    return AnneauDetecte(lat, lon, r, ecart, len(uniques))


# ---------------------------------------------------------------------------
# Branches
# ---------------------------------------------------------------------------
@dataclass
class BrancheDetectee:
    azimut: float
    numero: str
    nom_voie: str
    nature: str
    importance: int
    gestionnaire: str = ""
    largeur: Optional[float] = None
    voies: Optional[int] = None
    sens_unique: bool = False
    chaussees: int = 1                 # 2 pour une branche à chaussées séparées (entrée et sortie distinctes)

    @property
    def nom(self) -> str:
        return nom_branche(self.numero, self.nom_voie, self.azimut)


def _intersections_cercle(loc: list[tuple[float, float]], r: float) -> list[tuple[float, float]]:
    out = []
    for (x1, y1), (x2, y2) in zip(loc, loc[1:]):
        dx, dy = x2 - x1, y2 - y1
        a = dx * dx + dy * dy
        if a == 0:
            continue
        b = 2 * (x1 * dx + y1 * dy)
        c = x1 * x1 + y1 * y1 - r * r
        disc = b * b - 4 * a * c
        if disc < 0:
            continue
        for s in (-1, 1):
            t = (-b + s * math.sqrt(disc)) / (2 * a)
            if 0 <= t <= 1:
                out.append((x1 + t * dx, y1 + t * dy))
    return out


def _distance_segment(px, py, x1, y1, x2, y2) -> float:
    dx, dy = x2 - x1, y2 - y1
    a = dx * dx + dy * dy
    t = 0.0 if a == 0 else max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / a))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def _distance_polyligne(loc, px=0.0, py=0.0) -> float:
    return min(_distance_segment(px, py, *a, *b) for a, b in zip(loc, loc[1:]))


def detecter_branches(troncons: list[Troncon], lat_c: float, lon_c: float,
                      rayon_axe: Optional[float] = None, ecart_fusion: float = 14.0) -> list[BrancheDetectee]:
    """Branches raccordées au carrefour, triées par azimut.

    Chaque tronçon qui atteint l'anneau (ou le centre, à défaut d'anneau) est coupé par un cercle
    situé au-delà des îlots ; le point de coupure donne l'azimut de la branche. Les coupures
    proches (chaussées séparées, tronçons découpés) sont fusionnées.
    """
    r_raccord = (rayon_axe + 6.0) if rayon_axe else 12.0
    r_coupe = (rayon_axe + 15.0) if rayon_axe else 25.0
    candidats: list[BrancheDetectee] = []
    for t in troncons:
        if t.anneau or t.nature in NATURES_NON_ROUTIERES:
            continue
        loc = [vers_local(lat_c, lon_c, la, lo) for la, lo in t.points]
        if _distance_polyligne(loc) > r_raccord:
            continue
        coupes = _intersections_cercle(loc, r_coupe)
        if not coupes:                    # tronçon court (arrêté par un carrefour voisin) : son point le plus éloigné
            loin = max(loc, key=lambda q: math.hypot(*q))
            if math.hypot(*loin) >= r_raccord + 3:
                coupes = [loin]
        for e, n in coupes:
            az = math.degrees(math.atan2(e, n)) % 360
            candidats.append(BrancheDetectee(az, t.numero, t.nom, t.nature, t.importance, t.gestionnaire,
                                             t.largeur, t.voies, t.sens_unique))
    candidats.sort(key=lambda b: (b.importance, b.azimut))
    retenues: list[BrancheDetectee] = []
    for b in candidats:
        if all(_ecart(b.azimut, r.azimut) > ecart_fusion for r in retenues):
            retenues.append(b)
    return sorted(_fusionner_chaussees(retenues), key=lambda b: b.azimut)


NATURES_NON_ROUTIERES = {"Sentier", "Escalier", "Piste cyclable", "Bac ou liaison maritime", "Bac auto",
                         "Bac piéton"}
ECART_CHAUSSEES = 40.0     # degrés : deux chaussées d'une même route vues depuis le centre


def _ecart(a: float, b: float) -> float:
    return abs((a - b + 180) % 360 - 180)


def _meme_route(a: BrancheDetectee, b: BrancheDetectee) -> bool:
    if (a.numero or a.nom_voie) and (a.numero, a.nom_voie) == (b.numero, b.nom_voie):
        return True
    return a.sens_unique and b.sens_unique and (not (a.numero or b.numero) or a.numero == b.numero)


def _fusionner_chaussees(branches: list[BrancheDetectee]) -> list[BrancheDetectee]:
    """Route à chaussées séparées : l'entrée et la sortie forment une seule branche de Girabase."""
    branches = list(branches)
    fusion = True
    while fusion:
        fusion = False
        paires = [(i, j) for i in range(len(branches)) for j in range(i + 1, len(branches))
                  if _meme_route(branches[i], branches[j])
                  and _ecart(branches[i].azimut, branches[j].azimut) <= ECART_CHAUSSEES]
        if paires:
            i, j = min(paires, key=lambda p: _ecart(branches[p[0]].azimut, branches[p[1]].azimut))
            a, b = branches[i], branches[j]
            x = math.sin(math.radians(a.azimut)) + math.sin(math.radians(b.azimut))
            y = math.cos(math.radians(a.azimut)) + math.cos(math.radians(b.azimut))
            garde = a if (a.importance, not a.numero) <= (b.importance, not b.numero) else b
            fusionnee = BrancheDetectee(math.degrees(math.atan2(x, y)) % 360, garde.numero or a.numero or b.numero,
                                        garde.nom_voie or a.nom_voie or b.nom_voie, garde.nature,
                                        min(a.importance, b.importance), garde.gestionnaire, garde.largeur,
                                        garde.voies, False, 2)
            branches = [c for k, c in enumerate(branches) if k not in (i, j)] + [fusionnee]
            fusion = True
    return branches


def route_proche(troncons: list[Troncon], lat: float, lon: float, distance_max: float = 20.0) -> Optional[Troncon]:
    """Tronçon le plus proche d'un point (pour nommer un axe tracé à la main)."""
    meilleur, d_min = None, distance_max
    for t in troncons:
        if t.anneau:
            continue
        loc = [vers_local(lat, lon, la, lo) for la, lo in t.points]
        d = _distance_polyligne(loc)
        if d < d_min or (meilleur is not None and abs(d - d_min) < 1.0 and t.importance < meilleur.importance):
            meilleur, d_min = t, min(d, d_min)
    return meilleur


# ---------------------------------------------------------------------------
# Carrefour plan (sans anneau) : nœud du réseau BD TOPO
# ---------------------------------------------------------------------------
@dataclass
class CarrefourDetecte:
    lat: float
    lon: float
    degre: int              # nombre d'extrémités de tronçons qui s'y rejoignent
    distance: float         # distance au point cliqué (m)


def detecter_carrefour(troncons: list[Troncon], lat0: float, lon0: float, distance_max: float = 40.0,
                       tolerance: float = 1.5) -> Optional[CarrefourDetecte]:
    """Nœud de degré ≥ 3 le plus proche du point cliqué (les tronçons BD TOPO sont coupés aux carrefours)."""
    extremites = []
    for t in troncons:
        if t.anneau or len(t.points) < 2:
            continue
        for la, lo in (t.points[0], t.points[-1]):
            e, n = vers_local(lat0, lon0, la, lo)
            if math.hypot(e, n) <= distance_max + tolerance:
                extremites.append((e, n))
    noeuds: list[list] = []                  # [somme e, somme n, nombre]
    for e, n in extremites:
        for nd in noeuds:
            if math.hypot(nd[0] / nd[2] - e, nd[1] / nd[2] - n) <= tolerance:
                nd[0] += e
                nd[1] += n
                nd[2] += 1
                break
        else:
            noeuds.append([e, n, 1])
    candidats = [(math.hypot(nd[0] / nd[2], nd[1] / nd[2]), nd) for nd in noeuds if nd[2] >= 3]
    candidats = [c for c in candidats if c[0] <= distance_max]
    if not candidats:
        return None
    d, nd = min(candidats, key=lambda c: (c[0] - 3.0 * c[1][2], c[0]))   # préfère les nœuds les plus raccordés
    from .projections import depuis_local
    lat, lon = depuis_local(lat0, lon0, nd[0] / nd[2], nd[1] / nd[2])
    return CarrefourDetecte(lat, lon, nd[2], d)


def estimer_anneau(rayon_axe: float, LA: float = 7.0, Bf: float = 2.0) -> tuple[float, float, float]:
    """Anneau (R, Bf, LA) d'un giratoire existant à partir du rayon de l'axe de sa chaussée annulaire.

    La BD TOPO décrit l'axe de l'anneau : le rayon extérieur est estimé à Rg = r_axe + LA / 2, à
    largeur d'anneau et bande franchissable données ; R est arrondi au demi-mètre. Pour un petit
    anneau (R < 1 m), on obtient un mini-giratoire : R = 0 et îlot franchissable de rayon Bf ≤ 3 m.
    """
    rg = rayon_axe + LA / 2
    R = round((rg - LA - Bf) * 2) / 2
    if R >= 1.0:
        return R, Bf, LA
    bf = max(0.0, min(3.0, round((rg - LA) * 2) / 2))
    return 0.0, bf, round((rg - bf) * 2) / 2
