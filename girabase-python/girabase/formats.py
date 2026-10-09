"""Mise en forme des résultats, à l'identique de Résultats.frm (AfficheRésultats)."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from .calcul import ResultatBranche


def arrondi(x: float, decimales: int = 0) -> Decimal:
    """Arrondi de la fonction Format de VB (demi vers l'extérieur)."""
    q = Decimal(1).scaleb(-decimales)
    return Decimal(repr(x)).quantize(q, rounding=ROUND_HALF_UP)


def nombre(x: float, decimales: int = 0) -> str:
    s = f"{arrondi(x, decimales):f}"
    if s in ("-0", "-0.0", "-0.00"):
        s = s[1:]
    return s.replace(".", ",")


def rc(rb: ResultatBranche) -> str:
    return "" if rb.entree_nulle else nombre(rb.rc_affichee)


def rc_pct(rb: ResultatBranche) -> str:
    v = rb.RC_pct
    return "" if v is None else nombre(v) + " %"


def lk(rb: ResultatBranche) -> str:
    return "" if rb.entree_nulle else nombre(rb.LK) + " véh"


def lkm(rb: ResultatBranche) -> str:
    return "" if rb.entree_nulle else nombre(rb.LKM) + " véh"


def tma(rb: ResultatBranche) -> str:
    return "" if rb.entree_nulle else nombre(rb.TMA) + " s"


def tta_heures(tta: float) -> float:
    """Temps total d'attente en heures, minutes arrondies comme dans Girabase."""
    nb_sec = int(round(tta))
    h = nb_sec // 3600
    nb_sec -= h * 3600
    mn = nb_sec // 60
    nb_sec -= mn * 60
    if nb_sec > 30:
        mn += 1
    return h + mn / 60


def tta(rb: ResultatBranche) -> str:
    if rb.entree_nulle:
        return ""
    h = tta_heures(rb.TTA)
    return nombre(h, 0 if h > 100 else 1) + " h"


def tta_hms(rb: ResultatBranche) -> str:
    nb_sec = int(round(rb.TTA))
    h, reste = divmod(nb_sec, 3600)
    m, s = divmod(reste, 60)
    return (f"{h}h" if h else "") + f"{m}m{s}s"


def niveau_rc(pct: Optional[float]) -> str:
    """Lecture du guide (§1.3.1) : 'sature' < 0 %, 'faible' < 15 %, 'correct', 'surdim' > 80 %."""
    if pct is None:
        return ""
    if pct < 0:
        return "sature"
    if pct < 15:
        return "faible"
    if pct > 80:
        return "surdim"
    return "correct"
