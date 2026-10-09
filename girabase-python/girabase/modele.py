"""Modèle de données d'un projet Girabase : giratoire, branches, périodes de trafic.

Les branches sont indexées à partir de 0 (la branche n° 1 de Girabase est l'indice 0).
Les branches sont numérotées dans le sens de giration (sens trigonométrique,
circulation à droite) et la branche 1 a toujours un angle nul.

Une valeur de trafic ``None`` correspond à une case non saisie ("VIDE" dans Girabase).
"""
from __future__ import annotations

import copy
import datetime as _dt
import math
from dataclasses import dataclass, field
from typing import Optional

from .constantes import (COEF_2R, COEF_PL, LI_DEFAUT, QP_DEFAUT, Milieu, UniteAngle)

Matrice = list[list[Optional[int]]]

COULEURS_PERIODES = ["#1f6fd1", "#d1491f", "#2e9e4f", "#8e44ad", "#c99a06", "#16a3a3", "#b03a6b", "#555555"]


def _matrice_vide(n: int) -> Matrice:
    return [[None] * n for _ in range(n)]


def uvp_cellule(vl: Optional[int], pl: Optional[int], dr: Optional[int]) -> Optional[int]:
    """Conversion VL/PL/2R -> uvp d'une case, comme TRAFIC.setQ.

    Girabase cumule les modes un à un en tronquant la part deux-roues
    (Int(2R x 0,5)) ; une case dont aucun mode n'est saisi reste vide.
    """
    if vl is None and pl is None and dr is None:
        return None
    total = 0
    if vl is not None:
        total += vl
    if pl is not None:
        total += int(pl * COEF_PL)
    if dr is not None:
        total += math.floor(dr * COEF_2R)
    return total


@dataclass
class Branche:
    nom: str
    angle: int = 0                 # dans l'unité du giratoire, entier comme dans Girabase
    rampe: bool = False            # rampe > 3 % en entrée
    tad: bool = False              # voie directe de tourne-à-droite
    evasee: bool = False           # entrée évasée
    le4: float = 3.5               # largeur d'entrée à 4 m (m) — valeurs par défaut de Girabase
    le15: float = 3.5              # largeur d'entrée à 15 m (m)
    li: float = LI_DEFAUT          # largeur d'îlot séparateur (m)
    ls: float = 4.0                # largeur de sortie (m)

    @property
    def entree_nulle(self) -> bool:
        return self.le4 == 0

    @property
    def sortie_nulle(self) -> bool:
        return self.ls == 0

    @property
    def largeur_entree(self) -> float:
        """LE retenue (NOTE DE CALCUL §1.2) : moyenne 4 m / 15 m si l'entrée est évasée."""
        return (self.le4 + self.le15) / 2 if self.evasee else self.le4


@dataclass
class Periode:
    nom: str
    nb_branches: int
    mode_uvp: bool = True
    couleur: str = COULEURS_PERIODES[0]
    pietons: list[Optional[int]] = field(default_factory=list)
    uvp: Matrice = field(default_factory=list)
    vl: Matrice = field(default_factory=list)
    pl: Matrice = field(default_factory=list)
    dr: Matrice = field(default_factory=list)       # deux-roues
    branche_saturee: Optional[int] = None           # période fictive issue de "Saturer la branche"
    periode_origine: Optional[str] = None

    def __post_init__(self) -> None:
        n = self.nb_branches
        if not self.pietons:
            self.pietons = [QP_DEFAUT] * n
        for nom in ("uvp", "vl", "pl", "dr"):
            if not getattr(self, nom):
                setattr(self, nom, _matrice_vide(n))

    # -- accès ----------------------------------------------------------------
    def matrice_uvp(self) -> Matrice:
        """Matrice en uvp/h (calculée depuis VL/PL/2R si la saisie est par mode)."""
        if self.mode_uvp:
            return [row[:] for row in self.uvp]
        n = self.nb_branches
        return [[uvp_cellule(self.vl[i][j], self.pl[i][j], self.dr[i][j]) for j in range(n)]
                for i in range(n)]

    def matrices_saisie(self) -> dict[str, Matrice]:
        if self.mode_uvp:
            return {"uvp": self.uvp}
        return {"vl": self.vl, "pl": self.pl, "dr": self.dr}

    def est_complete(self, branches: list[Branche]) -> bool:
        """Toutes les cases utiles saisies (TRAFIC.EstComplète), demi-tours compris."""
        for mat in self.matrices_saisie().values():
            for i, row in enumerate(mat):
                for j, v in enumerate(row):
                    if v is None and not (branches[i].entree_nulle or branches[j].sortie_nulle):
                        return False
        return True

    def cases_vides(self, branches: list[Branche]) -> int:
        nb = 0
        for mat in self.matrices_saisie().values():
            for i, row in enumerate(mat):
                for j, v in enumerate(row):
                    if v is None and not (branches[i].entree_nulle or branches[j].sortie_nulle):
                        nb += 1
        return nb

    def completer_par_zero(self, branches: list[Branche]) -> None:
        for mat in self.matrices_saisie().values():
            for i, row in enumerate(mat):
                for j, v in enumerate(row):
                    if v is None and not (branches[i].entree_nulle or branches[j].sortie_nulle):
                        row[j] = 0
        for i, v in enumerate(self.pietons):
            if v is None:
                self.pietons[i] = 0

    def total_entrant(self, i: int) -> int:
        return sum(v or 0 for v in self.matrice_uvp()[i])

    def total_sortant(self, j: int) -> int:
        return sum((row[j] or 0) for row in self.matrice_uvp())

    def total(self) -> int:
        return sum(v or 0 for row in self.matrice_uvp() for v in row)

    def basculer_mode(self) -> None:
        """Passage UVP <-> VL/PL/2R (les matrices véhicules sont réinitialisées, comme Girabase)."""
        n = self.nb_branches
        if self.mode_uvp:
            self.vl, self.pl, self.dr = _matrice_vide(n), _matrice_vide(n), _matrice_vide(n)
        else:
            self.uvp = _matrice_vide(n)
        self.mode_uvp = not self.mode_uvp

    def copie(self, nom: str) -> "Periode":
        p = copy.deepcopy(self)
        p.nom = nom
        p.branche_saturee = None
        p.periode_origine = None
        return p

    # -- gestion du nombre de branches ----------------------------------------
    def inserer_branche(self, index: int) -> None:
        self.nb_branches += 1
        self.pietons.insert(index, QP_DEFAUT)
        for mat in (self.uvp, self.vl, self.pl, self.dr):
            for row in mat:
                row.insert(index, None)
            mat.insert(index, [None] * self.nb_branches)

    def supprimer_branche(self, index: int) -> None:
        self.nb_branches -= 1
        del self.pietons[index]
        for mat in (self.uvp, self.vl, self.pl, self.dr):
            del mat[index]
            for row in mat:
                del row[index]


