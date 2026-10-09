"""Analyse du carrefour, site, export KML — sur des données réelles de la BD TOPO (IGN, Licence Ouverte).

tests/donnees/bdtopo_lombers_d71_d41.json : tronçons de route à moins de 120 m du giratoire D71 / D41 à
Lombers (Tarn), extraits du service WFS de la Géoplateforme le 09/10/2026.
"""
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from girabase.carto import analyse as A
from girabase.carto import geoservices as G
from girabase.carto.geoservices import Commune
from girabase.carto.kml import contenu_kml
from girabase.carto.projections import azimut, format_dms
from girabase.carto.site import SiteCarto
from girabase.conseils import erreurs

DONNEES = Path(__file__).resolve().parent / "donnees" / "bdtopo_lombers_d71_d41.json"
CLIC = (43.816139, 2.169778)          # coordonnées relevées sur Google Maps (capture fournie)


@pytest.fixture(scope="module")
def troncons():
    return G.lire_routes(json.loads(DONNEES.read_text(encoding="utf-8")))


def test_lecture_bdtopo(troncons):
    assert len(troncons) == 9
    numeros = {t.numero for t in troncons}
    assert {"D71", "D41"} <= numeros
    d71 = next(t for t in troncons if t.numero == "D71" and not t.anneau)
    assert d71.nom == "Route Vieille d'Albi" and d71.gestionnaire == "Tarn" and d71.insee == "81147"
    assert sum(t.anneau for t in troncons) == 4


def test_detection_anneau(troncons):
    an = A.detecter_anneau(troncons, *CLIC)
    assert an is not None
    assert format_dms(an.lat, an.lon) == "43°48'58.1\"N 2°10'11.2\"E"
    assert 9.5 < an.rayon_axe < 12.0 and an.ecart_type < 0.5


def test_detection_branches(troncons):
    an = A.detecter_anneau(troncons, *CLIC)
    br = A.detecter_branches(troncons, an.lat, an.lon, an.rayon_axe)
    assert [b.nom for b in br] == ["D41 Est", "D71 Sud", "D41 Ouest", "D71 Nord"]
    az = [b.azimut for b in br]
    for obtenu, attendu in zip(az, [72, 155, 261, 342]):          # lecture sur la photo aérienne
        assert abs(obtenu - attendu) < 6
    assert "Chemin" not in " ".join(b.nom_voie for b in br)        # chemin voisin non raccordé


def test_route_proche_pour_axe_trace(troncons):
    an = A.detecter_anneau(troncons, *CLIC)
    from girabase.carto.projections import point_azimut
    lat, lon = point_azimut(an.lat, an.lon, 160, 45)             # clic approximatif sur la D71 au sud
    t = A.route_proche(troncons, lat, lon)
    assert t is not None and t.numero == "D71"


def test_orientations():
    assert A.cardinal4(341.5) == "Nord" and A.cardinal4(71.7) == "Est" and A.cardinal4(260.9) == "Ouest"
    assert A.cardinal8(155.1) == "SE" and A.cardinal8(22.4) == "N" and A.cardinal8(22.6) == "NE"
    assert A.angle_girabase(341.5, 260.9) == pytest.approx(80.6)     # sens inverse des aiguilles d'une montre


@pytest.fixture
def site(troncons):
    an = A.detecter_anneau(troncons, *CLIC)
    s = SiteCarto(lat=an.lat, lon=an.lon, commune=Commune("Lombers", "81147", "81120", "81"), R=4, Bf=2, LA=7)
    for b in A.detecter_branches(troncons, an.lat, an.lon, an.rayon_axe):
        s.ajouter_branche(b.azimut, b.numero, b.nom_voie, "BD TOPO")
    s.choisir_branche1_nord()
    return s


def test_ordre_et_angles_girabase(site):
    ordre = site.ordre_girabase()
    assert [b.nom for b, _ in ordre] == ["D71 Nord", "D41 Ouest", "D71 Sud", "D41 Est"]
    angles = [a for _, a in ordre]
    assert angles[0] == 0 and all(a < b for a, b in zip(angles, angles[1:]))
    assert angles[1] == pytest.approx(80.6, abs=0.5)


def test_vers_giratoire(site):
    g = site.vers_giratoire()
    assert g.nom == "Giratoire D71 / D41 — Lombers"
    assert [b.nom for b in g.branches] == ["D71 Nord", "D41 Ouest", "D71 Sud", "D41 Est"]
    assert [b.angle for b in g.branches] == [0, 81, 186, 270]
    assert "Lombers (81147)" in g.localisation and "Lambert-93" in g.localisation
    g.milieu = __import__("girabase.constantes", fromlist=["Milieu"]).Milieu.RASE_CAMPAGNE
    g.periodes[0].completer_par_zero(g.branches)
    assert erreurs(g) == []


def test_enregistrement_site(site, tmp_path):
    chemin = tmp_path / "site.json"
    site.enregistrer(chemin)
    s2 = SiteCarto.ouvrir(chemin)
    assert s2.vers_dict() == site.vers_dict()


