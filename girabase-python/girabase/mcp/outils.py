"""Outils MCP de Girabase : définitions (schémas JSON) et traitements."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

from .. import __version__, gbs
from ..carto.conception import site_depuis_troncons
from ..carto.geoservices import (lire_commune, lire_recherche, lire_routes, url_commune, url_recherche,
                                 url_routes)
from ..carto.kml import exporter_kml
from ..carto.projections import CC, analyser_saisie, en_metropole, format_dms, systeme_legal, zone_cc
from ..carto.site import BrancheSite, SiteCarto
from ..echange import DonneesInvalides, calcul_complet, giratoire_depuis_dict, giratoire_vers_dict
from .reseau import ClientGeoplateforme

SCHEMA_GIRATOIRE = {
    "type": "object",
    "description": "Giratoire au format d'échange de Girabase (voir l'exemple de la description de l'outil).",
    "properties": {
        "nom": {"type": "string"},
        "localisation": {"type": "string"},
        "milieu": {"type": "string", "enum": ["rase_campagne", "periurbain", "centre_ville"],
                   "description": "Environnement : il détermine les coefficients du calcul."},
        "anneau": {"type": "object", "properties": {
            "R": {"type": "number", "description": "Rayon de l'îlot central infranchissable (m), 0 = mini-giratoire"},
            "Bf": {"type": "number", "description": "Largeur de la bande franchissable (m)"},
            "LA": {"type": "number", "description": "Largeur de l'anneau (m)"}}},
        "branches": {"type": "array", "minItems": 3, "maxItems": 8, "items": {"type": "object", "properties": {
            "nom": {"type": "string"},
            "angle": {"type": "number", "description": "Angle en degrés depuis la branche 1, dans le sens de "
                                                       "giration (inverse des aiguilles d'une montre)"},
            "le4": {"type": "number", "description": "Largeur d'entrée à 4 m (m), défaut 3,5 ; 0 = sortie seule"},
            "le15": {"type": "number", "description": "Largeur d'entrée à 15 m (m), si entrée évasée"},
            "li": {"type": "number", "description": "Largeur de l'îlot séparateur (m), défaut 3"},
            "ls": {"type": "number", "description": "Largeur de sortie (m), défaut 4 ; 0 = entrée seule"},
            "evasee": {"type": "boolean"}, "rampe": {"type": "boolean", "description": "Rampe > 3 % en entrée"},
            "tad": {"type": "boolean", "description": "Voie directe de tourne-à-droite"}},
            "required": ["nom", "angle"]}},
        "periodes": {"type": "array", "items": {"type": "object", "properties": {
            "nom": {"type": "string"},
            "trafics_uvp": {"type": "array", "items": {"type": "array", "items": {"type": ["number", "null"]}},
                            "description": "Matrice origine-destination en uvp/h : ligne = branche d'entrée, "
                                           "colonne = branche de sortie (diagonale = demi-tours)"},
            "trafics_vl": {"type": "array", "description": "Matrice VL (véhicules/h), à la place de trafics_uvp"},
            "trafics_pl": {"type": "array", "description": "Matrice PL (véhicules/h)"},
            "trafics_2r": {"type": "array", "description": "Matrice deux-roues (véhicules/h)"},
            "pietons": {"type": "array", "items": {"type": "number"},
                        "description": "Piétons/h traversant chaque branche"}}}}},
    "required": ["branches"],
}

POSITION = {"type": "string", "description": "Coordonnées du carrefour : DMS de Google Maps "
                                             "(43°48'58.1\"N 2°10'11.2\"E), degrés décimaux (43.8161, 2.1698), "
                                             "Lambert-93 ou CC (X Y en mètres), UTM outre-mer avec la zone ou "
                                             "le code EPSG en tête (UTM 40S 342177 7639537), ou une adresse."}

EXEMPLE = ('{"nom": "Giratoire D71 / D41", "milieu": "rase_campagne", "anneau": {"R": 5, "Bf": 2, "LA": 7}, '
           '"branches": [{"nom": "D71 Nord", "angle": 0}, {"nom": "D41 Ouest", "angle": 81}, '
           '{"nom": "D71 Sud", "angle": 186}, {"nom": "D41 Est", "angle": 270}], '
           '"periodes": [{"nom": "HPM", "trafics_uvp": [[0,120,300,80],[100,0,90,200],[280,60,0,70],[90,210,60,0]]}]}')

OUTILS: list[dict] = [
    {"name": "calculer_capacite", "title": "Calculer la capacité d'un giratoire (Girabase 4)",
     "description": "Calcule, pour chaque période de trafic, la capacité de chaque entrée, la réserve de capacité "
                    "(uvp/h et %), les files d'attente moyenne et maximale et les temps d'attente, avec le modèle "
                    "de GIRABASE 4 (CERTU/CEREMA) reproduit à l'identique, ainsi que les contrôles, "
                    "recommandations et conseils du logiciel. Donner soit « giratoire » (format JSON), soit "
                    "« fichier_gbs » (projet Girabase existant). Exemple de giratoire : " + EXEMPLE,
     "inputSchema": {"type": "object", "properties": {
         "giratoire": SCHEMA_GIRATOIRE,
         "fichier_gbs": {"type": "string", "description": "Chemin d'un projet Girabase .gbs"}}},
     "annotations": {"readOnlyHint": True, "openWorldHint": False}},
    {"name": "lire_projet_gbs", "title": "Lire un projet Girabase (.gbs)",
     "description": "Lit un projet Girabase (.gbs de Girabase 4 ou du portage Python) et le renvoie au format "
                    "JSON d'échange (géométrie, branches, périodes et matrices de trafic).",
     "inputSchema": {"type": "object", "properties": {"fichier": {"type": "string"}}, "required": ["fichier"]},
     "annotations": {"readOnlyHint": True, "openWorldHint": False}},
    {"name": "ecrire_projet_gbs", "title": "Enregistrer un projet Girabase (.gbs)",
     "description": "Écrit un giratoire (format JSON d'échange) dans un projet .gbs, qui s'ouvre dans Girabase "
                    "(portage Python et Girabase 4). Refuse d'écraser un fichier existant sauf si "
                    "« remplacer » vaut true.",
     "inputSchema": {"type": "object", "properties": {
         "fichier": {"type": "string", "description": "Chemin du .gbs à créer"},
         "giratoire": SCHEMA_GIRATOIRE, "remplacer": {"type": "boolean", "default": False}},
         "required": ["fichier", "giratoire"]},
     "annotations": {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": True, "openWorldHint": False}},
    {"name": "analyser_carrefour", "title": "Analyser un carrefour sur les données de l'IGN",
     "description": "À partir de coordonnées (ou d'une adresse), lit la BD TOPO de l'IGN : giratoire existant "
                    "(centre, rayon de l'anneau, R/Bf/LA proposés) ou carrefour plan, branches avec numéro de "
                    "route, nom de voie, azimut, orientation Nord/Est/Sud/Ouest et angle Girabase, commune, "
                    "coordonnées WGS84 / Lambert-93 / CC (ou UTM outre-mer). Renvoie aussi un « giratoire » prêt "
                    "pour calculer_capacite (ajouter les trafics). Nécessite Internet. Données IGN sous Licence "
                    "Ouverte Etalab 2.0 : reprendre la mention « sources » dans les documents produits.",
     "inputSchema": {"type": "object", "properties": {
         "position": POSITION,
         "milieu": {"type": "string", "enum": ["rase_campagne", "periurbain", "centre_ville"]},
         "LA": {"type": "number", "description": "Largeur d'anneau projetée (m), défaut 7"},
         "Bf": {"type": "number", "description": "Bande franchissable projetée (m), défaut 2"}},
         "required": ["position"]},
     "annotations": {"readOnlyHint": True, "openWorldHint": True}},
    {"name": "convertir_coordonnees", "title": "Convertir des coordonnées (WGS84, Lambert-93, CC, UTM)",
     "description": "Convertit une position donnée en DMS, degrés décimaux, Lambert-93, CC42 à CC50 ou UTM "
                    "outre-mer vers "
                    "WGS84 (décimal et DMS), RGF93 Lambert-93 et CC en métropole, ou le système légal UTM "
                    "outre-mer. Calcul local, sans Internet.",
     "inputSchema": {"type": "object", "properties": {"position": POSITION,
                                                      "zone_cc": {"type": "integer", "minimum": 42, "maximum": 50}},
                     "required": ["position"]},
     "annotations": {"readOnlyHint": True, "openWorldHint": False}},
    {"name": "rechercher_lieu", "title": "Rechercher une adresse ou un lieu (géocodage IGN)",
     "description": "Recherche une commune, une adresse ou un lieu-dit en France avec le géocodage de la "
                    "Géoplateforme de l'IGN. Nécessite Internet.",
     "inputSchema": {"type": "object", "properties": {"texte": {"type": "string"},
                                                      "limite": {"type": "integer", "minimum": 1, "maximum": 10}},
                     "required": ["texte"]},
     "annotations": {"readOnlyHint": True, "openWorldHint": True}},
    {"name": "exporter_kml", "title": "Exporter le schéma du giratoire en KML",
     "description": "Écrit un fichier KML (Google Earth, QGIS, Géoportail) : centre, îlot central, bande "
                    "franchissable, anneau, axes des branches, bords de chaussée et îlots séparateurs. Accepte "
                    "le « site » renvoyé par analyser_carrefour, éventuellement modifié.",
     "inputSchema": {"type": "object", "properties": {
         "fichier": {"type": "string"},
         "site": {"type": "object", "description": "{lat, lon, R, Bf, LA, nom, branches: [{nom, azimut}]}",
                  "properties": {"lat": {"type": "number"}, "lon": {"type": "number"},
                                 "R": {"type": "number"}, "Bf": {"type": "number"}, "LA": {"type": "number"},
                                 "nom": {"type": "string"},
                                 "branches": {"type": "array", "items": {"type": "object"}}},
                  "required": ["lat", "lon", "branches"]},
         "remplacer": {"type": "boolean", "default": False}},
         "required": ["fichier", "site"]},
     "annotations": {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": True, "openWorldHint": False}},
]

INSTRUCTIONS = (
    f"Girabase {__version__} — portage Python de GIRABASE 4 (CERTU/CEREMA, licence GPL v3) : capacité des "
    "carrefours giratoires. Démarche type : analyser_carrefour (position) → compléter le « giratoire » renvoyé "
    "avec le milieu et les trafics → calculer_capacite → ecrire_projet_gbs / exporter_kml. Les résultats "
    "reproduisent ceux de Girabase 4 ; la géométrie issue de la BD TOPO est une proposition à vérifier sur plan "
    "topographique. Citer la mention « sources » (IGN, Licence Ouverte Etalab 2.0) dans les documents produits.")


# ---------------------------------------------------------------------------
# Traitements
# ---------------------------------------------------------------------------
class ErreurOutil(ValueError):
    """Erreur présentée à l'IA (isError) avec un message utile."""


