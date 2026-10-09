"""Conception automatique à partir de la BD TOPO : du point cliqué au giratoire (centre, anneau, branches).

Partagé par la fenêtre de localisation et le serveur MCP.
"""
from __future__ import annotations

from typing import Optional

from ..constantes import NB_BRANCHES_MAX
from . import analyse as A
from .geoservices import Troncon, mention_sources
from .site import SiteCarto


def site_depuis_troncons(troncons: list[Troncon], lat: float, lon: float, LA: float = 7.0, Bf: float = 2.0,
                         site: Optional[SiteCarto] = None) -> tuple[SiteCarto, str]:
    """Giratoire existant (anneau BD TOPO) ou carrefour plan (nœud du réseau) le plus proche du point.

    Retourne le site et sa nature : « giratoire », « carrefour » ou « aucun » (centre laissé au point cliqué).
    """
    s = site or SiteCarto()
    s.LA, s.Bf = LA, Bf
    an = A.detecter_anneau(troncons, lat, lon, 60)
    car = None if an else A.detecter_carrefour(troncons, lat, lon, 40)
    if an:
        s.lat, s.lon = an.lat, an.lon
        s.rayon_axe_bdtopo = round(an.rayon_axe, 2)
        s.R, s.Bf, s.LA = A.estimer_anneau(an.rayon_axe, s.LA, s.Bf)
        nature = "giratoire"
    elif car:
        s.lat, s.lon = car.lat, car.lon
        nature = "carrefour"
    else:
        s.lat, s.lon = lat, lon
        return s, "aucun"
    s.sources = mention_sources(troncons)
    for b in A.detecter_branches(troncons, s.lat, s.lon, s.rayon_axe_bdtopo)[:NB_BRANCHES_MAX]:
        s.ajouter_branche(b.azimut, b.numero, b.nom_voie, "BD TOPO")
    s.distinguer_noms()
    s.choisir_branche1_nord()
    if nature == "carrefour" and len(s.branches) >= 6:
        s.R = 9.0                                  # valeur par défaut de Girabase à partir de 6 branches
    return s, nature
