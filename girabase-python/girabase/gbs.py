"""Lecture et écriture des fichiers projet Girabase 4 (*.gbs).

Le format est celui produit par les instructions VB6 ``Write #`` de GIRATOIRE.Ecrire :
valeurs séparées par des virgules, chaînes entre guillemets, booléens et dates entre
dièses (#TRUE#, #2005-09-07#), point décimal, encodage Windows-1252.
Les matrices de trafic sont des chaînes de champs de 4 chiffres séparés par un espace,
« VIDE » pour une case non saisie.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Iterator, Optional, Union

from .constantes import Milieu, UniteAngle
from .modele import Branche, Giratoire, Periode

ENCODAGE = "cp1252"
LG_TRAFIC = 4
ID_VIDE = "VIDE"


class ErreurFichierGbs(ValueError):
    pass


# ---------------------------------------------------------------------------
# Lecture
# ---------------------------------------------------------------------------
class _Lecteur:
    """Équivalent de ``Input #`` : lit les champs les uns après les autres."""

    def __init__(self, texte: str):
        self.jetons = list(self._decouper(texte))
        self.pos = 0

    @staticmethod
    def _decouper(t: str) -> Iterator[tuple[str, object]]:
        i, n = 0, len(t)
        while i < n:
            c = t[i]
            if c in " \t\r\n,":
                # Une virgule suivie d'une autre virgule = champ vide
                if c == "," and (i + 1 >= n or t[i + 1] in ",\r\n"):
                    j = i + 1
                    if j < n and t[j] == ",":
                        yield ("vide", None)
                i += 1
                continue
            if c == '"':
                j = t.find('"', i + 1)
                if j < 0:
                    raise ErreurFichierGbs("Guillemet non fermé.")
                yield ("str", t[i + 1:j])
                i = j + 1
                continue
            if c == "#":
                j = t.find("#", i + 1)
                if j < 0:
                    raise ErreurFichierGbs("Littéral # non fermé.")
                yield _Lecteur._litteral(t[i + 1:j])
                i = j + 1
                continue
            j = i
            while j < n and t[j] not in ",\r\n":
                j += 1
            brut = t[i:j].strip()
            try:
                v: object = int(brut)
                yield ("num", v)
            except ValueError:
                try:
                    yield ("num", float(brut))
                except ValueError:
                    yield ("str", brut)
            i = j

    @staticmethod
    def _litteral(s: str) -> tuple[str, object]:
        u = s.strip().upper()
        if u in ("TRUE", "VRAI"):
            return ("bool", True)
        if u in ("FALSE", "FAUX"):
            return ("bool", False)
        if u in ("NULL", "ERROR"):
            return ("vide", None)
        for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y"):
            try:
                return ("date", _dt.datetime.strptime(s.strip(), fmt).date())
            except ValueError:
                pass
        raise ErreurFichierGbs(f"Littéral non reconnu : #{s}#")

    def suivant(self) -> tuple[str, object]:
        if self.pos >= len(self.jetons):
            raise ErreurFichierGbs("Fin de fichier inattendue.")
        j = self.jetons[self.pos]
        self.pos += 1
        return j

    def chaine(self) -> str:
        typ, v = self.suivant()
        return "" if v is None else str(v)

    def entier(self, mini: Optional[int] = None, maxi: Optional[int] = None) -> int:
        typ, v = self.suivant()
        if typ != "num" or not isinstance(v, int):
            raise ErreurFichierGbs(f"Entier attendu, lu : {v!r}")
        if (mini is not None and v < mini) or (maxi is not None and v > maxi):
            raise ErreurFichierGbs(f"Valeur hors bornes : {v}")
        return v

    def reel(self) -> float:
        typ, v = self.suivant()
        if typ == "num":
            return float(v)  # type: ignore[arg-type]
        if typ == "str":
            try:
                return float(str(v).replace(",", "."))
            except ValueError:
                pass
        raise ErreurFichierGbs(f"Nombre attendu, lu : {v!r}")

    def booleen(self) -> bool:
        typ, v = self.suivant()
        if typ != "bool":
            raise ErreurFichierGbs(f"Booléen attendu, lu : {v!r}")
        return bool(v)

    def date(self) -> _dt.date:
        typ, v = self.suivant()
        if typ != "date":
            raise ErreurFichierGbs(f"Date attendue, lu : {v!r}")
        return v  # type: ignore[return-value]


def _decoder_ligne(chaine: str, n: int) -> list[Optional[int]]:
    out: list[Optional[int]] = []
    for i in range(n):
        champ = chaine[(LG_TRAFIC + 1) * i:(LG_TRAFIC + 1) * i + LG_TRAFIC].strip()
        if champ == "" or champ.upper() == ID_VIDE:
            out.append(None)
        else:
            try:
                out.append(int(champ))
            except ValueError as exc:
                raise ErreurFichierGbs(f"Trafic illisible : {champ!r}") from exc
    return out


def _couleur_vers_hex(bgr: int) -> str:
    r, g, b = bgr & 0xFF, (bgr >> 8) & 0xFF, (bgr >> 16) & 0xFF
    return f"#{r:02x}{g:02x}{b:02x}"


def _hex_vers_couleur(h: str) -> int:
    h = h.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return r | (g << 8) | (b << 16)


