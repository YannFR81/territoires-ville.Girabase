"""Format d'échange JSON d'un giratoire et de ses résultats (serveur MCP, scripts).

Exemple minimal :

    {"nom": "Giratoire D71 / D41", "milieu": "rase_campagne",
     "anneau": {"R": 5, "Bf": 2, "LA": 7},
     "branches": [{"nom": "D71 Nord", "angle": 0}, {"nom": "D41 Ouest", "angle": 81},
                  {"nom": "D71 Sud", "angle": 186}, {"nom": "D41 Est", "angle": 270}],
     "periodes": [{"nom": "HPM", "trafics_uvp": [[0, 120, 300, 80], [100, 0, 90, 200],
                                                 [280, 60, 0, 70], [90, 210, 60, 0]]}]}

Les largeurs absentes prennent les valeurs par défaut de Girabase (entrée 3,5 m, îlot 3 m, sortie 4 m) ;
les trafics sont en uvp/h (« trafics_uvp ») ou par catégorie (« trafics_vl », « trafics_pl », « trafics_2r »).
"""
from __future__ import annotations

from typing import Any, Optional

from . import formats as F
from .calcul import ResultatPeriode, calculer
from .conseils import (avertissements_domaine, erreurs, recommandations_saisie, remarques_conception,
                       remarques_fonctionnement, remarques_trafics)
from .constantes import NB_BRANCHES_MAX, NB_BRANCHES_MIN, Milieu, UniteAngle
from .modele import Branche, Giratoire, Periode

MILIEUX = {"rase_campagne": Milieu.RASE_CAMPAGNE, "periurbain": Milieu.PERIURBAIN,
           "centre_ville": Milieu.CENTRE_VILLE}
CODES_MILIEU = {v: k for k, v in MILIEUX.items()}
ALIAS_MILIEU = {"rc": "rase_campagne", "rase campagne": "rase_campagne", "pu": "periurbain",
                "périurbain": "periurbain", "peri-urbain": "periurbain", "cv": "centre_ville",
                "centre-ville": "centre_ville", "centre ville": "centre_ville", "urbain": "centre_ville"}


class DonneesInvalides(ValueError):
    """Description de giratoire incomplète ou incohérente (message en clair pour l'utilisateur)."""


def _milieu(valeur: Any) -> Optional[Milieu]:
    if valeur is None or valeur == "":
        return None
    if isinstance(valeur, int):
        return Milieu(valeur)
    cle = str(valeur).strip().lower()
    cle = ALIAS_MILIEU.get(cle, cle)
    if cle not in MILIEUX:
        raise DonneesInvalides(f"Milieu inconnu « {valeur} » : rase_campagne, periurbain ou centre_ville.")
    return MILIEUX[cle]


def _matrice(m: Any, n: int, nom: str) -> list[list[Optional[int]]]:
    if not isinstance(m, list) or len(m) != n or any(not isinstance(r, list) or len(r) != n for r in m):
        raise DonneesInvalides(f"« {nom} » doit être une matrice {n} × {n} (origine en ligne, destination en "
                               "colonne).")
    out = []
    for i, r in enumerate(m):
        ligne = []
        for j, v in enumerate(r):
            if v is None or v == "":
                ligne.append(None)
                continue
            try:
                x = float(v)
            except (TypeError, ValueError):
                raise DonneesInvalides(f"« {nom} »[{i + 1}][{j + 1}] n'est pas un nombre : {v!r}") from None
            if x < 0:
                raise DonneesInvalides(f"« {nom} »[{i + 1}][{j + 1}] est négatif.")
            ligne.append(int(round(x)))
        out.append(ligne)
    return out


