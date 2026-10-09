"""Conversions de coordonnées, vérifiées contre PROJ (pyproj, dépendance de test facultative)."""
import math

import pytest

from girabase.carto import projections as P

LOMBERS = (43.816139, 2.169778)          # carrefour D71 / D41 (exemple fourni)
POINTS = [LOMBERS, (43.9289, 2.1464), (46.5, 3.0), (42.5, 3.1), (50.9, 2.4), (44.2, -1.2), (48.85, 7.7)]


def test_point_origine_lambert93():
    x, y = P.LAMBERT93.depuis_geo(46.5, 3.0)
    assert (x, y) == pytest.approx((700000.0, 6600000.0), abs=1e-6)


@pytest.mark.parametrize("lat,lon", POINTS)
def test_aller_retour(lat, lon):
    for proj in [P.LAMBERT93, P.CC[P.zone_cc(lat)]]:
        x, y = proj.depuis_geo(lat, lon)
        la, lo = proj.vers_geo(x, y)
        assert (la, lo) == pytest.approx((lat, lon), abs=1e-10)


@pytest.mark.parametrize("lat,lon", POINTS)
def test_conforme_a_proj(lat, lon):
    pyproj = pytest.importorskip("pyproj")
    for proj in [P.LAMBERT93] + [P.CC[k] for k in range(42, 51)]:
        t = pyproj.Transformer.from_crs(4171, proj.epsg, always_xy=True)       # RGF93 géographique
        x_ref, y_ref = t.transform(lon, lat)
        x, y = proj.depuis_geo(lat, lon)
        assert (x, y) == pytest.approx((x_ref, y_ref), abs=1e-3), proj.nom   # au millimètre


def test_zone_cc_tarn():
    assert P.zone_cc(LOMBERS[0]) == 44
    assert P.zone_cc(43.4) == 43 and P.zone_cc(41.0) == 42 and P.zone_cc(51.2) == 50


def test_plan_local_et_azimut():
    lat0, lon0 = LOMBERS
    lat, lon = P.point_azimut(lat0, lon0, 60.0, 100.0)
    assert P.azimut(lat0, lon0, lat, lon) == pytest.approx(60.0, abs=1e-6)
    e, n = P.vers_local(lat0, lon0, lat, lon)
    assert math.hypot(e, n) == pytest.approx(100.0, abs=1e-6)
    pyproj = pytest.importorskip("pyproj")
    az, _, dist = pyproj.Geod(ellps="GRS80").inv(lon0, lat0, lon, lat)
    assert dist == pytest.approx(100.0, abs=2e-3) and az % 360 == pytest.approx(60.0, abs=1e-3)


def test_mercator_et_tuiles():
    x, y = P.vers_mercator(*LOMBERS)
    assert P.depuis_mercator(x, y) == pytest.approx(LOMBERS, abs=1e-12)
    n = 2 ** 19                                   # formule des tuiles OSM / WMTS « PM »
    attendu = (int((LOMBERS[1] + 180) / 360 * n),
               int((1 - math.asinh(math.tan(math.radians(LOMBERS[0]))) / math.pi) / 2 * n))
    assert P.tuile_de(x, y, 19) == attendu == (265303, 191013)
    cx, cy = P.coin_tuile(*attendu, 19)
    assert cx <= x < cx + P.taille_tuile(19) and cy - P.taille_tuile(19) < y <= cy


def test_format_dms_google():
    assert P.format_dms(*LOMBERS) == "43°48'58.1\"N 2°10'11.2\"E"


@pytest.mark.parametrize("texte,systeme", [
    ("43°48'58.1\"N 2°10'11.2\"E", "WGS84 (DMS)"),
    ("43° 48' 58.1'' N, 2° 10' 11.2'' E", "WGS84 (DMS)"),
    ("43.816139, 2.169778", "WGS84 (degrés décimaux)"),
    ("43,816139 2,169778", "WGS84 (degrés décimaux)"),
])
def test_saisie_geographique(texte, systeme):
    lat, lon, sys = P.analyser_saisie(texte)
    assert sys == systeme
    assert (lat, lon) == pytest.approx(LOMBERS, abs=2e-5)


def test_saisie_projetee():
    x, y = P.LAMBERT93.depuis_geo(*LOMBERS)
    lat, lon, sys = P.analyser_saisie(f"{x:.2f} {y:.2f}")
    assert sys == "Lambert-93" and (lat, lon) == pytest.approx(LOMBERS, abs=1e-6)   # saisie au cm
    x, y = P.CC[44].depuis_geo(*LOMBERS)
    lat, lon, sys = P.analyser_saisie(f"X={x:.2f} Y={y:.2f}")
    assert sys == "CC44" and (lat, lon) == pytest.approx(LOMBERS, abs=1e-6)
    assert P.analyser_saisie("Lombers Tarn") is None


# --- Outre-mer : UTM des systèmes légaux (valeurs de référence PROJ / pyproj 3.8) ---------------------
OUTRE_MER = [
    ("Saint-Denis (La Réunion)", -20.8789, 55.4481, 2975, 338568.315, 7690475.437),
    ("Pointe-à-Pitre", 16.2411, -61.5331, 5490, 656770.897, 1796166.176),
    ("Fort-de-France", 14.6161, -61.0588, 5490, 709096.316, 1616759.733),
    ("Cayenne", 4.9372, -52.3260, 2972, 352980.205, 545868.922),
    ("Saint-Laurent-du-Maroni", 5.4986, -54.0306, 2972, 164156.733, 608630.905),
    ("Mamoudzou", -12.7806, 45.2279, 4471, 524735.375, 8587115.812),
    ("Saint-Pierre", 46.7811, -56.1764, 4467, 562869.803, 5181168.316),
]


@pytest.mark.parametrize("nom,lat,lon,epsg,x,y", OUTRE_MER)
def test_utm_outre_mer(nom, lat, lon, epsg, x, y):
    from girabase.carto.projections import TERRITOIRES, systeme_legal
    c = systeme_legal(lat, lon)
    assert c.epsg == epsg
    assert c.x == pytest.approx(x, abs=0.002) and c.y == pytest.approx(y, abs=0.002)
    proj = next(p for *_, p in TERRITOIRES if p.epsg == epsg)
    la, lo = proj.vers_geo(c.x, c.y)
    assert la == pytest.approx(lat, abs=1e-9) and lo == pytest.approx(lon, abs=1e-9)


def test_systeme_legal_metropole_et_hors_france():
    from girabase.carto.projections import en_metropole, systeme_legal
    c = systeme_legal(43.816139, 2.169778)
    assert c.nom == "RGF93 Lambert-93" and round(c.x, 1) == 633197.5
    assert en_metropole(41.92, 8.74)                      # Ajaccio
    assert systeme_legal(40.42, -3.70) is None              # Madrid
    assert systeme_legal(51.51, -0.13) is None              # Londres
    assert systeme_legal(41.90, 12.50) is None              # Rome


def test_saisie_utm_outre_mer():
    from girabase.carto.projections import analyser_saisie, systeme_legal
    c = systeme_legal(-21.3393, 55.4781)
    for texte in (f"UTM 40S {c.x:.2f} {c.y:.2f}", f"EPSG:2975 {c.x:.2f}, {c.y:.2f}", f"utm40s {c.x:.0f} {c.y:.0f}"):
        lat, lon, nom = analyser_saisie(texte)
        assert abs(lat + 21.3393) < 1e-5 and abs(lon - 55.4781) < 1e-5 and nom == "RGR92 / UTM 40S"
    assert analyser_saisie("EPSG:9999 340000 7640000") is None
    assert analyser_saisie("UTM 40S 12") is None