@dataclass
class Giratoire:
    nom: str = "Nouveau giratoire"
    localisation: str = ""
    variante: str = "Variante 1"
    date_modif: _dt.date = field(default_factory=_dt.date.today)
    milieu: Optional[Milieu] = None
    unite_angle: UniteAngle = UniteAngle.DEGRE
    R: float = 6.0           # rayon de l'îlot central infranchissable (m), 0 = mini-giratoire
    Bf: float = 2.0          # largeur de la bande franchissable (m)
    LA: float = 7.0          # largeur de l'anneau (m)
    branches: list[Branche] = field(default_factory=list)
    periodes: list[Periode] = field(default_factory=list)

    @property
    def n(self) -> int:
        return len(self.branches)

    @property
    def Rg(self) -> float:
        """Rayon extérieur."""
        return self.R + self.Bf + self.LA

    @property
    def mini_giratoire(self) -> bool:
        return self.R == 0

    def suivante(self, i: int) -> int:
        return (i + 1) % self.n

    def precedente(self, i: int) -> int:
        return (i - 1) % self.n

    def angle_rad(self, i: int) -> float:
        return self.branches[i].angle * math.pi / self.unite_angle.demi_tour

    def periodes_reelles(self) -> list[Periode]:
        return [p for p in self.periodes if p.branche_saturee is None]

    def nom_periode_libre(self, base: str = "Période") -> str:
        noms = {p.nom for p in self.periodes}
        k = len(self.periodes) + 1
        while f"{base} {k}" in noms:
            k += 1
        return f"{base} {k}"

    def nouvelle_periode(self, nom: Optional[str] = None, mode_uvp: bool = True) -> Periode:
        nom = nom or self.nom_periode_libre()
        couleur = COULEURS_PERIODES[len(self.periodes) % len(COULEURS_PERIODES)]
        p = Periode(nom=nom, nb_branches=self.n, mode_uvp=mode_uvp, couleur=couleur)
        self.periodes.append(p)
        return p

    def changer_unite_angle(self) -> None:
        """Bascule degrés <-> grades (GIRATOIRE.ChangeUnitéAngle)."""
        coef = 10 / 9 if self.unite_angle is UniteAngle.DEGRE else 0.9
        for b in self.branches:
            b.angle = round(b.angle * coef)       # affectation à un Integer VB : arrondi bancaire
        self.unite_angle = UniteAngle.GRADE if self.unite_angle is UniteAngle.DEGRE else UniteAngle.DEGRE

    def ajouter_branche(self, nom: Optional[str] = None) -> Branche:
        """Ajoute une branche à la fin, placée au milieu du plus grand écart angulaire libre."""
        tour = 2 * self.unite_angle.demi_tour
        nom = nom or self._nom_branche_libre()
        if not self.branches:
            b = Branche(nom=nom, angle=0)
            self.branches.append(b)
            for p in self.periodes:
                p.inserer_branche(0)
            return b
        angles = [b.angle for b in self.branches]
        dernier = angles[-1]
        angle = round((dernier + tour) / 2)
        if angle <= dernier or angle >= tour:
            angle = min(dernier + 1, tour - 1)
        b = Branche(nom=nom, angle=angle)
        self.branches.append(b)
        for p in self.periodes:
            p.inserer_branche(self.n - 1)
        return b

    def supprimer_branche(self, index: int) -> None:
        del self.branches[index]
        for p in self.periodes:
            p.supprimer_branche(index)
        if self.branches and self.branches[0].angle != 0:
            decal = self.branches[0].angle
            for b in self.branches:
                b.angle -= decal

    def _nom_branche_libre(self) -> str:
        noms = {b.nom for b in self.branches}
        k = self.n + 1
        while f"Branche {k}" in noms:
            k += 1
        return f"Branche {k}"


def giratoire_defaut(nb_branches: int = 4, milieu: Milieu = Milieu.PERIURBAIN) -> Giratoire:
    """Giratoire de départ avec les valeurs par défaut de Girabase (guide §2.4.2) :
    R = 6 m (9 m à partir de 6 branches), Bf = 2 m, LA = 7 m, entrées 3,5 m, îlots 3 m, sorties 4 m."""
    g = Giratoire(milieu=milieu, R=6.0 if nb_branches <= 5 else 9.0)
    for k in range(nb_branches):
        g.branches.append(Branche(nom=f"Branche {k + 1}", angle=round(360 * k / nb_branches)))
    g.nouvelle_periode("HPM")
    return g