def giratoire_depuis_dict(d: dict) -> Giratoire:
    if not isinstance(d, dict):
        raise DonneesInvalides("Le giratoire doit être un objet JSON.")
    branches = d.get("branches") or []
    n = len(branches)
    if not NB_BRANCHES_MIN <= n <= NB_BRANCHES_MAX:
        raise DonneesInvalides(f"Girabase traite de {NB_BRANCHES_MIN} à {NB_BRANCHES_MAX} branches ({n} reçues).")
    anneau = d.get("anneau") or {}
    g = Giratoire(nom=str(d.get("nom") or "Giratoire"), localisation=str(d.get("localisation") or ""),
                  variante=str(d.get("variante") or "Variante 1"), milieu=_milieu(d.get("milieu")),
                  R=float(anneau.get("R", d.get("R", 6.0))), Bf=float(anneau.get("Bf", d.get("Bf", 2.0))),
                  LA=float(anneau.get("LA", d.get("LA", 7.0))))
    if str(d.get("unite_angle", "degres")).lower().startswith("grad"):
        g.unite_angle = UniteAngle.GRADE
    for k, b in enumerate(branches):
        if not isinstance(b, dict):
            raise DonneesInvalides(f"Branche {k + 1} : objet attendu.")
        le4 = float(b.get("le4", b.get("largeur_entree", 3.5)))
        g.branches.append(Branche(nom=str(b.get("nom") or f"Branche {k + 1}"), angle=int(round(float(b.get("angle",
                                  round(360 * k / n))))), rampe=bool(b.get("rampe", False)),
                                  tad=bool(b.get("tad", b.get("tourne_a_droite", False))),
                                  evasee=bool(b.get("evasee", False)), le4=le4,
                                  le15=float(b.get("le15", le4)), li=float(b.get("li", b.get("largeur_ilot", 3.0))),
                                  ls=float(b.get("ls", b.get("largeur_sortie", 4.0)))))
    periodes = d.get("periodes")
    if periodes is None:
        periodes = [{"nom": "HPM"}]
    for k, p in enumerate(periodes):
        if not isinstance(p, dict):
            raise DonneesInvalides(f"Période {k + 1} : objet attendu.")
        mode_uvp = "trafics_vl" not in p
        per = Periode(nom=str(p.get("nom") or f"Période {k + 1}"), nb_branches=n, mode_uvp=mode_uvp)
        if mode_uvp:
            if "trafics_uvp" in p:
                per.uvp = _matrice(p["trafics_uvp"], n, "trafics_uvp")
        else:
            per.vl = _matrice(p["trafics_vl"], n, "trafics_vl")
            per.pl = _matrice(p.get("trafics_pl") or [[0] * n for _ in range(n)], n, "trafics_pl")
            per.dr = _matrice(p.get("trafics_2r") or [[0] * n for _ in range(n)], n, "trafics_2r")
        if "pietons" in p:
            pi = p["pietons"]
            if not isinstance(pi, list) or len(pi) != n:
                raise DonneesInvalides(f"« pietons » : liste de {n} valeurs (piétons/h traversant chaque branche).")
            per.pietons = [None if v is None else int(round(float(v))) for v in pi]
        g.periodes.append(per)
    return g


def giratoire_vers_dict(g: Giratoire) -> dict:
    periodes = []
    for p in g.periodes_reelles():
        d: dict[str, Any] = {"nom": p.nom, "pietons": list(p.pietons)}
        if p.mode_uvp:
            d["trafics_uvp"] = [list(r) for r in p.uvp]
        else:
            d.update(trafics_vl=[list(r) for r in p.vl], trafics_pl=[list(r) for r in p.pl],
                     trafics_2r=[list(r) for r in p.dr])
        periodes.append(d)
    return {"nom": g.nom, "variante": g.variante, "localisation": g.localisation,
            "milieu": CODES_MILIEU.get(g.milieu), "unite_angle": "grades" if g.unite_angle is UniteAngle.GRADE
            else "degres", "anneau": {"R": g.R, "Bf": g.Bf, "LA": g.LA, "Rg": g.Rg},
            "branches": [{"nom": b.nom, "angle": b.angle, "le4": b.le4, "le15": b.le15, "li": b.li, "ls": b.ls,
                          "evasee": b.evasee, "rampe": b.rampe, "tad": b.tad} for b in g.branches],
            "periodes": periodes}


def _resultat_periode(g: Giratoire, res: ResultatPeriode) -> dict:
    branches = []
    for rb in res.branches:
        pct = rb.RC_pct
        branches.append({
            "branche": rb.nom, "entree_nulle": rb.entree_nulle, "trafic_entrant_uvp_h": rb.QE,
            "trafic_genant_uvp_h": rb.QG, "capacite_uvp_h": round(rb.C), "reserve_uvp_h": round(rb.rc_affichee),
            "reserve_pct": None if pct is None else round(pct), "niveau": F.niveau_rc(pct),
            "file_moyenne_veh": round(rb.LK, 1), "file_maximale_veh": round(rb.LKM, 1),
            "attente_moyenne_s": round(rb.TMA), "attente_totale_h": round(F.tta_heures(rb.TTA), 1),
            "affichage_girabase": {"reserve": F.rc(rb), "reserve_pct": F.rc_pct(rb), "file_moyenne": F.lk(rb),
                                   "file_maximale": F.lkm(rb), "attente_moyenne": F.tma(rb),
                                   "attente_totale": F.tta(rb)}})
    return {"periode": res.periode.nom, "trafics_complets": res.complete, "branches": branches,
            "remarques_trafics": [r.texte for r in remarques_trafics(g, res)],
            "fonctionnement": [r.texte for r in remarques_fonctionnement(g, res)],
            "avertissements": [r.texte for r in avertissements_domaine(g, res.periode)]}


def calcul_complet(g: Giratoire) -> dict:
    """Résultats de toutes les périodes, avec les contrôles et les conseils de Girabase 4."""
    err = [r.texte for r in erreurs(g)]
    sortie: dict[str, Any] = {"giratoire": g.nom, "milieu": CODES_MILIEU.get(g.milieu), "Rg_m": round(g.Rg, 2),
                              "erreurs": err, "recommandations": [r.texte for r in recommandations_saisie(g, None)]}
    if err:
        sortie["resultats"] = []
        return sortie
    resultats = calculer(g)
    sortie["resultats"] = [_resultat_periode(g, r) for r in resultats]
    sortie["remarques_conception"] = [r.texte for r in remarques_conception(g, resultats[0] if resultats else None)]
    sortie["lecture"] = ("Réserve de capacité (guide Girabase §1.3.1) : < 0 % entrée saturée, < 15 % réserve "
                         "faible, 15 à 80 % fonctionnement correct, > 80 % entrée surdimensionnée.")
    return sortie