def test_export_kml(site):
    texte = contenu_kml(site)
    racine = ET.fromstring(texte.encode("utf-8"))
    ns = {"k": "http://www.opengis.net/kml/2.2"}
    noms = [n.text for n in racine.iter("{http://www.opengis.net/kml/2.2}name")]
    assert "1. D71 Nord" in noms and "4. D41 Est" in noms and "Centre" in noms
    # L'axe de la branche D41 Est part bien vers l'est-nord-est
    pm = next(p for p in racine.iterfind(".//k:Placemark", ns) if p.find("k:name", ns).text == "4. D41 Est")
    (lon1, lat1, _), (lon2, lat2, _) = [tuple(map(float, c.split(","))) for c in
                                        pm.find(".//k:coordinates", ns).text.split()]
    assert azimut(site.lat, site.lon, lat2, lon2) == pytest.approx(site.branches[0].azimut, abs=0.01)
    # Schéma des voies : bords de chaussée et îlots séparateurs géoréférencés
    assert noms.count("Bord de chaussée") == 8 and noms.count("Îlot séparateur") == 4


# --- Carrefours plans (sans anneau) : extraits BD TOPO réels à Réalmont (Tarn), 09/10/2026 ------------
def _routes(nom):
    return G.lire_routes(json.loads((DONNEES.parent / f"bdtopo_{nom}.json").read_text(encoding="utf-8")))


def test_carrefour_plan_en_ville():
    tr = _routes("realmont_d612_d86")
    c = A.detecter_carrefour(tr, 43.77535, 2.18812)                 # clic à une douzaine de mètres
    assert c is not None and c.degre == 4
    assert format_dms(c.lat, c.lon) == "43°46'30.9\"N 2°11'16.9\"E"
    assert A.detecter_anneau(tr, c.lat, c.lon, 60) is None
    br = A.detecter_branches(tr, c.lat, c.lon, None)
    assert [b.numero for b in br] == ["", "D86", "D612", "D612"]
    assert [round(b.azimut) for b in br] == [47, 139, 228, 325]


def test_carrefour_en_t_en_campagne():
    tr = _routes("realmont_d612_d141")
    c = A.detecter_carrefour(tr, 43.76120, 2.17490)
    assert c is not None and c.degre == 3
    br = A.detecter_branches(tr, c.lat, c.lon, None)
    assert [b.nom for b in br] == ["D612 Nord", "D612 Sud", "D141 Nord"]
    s = SiteCarto(lat=c.lat, lon=c.lon)
    for b in br:
        s.ajouter_branche(b.azimut, b.numero, b.nom_voie, "BD TOPO")
    s.distinguer_noms()
    s.choisir_branche1_nord()
    # branche n° 1 : la plus proche du Nord (D141 à 330°, contre 31° pour la D612)
    assert [b.nom for b, _ in s.ordre_girabase()] == ["D141 Nord", "D612 Sud", "D612 Nord"]
    assert [round(a) for _, a in s.ordre_girabase()] == [0, 122, 298]
    assert A.detecter_carrefour(tr, 43.7650, 2.1800) is None        # loin de tout carrefour


def test_noms_distingues():
    s = SiteCarto(lat=44.0, lon=2.0)
    for az in (10, 340, 180):
        s.ajouter_branche(az, "D612")
    s.distinguer_noms()
    assert sorted(b.nom for b in s.branches) == ["D612 Nord (10°)", "D612 Nord (340°)", "D612 Sud"]
    s.branches[0].azimut, s.branches[0].nom = 40, "D612 Nord"
    s.branches[1].nom = "D612 Nord"
    s.distinguer_noms()
    assert sorted(b.nom for b in s.branches) == ["D612 Nord", "D612 Nord-Est", "D612 Sud"]


def test_estimation_anneau():
    assert A.estimer_anneau(10.73) == (5.0, 2.0, 7.0)                 # Lombers : Rg ≈ 14,2 m
    assert A.estimer_anneau(20.0, LA=8.0) == (14.0, 2.0, 8.0)
    R, Bf, LA = A.estimer_anneau(5.5)                                  # petit anneau : mini-giratoire
    assert R == 0 and R + Bf + LA == pytest.approx(9.0, abs=0.5)


def test_fonds_automatiques():
    from girabase.carto.geoservices import ROUTES, SEUIL_PHOTO, fond_effectif, url_tuile
    assert fond_effectif("auto", 6) == "plan" and fond_effectif("auto", SEUIL_PHOTO) == "ortho"
    assert fond_effectif("auto_osm", 12) == "osm" and fond_effectif("plan", 19) == "plan"
    assert "LAYER=TRANSPORTNETWORKS.ROADS" in url_tuile(ROUTES, 1, 2, 17)


def test_outre_mer_chaussees_separees():
    """Saint-Pierre (La Réunion) : quatre branches à chaussées séparées, coordonnées RGR92 / UTM 40S."""
    tr = _routes("saint_pierre_reunion")
    an = A.detecter_anneau(tr, -21.33133, 55.47210)
    assert an is not None and 9 < an.rayon_axe < 10
    br = A.detecter_branches(tr, an.lat, an.lon, an.rayon_axe)
    assert [b.nom for b in br] == ["Rue Luc Lorion Nord", "Rue Joseph Hubert Est", "Rue Luc Lorion Sud",
                                   "Allée de la Piscine Ouest"]
    assert all(b.chaussees == 2 for b in br)                      # entrée et sortie fusionnées
    s = SiteCarto(lat=an.lat, lon=an.lon)
    leg = s.coordonnees_legales()
    assert leg.nom == "RGR92 / UTM 40S" and not s.metropole
    assert round(leg.x) == 341546 and round(leg.y) == 7640409
    assert "RGR92 / UTM 40S" in contenu_kml(s) and "CC" not in s.texte_localisation()