def lire_texte(texte: str) -> Giratoire:
    lec = _Lecteur(texte)
    titre = lec.chaine()
    if titre.lower() not in ("girabase", "girawal"):
        raise ErreurFichierGbs("Ce fichier n'est pas un projet Girabase.")
    version = lec.chaine()
    if not version.lower().startswith("version"):
        raise ErreurFichierGbs("Version de fichier non reconnue.")
    g = Giratoire()
    g.variante = lec.chaine()
    g.date_modif = lec.date()
    g.nom = lec.chaine()
    milieu = lec.entier(-1, 2)
    g.milieu = None if milieu == -1 else Milieu(milieu)
    nb_branches = lec.entier(3, 8)
    nb_periodes = lec.entier(0)
    g.unite_angle = UniteAngle(lec.entier(0, 1))
    g.R = lec.reel()
    g.Bf = lec.reel()
    g.LA = lec.reel()
    # Localisation (éventuellement sur plusieurs champs) jusqu'au mot-clé BRANCHES
    morceaux = []
    while True:
        typ, v = lec.suivant()
        if typ == "str" and v == "BRANCHES":
            break
        morceaux.append("" if v is None else str(v))
    g.localisation = "\n".join(morceaux).replace("\r\n", "\n").replace("\r", "\n")
    tour = 2 * g.unite_angle.demi_tour
    for k in range(nb_branches):
        b = Branche(nom=lec.chaine())
        b.angle = lec.entier(0, tour - 1)
        b.rampe = lec.booleen()
        b.tad = lec.booleen()
        b.evasee = lec.booleen()
        b.le4, b.le15, b.li, b.ls = lec.reel(), lec.reel(), lec.reel(), lec.reel()
        if k > 0 and b.angle <= g.branches[-1].angle:
            raise ErreurFichierGbs("Les angles des branches doivent être croissants.")
        g.branches.append(b)
    if lec.chaine() != "TRAFICS":
        raise ErreurFichierGbs("Section TRAFICS absente.")
    for _ in range(nb_periodes):
        nom = lec.chaine()
        mode_uvp = lec.booleen()
        couleur = lec.entier(0, 0xFFFFFF)
        p = Periode(nom=nom, nb_branches=nb_branches, mode_uvp=mode_uvp, couleur=_couleur_vers_hex(couleur))
        p.pietons = _decoder_ligne(lec.chaine(), nb_branches)
        if mode_uvp:
            p.uvp = [_decoder_ligne(lec.chaine(), nb_branches) for _ in range(nb_branches)]
        else:
            p.vl = [_decoder_ligne(lec.chaine(), nb_branches) for _ in range(nb_branches)]
            p.pl = [_decoder_ligne(lec.chaine(), nb_branches) for _ in range(nb_branches)]
            p.dr = [_decoder_ligne(lec.chaine(), nb_branches) for _ in range(nb_branches)]
        if any(q.nom == nom for q in g.periodes):
            raise ErreurFichierGbs(f"Période en double : {nom}")
        g.periodes.append(p)
    return g


def lire(chemin: Union[str, Path]) -> Giratoire:
    donnees = Path(chemin).read_bytes()
    try:
        texte = donnees.decode(ENCODAGE)
    except UnicodeDecodeError:
        texte = donnees.decode("latin-1")
    return lire_texte(texte)


# ---------------------------------------------------------------------------
# Écriture
# ---------------------------------------------------------------------------
def _w(v: object) -> str:
    if isinstance(v, bool):
        return "#TRUE#" if v else "#FALSE#"
    if isinstance(v, _dt.date):
        return f"#{v:%Y-%m-%d}#"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        s = f"{v:.7g}"
        if "e" in s:
            s = f"{v:.7f}".rstrip("0").rstrip(".")
        return s
    return '"' + str(v).replace('"', "'") + '"'


def _ligne(*valeurs: object) -> str:
    return ",".join(_w(v) for v in valeurs) + "\r\n"


def _coder_ligne(valeurs: list[Optional[int]]) -> str:
    champs = [ID_VIDE if v is None else f"{v:0{LG_TRAFIC}d}" for v in valeurs]
    return " ".join(champs)


def ecrire_texte(g: Giratoire) -> str:
    periodes = g.periodes_reelles()
    out = [
        _ligne("Girabase", "Version 4"),
        _ligne(g.variante, g.date_modif),
        _ligne(g.nom, -1 if g.milieu is None else int(g.milieu)),
        _ligne(g.n, len(periodes), int(g.unite_angle)),
        _ligne(float(g.R), float(g.Bf), float(g.LA)),
        _ligne(g.localisation.replace("\n", "\r\n")),
        _ligne("BRANCHES"),
    ]
    for b in g.branches:
        out.append(_ligne(b.nom, int(b.angle), b.rampe, b.tad))
        out.append(_ligne(b.evasee, float(b.le4), float(b.le15), float(b.li), float(b.ls)))
    out.append(_ligne("TRAFICS"))
    for p in periodes:
        out.append(_ligne(p.nom, p.mode_uvp, _hex_vers_couleur(p.couleur)))
        out.append(_ligne(_coder_ligne(p.pietons)))
        mats = [p.uvp] if p.mode_uvp else [p.vl, p.pl, p.dr]
        for mat in mats:
            for row in mat:
                out.append(_ligne(_coder_ligne(row)))
    return "".join(out)


def ecrire(g: Giratoire, chemin: Union[str, Path]) -> None:
    g.date_modif = _dt.date.today()
    texte = ecrire_texte(g)
    Path(chemin).write_bytes(texte.encode(ENCODAGE, errors="replace"))