def _chemin(texte: str, extensions: tuple[str, ...]) -> Path:
    if not texte:
        raise ErreurOutil("Chemin de fichier manquant.")
    p = Path(texte).expanduser()
    if p.suffix.lower() not in extensions:
        raise ErreurOutil(f"Extension attendue : {' ou '.join(extensions)}.")
    return p


def _coordonnees(lat: float, lon: float, zone: Optional[int] = None) -> dict:
    d: dict[str, Any] = {"wgs84": {"lat": round(lat, 7), "lon": round(lon, 7), "dms": format_dms(lat, lon)}}
    leg = systeme_legal(lat, lon)
    if leg:
        d["systeme_legal"] = {"nom": leg.nom, "epsg": leg.epsg, "x": round(leg.x, 2), "y": round(leg.y, 2)}
    if en_metropole(lat, lon):
        z = zone or zone_cc(lat)
        x, y = CC[z].depuis_geo(lat, lon)
        d["cc"] = {"nom": f"RGF93 CC{z}", "epsg": 3900 + z, "x": round(x, 2), "y": round(y, 2)}
    return d


class Girabase:
    """Traitements des outils ; le client réseau est remplaçable (tests hors ligne)."""

    def __init__(self, client: Optional[ClientGeoplateforme] = None):
        self.client = client or ClientGeoplateforme()
        self.traitements: dict[str, Callable[[dict], dict]] = {
            "calculer_capacite": self.calculer_capacite, "lire_projet_gbs": self.lire_projet_gbs,
            "ecrire_projet_gbs": self.ecrire_projet_gbs, "analyser_carrefour": self.analyser_carrefour,
            "convertir_coordonnees": self.convertir_coordonnees, "rechercher_lieu": self.rechercher_lieu,
            "exporter_kml": self.exporter_kml}

    def appeler(self, nom: str, arguments: dict) -> dict:
        if nom not in self.traitements:
            raise ErreurOutil(f"Outil inconnu : {nom}")
        try:
            return self.traitements[nom](arguments or {})
        except DonneesInvalides as exc:
            raise ErreurOutil(str(exc)) from None
        except gbs.ErreurFichierGbs as exc:
            raise ErreurOutil(f"Projet .gbs illisible : {exc}") from None
        except FileNotFoundError as exc:
            raise ErreurOutil(f"Fichier introuvable : {exc.filename}") from None

    # -- calcul ------------------------------------------------------------
    def calculer_capacite(self, a: dict) -> dict:
        if a.get("fichier_gbs"):
            g = gbs.lire(_chemin(a["fichier_gbs"], (".gbs",)))
        elif a.get("giratoire"):
            g = giratoire_depuis_dict(a["giratoire"])
        else:
            raise ErreurOutil("Donner « giratoire » (format JSON) ou « fichier_gbs ».")
        if g.milieu is None:
            raise ErreurOutil("Préciser le milieu : rase_campagne, periurbain ou centre_ville.")
        return calcul_complet(g)

    def lire_projet_gbs(self, a: dict) -> dict:
        return giratoire_vers_dict(gbs.lire(_chemin(a.get("fichier", ""), (".gbs",))))

    def ecrire_projet_gbs(self, a: dict) -> dict:
        p = _chemin(a.get("fichier", ""), (".gbs",))
        if p.exists() and not a.get("remplacer"):
            raise ErreurOutil(f"{p} existe déjà : passer « remplacer »: true pour l'écraser.")
        g = giratoire_depuis_dict(a.get("giratoire") or {})
        p.parent.mkdir(parents=True, exist_ok=True)
        gbs.ecrire(g, p)
        return {"fichier": str(p.resolve()), "branches": g.n, "periodes": len(g.periodes),
                "message": "Projet enregistré ; il s'ouvre dans Girabase."}

    # -- coordonnées ---------------------------------------------------------
    def _position(self, texte: str) -> tuple[float, float, str]:
        if not texte or not str(texte).strip():
            raise ErreurOutil("Position manquante.")
        coord = analyser_saisie(str(texte))
        if coord:
            return coord
        lieux = lire_recherche(self.client.obtenir_json(url_recherche(str(texte), 1)))
        if not lieux:
            raise ErreurOutil(f"Lieu introuvable : « {texte} ».")
        return lieux[0].lat, lieux[0].lon, f"adresse : {lieux[0].libelle}"

    def convertir_coordonnees(self, a: dict) -> dict:
        coord = analyser_saisie(str(a.get("position", "")))
        if not coord:
            raise ErreurOutil("Format non reconnu : DMS (43°48'58.1\"N 2°10'11.2\"E), décimal (43.8161, 2.1698), "
                              "Lambert-93 ou CC (X Y en mètres), UTM outre-mer (UTM 40S X Y ou EPSG:2975 X Y).")
        lat, lon, systeme = coord
        z = a.get("zone_cc")
        if z is not None and int(z) not in CC:
            raise ErreurOutil("zone_cc : de 42 à 50.")
        return {"format_reconnu": systeme, **_coordonnees(lat, lon, int(z) if z else None)}

    def rechercher_lieu(self, a: dict) -> dict:
        lieux = lire_recherche(self.client.obtenir_json(url_recherche(str(a.get("texte", "")),
                                                                      int(a.get("limite") or 5))))
        return {"lieux": [{"libelle": l.libelle, "type": l.type, "commune": l.commune, "insee": l.insee,
                           **_coordonnees(l.lat, l.lon)} for l in lieux],
                "sources": "Géocodage de la Géoplateforme (IGN, BAN), Licence Ouverte Etalab 2.0"}

    # -- carte ---------------------------------------------------------------
    def analyser_carrefour(self, a: dict) -> dict:
        lat, lon, origine = self._position(a.get("position", ""))
        troncons = lire_routes(self.client.obtenir_json(url_routes(lat, lon, 150)))
        site, nature = site_depuis_troncons(troncons, lat, lon, float(a.get("LA", 7.0)), float(a.get("Bf", 2.0)))
        try:
            site.commune = lire_commune(self.client.obtenir_json(url_commune(site.lat, site.lon))) or site.commune
        except Exception:                        # commune facultative
            pass
        ordre = site.ordre_girabase()
        resultat: dict[str, Any] = {
            "position_donnee": {"lat": lat, "lon": lon, "format": origine},
            "nature": {"giratoire": "giratoire existant", "carrefour": "carrefour plan",
                       "aucun": "aucun carrefour de la BD TOPO à moins de 40 m"}[nature],
            "commune": {"nom": site.commune.nom, "insee": site.commune.insee} if site.commune.nom else None,
            "centre": _coordonnees(site.lat, site.lon),
            "branches": [{"numero": k + 1, "nom": b.nom, "route": b.numero, "voie": b.nom_voie,
                          "azimut_deg": round(b.azimut, 1), "orientation": b.orientation,
                          "angle_girabase_deg": round(angle, 1)} for k, (b, angle) in enumerate(ordre)],
            "sources": site.sources}
        if site.rayon_axe_bdtopo:
            resultat["anneau_existant"] = {
                "rayon_axe_m": site.rayon_axe_bdtopo,
                "Rg_estime_m": round(site.rayon_axe_bdtopo + site.LA / 2, 1),
                "remarque": "La BD TOPO décrit l'axe de l'anneau : Rg ≈ rayon de l'axe + LA/2, à vérifier."}
        resultat["anneau_propose"] = {"R": site.R, "Bf": site.Bf, "LA": site.LA, "Rg": site.Rg}
        if len(ordre) >= 3:
            g = site.vers_giratoire()
            if a.get("milieu"):
                from ..echange import _milieu
                g.milieu = _milieu(a["milieu"])
            d = giratoire_vers_dict(g)
            d["periodes"] = [{"nom": "HPM", "trafics_uvp": [[None] * g.n for _ in range(g.n)]}]
            resultat["giratoire"] = d
            resultat["etape_suivante"] = ("Renseigner « milieu » et les matrices de trafic, puis appeler "
                                          "calculer_capacite avec ce « giratoire ».")
        resultat["site"] = {"lat": site.lat, "lon": site.lon, "R": site.R, "Bf": site.Bf, "LA": site.LA,
                            "nom": site.nom_propose(), "sources": site.sources,
                            "branches": [{"nom": b.nom, "azimut": round(b.azimut, 2), "route": b.numero,
                                          "voie": b.nom_voie} for b, _ in ordre]}
        return resultat

    def exporter_kml(self, a: dict) -> dict:
        p = _chemin(a.get("fichier", ""), (".kml",))
        if p.exists() and not a.get("remplacer"):
            raise ErreurOutil(f"{p} existe déjà : passer « remplacer »: true pour l'écraser.")
        d = a.get("site") or {}
        try:
            site = SiteCarto(nom=str(d.get("nom", "")), lat=float(d["lat"]), lon=float(d["lon"]),
                             R=float(d.get("R", 6)), Bf=float(d.get("Bf", 2)), LA=float(d.get("LA", 7)),
                             sources=str(d.get("sources", "")))
            for b in d.get("branches") or []:
                site.branches.append(BrancheSite(str(b.get("nom") or "Branche"), float(b["azimut"]) % 360,
                                                 str(b.get("route", "")), str(b.get("voie", ""))))
        except (KeyError, TypeError, ValueError) as exc:
            raise ErreurOutil(f"« site » incomplet : {exc}. Attendu : lat, lon, branches [{{nom, azimut}}].") from None
        site.choisir_branche1_nord()
        p.parent.mkdir(parents=True, exist_ok=True)
        exporter_kml(site, p)
        return {"fichier": str(p.resolve()), "branches": len(site.branches),
                "message": "KML écrit (Google Earth, QGIS, Géoportail)."}
