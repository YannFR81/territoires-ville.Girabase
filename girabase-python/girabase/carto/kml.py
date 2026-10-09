"""Export KML (Google Earth, QGIS, Géoportail) de la conception schématique géoréférencée."""
from __future__ import annotations

import html
from pathlib import Path
from typing import Union

from .projections import point_azimut
from .site import SiteCarto

# Couleurs KML : aabbggrr — mêmes couleurs que le schéma
ORANGE, VERT, BLEU, LIE, BLANC = "ff0a59dd", "ff879d17", "ffc5995e", "ff41057f", "ffffffff"


def _style(ident: str, ligne: str, largeur: float, remplissage: str = "00000000") -> str:
    return (f'<Style id="{ident}"><LineStyle><color>{ligne}</color><width>{largeur}</width></LineStyle>'
            f'<PolyStyle><color>{remplissage}</color></PolyStyle></Style>')


def _coords(pts) -> str:
    return " ".join(f"{lon:.8f},{lat:.8f},0" for lat, lon in pts)


def _ligne(nom: str, style: str, pts, description: str = "") -> str:
    desc = f"<description><![CDATA[{description}]]></description>" if description else ""
    return (f"<Placemark><name>{html.escape(nom)}</name>{desc}<styleUrl>#{style}</styleUrl>"
            f"<LineString><tessellate>1</tessellate><altitudeMode>clampToGround</altitudeMode>"
            f"<coordinates>{_coords(pts)}</coordinates></LineString></Placemark>")


def _polygone(nom: str, style: str, pts, trou=None) -> str:
    interieur = (f"<innerBoundaryIs><LinearRing><coordinates>{_coords(trou)}</coordinates></LinearRing>"
                 f"</innerBoundaryIs>") if trou else ""
    return (f"<Placemark><name>{html.escape(nom)}</name><styleUrl>#{style}</styleUrl><Polygon>"
            f"<altitudeMode>clampToGround</altitudeMode><outerBoundaryIs><LinearRing>"
            f"<coordinates>{_coords(pts)}</coordinates></LinearRing></outerBoundaryIs>{interieur}</Polygon></Placemark>")


def _cercle(site: SiteCarto, r: float) -> list[tuple[float, float]]:
    return site.cercle(r)


def contenu_kml(site: SiteCarto) -> str:
    if not site.centre_defini:
        raise ValueError("Le centre du giratoire n'est pas défini.")
    nom = site.nom or site.nom_propose()
    leg = site.coordonnees_legales()
    coords = f"WGS84 : {site.lat:.7f} ; {site.lon:.7f}<br/>"
    if leg:
        coords += f"{leg.nom} : X = {leg.x:.2f} m, Y = {leg.y:.2f} m<br/>"
    if site.metropole:
        z, xc, yc = site.cc()
        coords += f"RGF93 CC{z} : X = {xc:.2f} m, Y = {yc:.2f} m<br/>"
    desc_centre = (f"<b>{html.escape(nom)}</b><br/>"
                   + (f"Commune : {html.escape(site.commune.nom)} ({site.commune.insee})<br/>" if site.commune.nom else "")
                   + coords.replace(".", ",")
                   + f"Anneau : R = {site.R:.2f} m, Bf = {site.Bf:.2f} m, LA = {site.LA:.2f} m, "
                   f"Rg = {site.Rg:.2f} m".replace(".", ",")
                   + f"<br/><small>{html.escape(site.mention())}</small>")
    parties = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>',
        f"<name>{html.escape(nom)}</name>",
        "<description><![CDATA[Conception schématique Girabase (portage Python) — à vérifier sur plan "
        "topographique.<br/>" + html.escape(site.mention())
        + "]]></description>",
        _style("anneau", BLANC, 3), _style("ilot", VERT, 2, "8045b060"), _style("bande", BLEU, 2, "40c5995e"),
        _style("axe", LIE, 3), _style("bord", ORANGE, 2.5), _style("ilot_sep", VERT, 2, "8045b060"),
        '<Style id="centre"><IconStyle><color>ff0a59dd</color><scale>1.1</scale><Icon>'
        "<href>https://maps.google.com/mapfiles/kml/shapes/placemark_circle.png</href></Icon></IconStyle></Style>",
        f"<Placemark><name>Centre</name><description><![CDATA[{desc_centre}]]></description>"
        f"<styleUrl>#centre</styleUrl><Point><coordinates>{site.lon:.8f},{site.lat:.8f},0</coordinates></Point>"
        "</Placemark>",
        "<Folder><name>Anneau</name>",
    ]
    if site.R > 0:
        parties.append(_polygone(f"Îlot central infranchissable (R = {site.R:.2f} m)".replace(".", ","), "ilot",
                                 _cercle(site, site.R)))
    if site.Bf > 0:
        parties.append(_polygone(f"Bande franchissable ({site.Bf:.2f} m)".replace(".", ","), "bande",
                                 _cercle(site, site.R + site.Bf), _cercle(site, site.R) if site.R > 0 else None))
    parties.append(_ligne(f"Bord extérieur (Rg = {site.Rg:.2f} m)".replace(".", ","), "anneau", _cercle(site, site.Rg)))
    parties.append("</Folder><Folder><name>Branches</name>")
    for k, (b, angle) in enumerate(site.ordre_girabase()):
        d = (f"Route : {html.escape(b.numero or '—')}<br/>Voie : {html.escape(b.nom_voie or '—')}<br/>"
             f"Azimut : {b.azimut:.1f}° ({b.orientation})<br/>Angle Girabase : {angle:.0f}°<br/>"
             f"Entrée {b.le4:.2f} m, îlot {b.li:.2f} m, sortie {b.ls:.2f} m").replace(".", ",")
        pts = [point_azimut(site.lat, site.lon, b.azimut, site.Rg),
               point_azimut(site.lat, site.lon, b.azimut, site.Rg + 40)]
        parties.append(_ligne(f"{k + 1}. {b.nom}", "axe", pts, d))
    parties.append("</Folder>")
    # Schéma des voies d'entrée, de sortie et des îlots séparateurs
    elements = site.schema_geo()
    if elements:
        parties.append("<Folder><name>Schéma des branches</name>")
        for calque, pts in elements:
            if calque == "GIRA_BORDS_BRANCHES":
                parties.append(_ligne("Bord de chaussée", "bord", pts))
            else:
                parties.append(_polygone("Îlot séparateur", "ilot_sep", pts + pts[:1]))
        parties.append("</Folder>")
    parties.append("</Document></kml>")
    return "\n".join(parties)


def exporter_kml(site: SiteCarto, chemin: Union[str, Path]) -> None:
    Path(chemin).write_text(contenu_kml(site), encoding="utf-8")
