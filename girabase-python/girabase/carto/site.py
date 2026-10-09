"""Site cartographique d'un giratoire : centre, branches orientées, anneau, et passage vers Girabase."""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional, Union

from ..geometrie import schema
from ..modele import Branche, Giratoire
from .analyse import CARDINAUX_8_LONG, angle_girabase, cardinal8, nom_branche
from .geoservices import Commune, mention_fond
from .projections import (CC, LAMBERT93, CoordonneesLegales, depuis_local, en_metropole, format_dms, point_azimut,
                          systeme_legal, zone_cc)


@dataclass
class BrancheSite:
    nom: str
    azimut: float                      # degrés, sens horaire depuis le Nord géographique
    numero: str = ""                   # D71…
    nom_voie: str = ""                 # Route vieille d'Albi…
    le4: float = 3.5                   # largeurs pour le schéma (valeurs par défaut de Girabase)
    li: float = 3.0
    ls: float = 4.0
    source: str = "tracé"              # « tracé » ou « BD TOPO »

    @property
    def orientation(self) -> str:
        return cardinal8(self.azimut)


@dataclass
class SiteCarto:
    nom: str = ""
    lat: Optional[float] = None
    lon: Optional[float] = None
    commune: Commune = field(default_factory=Commune)
    R: float = 6.0
    Bf: float = 2.0
    LA: float = 7.0
    branches: list[BrancheSite] = field(default_factory=list)
    branche1: int = 0                  # indice (dans branches) de la branche n° 1 de Girabase
    fond: str = "auto"
    opacite: float = 0.5
    cadastre: bool = False
    zoom: float = 19.0
    rayon_axe_bdtopo: Optional[float] = None
    sources: str = ""                  # mention de paternité des données IGN utilisées (Licence Ouverte 2.0)

    def mention(self) -> str:
        """Mention des sources exigée par la Licence Ouverte : celle de l'analyse BD TOPO, sinon le fond consulté."""
        return self.sources or mention_fond(self.fond)

    @property
    def Rg(self) -> float:
        return self.R + self.Bf + self.LA

    @property
    def centre_defini(self) -> bool:
        return self.lat is not None and self.lon is not None

    # -- coordonnées ------------------------------------------------------
    def lambert93(self) -> tuple[float, float]:
        return LAMBERT93.depuis_geo(self.lat, self.lon)

    def coordonnees_legales(self) -> Optional[CoordonneesLegales]:
        """Lambert-93 en métropole, UTM du territoire outre-mer, None hors de France."""
        return systeme_legal(self.lat, self.lon)

    @property
    def metropole(self) -> bool:
        return self.centre_defini and en_metropole(self.lat, self.lon)

    def cc(self, zone: Optional[int] = None) -> tuple[int, float, float]:
        z = zone or zone_cc(self.lat)
        x, y = CC[z].depuis_geo(self.lat, self.lon)
        return z, x, y

    # -- branches ---------------------------------------------------------
    def ajouter_branche(self, azimut: float, numero: str = "", nom_voie: str = "", source: str = "tracé") -> BrancheSite:
        b = BrancheSite(nom_branche(numero, nom_voie, azimut), azimut % 360, numero, nom_voie, source=source)
        if not numero and not nom_voie:
            b.nom = f"Branche {len(self.branches) + 1} {b.nom.split()[-1]}"
        self.branches.append(b)
        if len(self.branches) == 1:
            self.branche1 = 0
        return b

    def supprimer_branche(self, i: int) -> None:
        ref = self.branches[self.branche1] if self.branches else None
        del self.branches[i]
        if ref is not None and ref in self.branches:
            self.branche1 = self.branches.index(ref)
        else:
            self.choisir_branche1_nord()

    def distinguer_noms(self) -> None:
        """Deux branches au même nom (« D612 Nord » deux fois) : orientation précisée à 8 directions."""
        for b in self.branches:
            pareils = [x for x in self.branches if x.nom == b.nom]
            if len(pareils) > 1:
                for x in pareils:
                    base = x.numero or x.nom_voie or "Branche"
                    x.nom = f"{base} {CARDINAUX_8_LONG[int(((x.azimut % 360) + 22.5) // 45) % 8]}"
        for b in self.branches:                # toujours identiques : azimut en clair
            pareils = [x for x in self.branches if x.nom == b.nom]
            if len(pareils) > 1:
                for x in pareils:
                    x.nom = f"{x.nom} ({x.azimut:.0f}°)"

    def choisir_branche1_nord(self) -> None:
        """Branche n° 1 par défaut : la plus proche du Nord."""
        if self.branches:
            self.branche1 = min(range(len(self.branches)),
                                key=lambda i: min(self.branches[i].azimut, 360 - self.branches[i].azimut))

    def ordre_girabase(self) -> list[tuple[BrancheSite, float]]:
        """Branches dans l'ordre de Girabase (sens de giration depuis la branche 1) avec leur angle."""
        if not self.branches:
            return []
        az1 = self.branches[min(self.branche1, len(self.branches) - 1)].azimut
        paires = [(b, angle_girabase(az1, b.azimut)) for b in self.branches]
        return sorted(paires, key=lambda p: p[1])

    # -- vers Girabase ----------------------------------------------------
    def nom_propose(self) -> str:
        numeros = []
        for b, _ in self.ordre_girabase():
            if b.numero and b.numero not in numeros:
                numeros.append(b.numero)
        base = "Giratoire " + " / ".join(numeros) if numeros else "Giratoire"
        return base + (f" — {self.commune.nom}" if self.commune.nom else "")

    def texte_localisation(self) -> str:
        lignes = []
        if self.commune.nom:
            lignes.append(f"{self.commune.nom} ({self.commune.insee})")
        if self.centre_defini:
            lignes.append(f"{format_dms(self.lat, self.lon)} — WGS84 {self.lat:.6f}, {self.lon:.6f}")
            leg = self.coordonnees_legales()
            if leg and self.metropole:
                z, xc, yc = self.cc()
                lignes.append(f"Lambert-93 X={leg.x:.2f} Y={leg.y:.2f} — CC{z} X={xc:.2f} Y={yc:.2f}")
            elif leg:
                lignes.append(f"{leg.nom} X={leg.x:.2f} Y={leg.y:.2f}")
        branches = ", ".join(f"{b.nom} ({b.azimut:.0f}°)" for b, _ in self.ordre_girabase())
        if branches:
            lignes.append(f"Branches : {branches}")
        if self.centre_defini:
            lignes.append(self.mention())
        return "\n".join(lignes)

    def vers_giratoire(self, angles_entiers: bool = True) -> Giratoire:
        """Giratoire Girabase : branches ordonnées, angles depuis la branche 1, anneau saisi."""
        g = Giratoire(nom=self.nom or self.nom_propose(), localisation=self.texte_localisation(),
                      R=self.R, Bf=self.Bf, LA=self.LA)
        for b, angle in self.ordre_girabase():
            a = int(round(angle)) % 360 if angles_entiers else angle
            g.branches.append(Branche(nom=b.nom, angle=a, le4=b.le4, le15=b.le4, li=b.li, ls=b.ls))
        if angles_entiers:     # angles strictement croissants après arrondi
            for k in range(1, g.n):
                if g.branches[k].angle <= g.branches[k - 1].angle:
                    g.branches[k].angle = g.branches[k - 1].angle + 1
        if g.n:
            g.nouvelle_periode("HPM")
        return g

    # -- géométrie géoréférencée -------------------------------------------
    def cercle(self, r: float, n: int = 96) -> list[tuple[float, float]]:
        return [point_azimut(self.lat, self.lon, 360 * k / n, r) for k in range(n + 1)]

    def schema_geo(self) -> list[tuple[str, list[tuple[float, float]]]]:
        """Bords de chaussée et îlots séparateurs du schéma Girabase, en (lat, lon).

        Le schéma est calculé dans le repère de Girabase (branche 1 sur l'axe des X, angles dans le
        sens de giration), puis tourné pour que la branche 1 suive son azimut réel.
        """
        if not (self.centre_defini and self.branches):
            return []
        g = self.vers_giratoire(angles_entiers=False)
        theta = math.radians(90 - self.ordre_girabase()[0][0].azimut)
        c, s = math.cos(theta), math.sin(theta)
        out = []
        for p in schema(g):
            if p.calque in ("GIRA_BORDS_BRANCHES", "GIRA_ILOTS_SEPARATEURS"):
                pts = [depuis_local(self.lat, self.lon, x * c - y * s, x * s + y * c) for x, y in p.points]
                out.append((p.calque, pts))
        return out

    # -- fichier ----------------------------------------------------------
    def vers_dict(self) -> dict:
        d = asdict(self)
        d["format"] = "girabase-site/1"
        return d

    @classmethod
    def depuis_dict(cls, d: dict) -> "SiteCarto":
        d = dict(d)
        d.pop("format", None)
        commune = Commune(**(d.pop("commune", None) or {}))
        branches = [BrancheSite(**b) for b in d.pop("branches", [])]
        connus = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(commune=commune, branches=branches, **connus)

    def enregistrer(self, chemin: Union[str, Path]) -> None:
        Path(chemin).write_text(json.dumps(self.vers_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def ouvrir(cls, chemin: Union[str, Path]) -> "SiteCarto":
        return cls.depuis_dict(json.loads(Path(chemin).read_text(encoding="utf-8")))


_RE_WGS84 = __import__("re").compile(r"WGS84\s+(-?\d{1,2}\.\d+)\s*,\s*(-?\d{1,3}\.\d+)")


def site_depuis_texte(texte: str) -> Optional[SiteCarto]:
    """Site centré sur les coordonnées WGS84 écrites dans la localisation d'un projet (« WGS84 43.816, 2.169 »)."""
    m = _RE_WGS84.search(texte or "")
    if not m:
        return None
    return SiteCarto(lat=float(m.group(1)), lon=float(m.group(2)))
