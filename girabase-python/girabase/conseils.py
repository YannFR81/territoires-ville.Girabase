"""Contrôles de validité, recommandations de saisie et conseils sur les résultats.

Portage de Données.frm (ValidationDonnées, ValiderFeuilleDonnées, ControleRecommandations,
VerifierAngleBranche) et de Résultats.frm (AfficheConception, AfficheConceptionBranches,
AffichePériode, AfficheFonctionnement).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from .calcul import ResultatPeriode, parametres_giratoire
from .constantes import (BF_MAX, LA_MAX_RC, LA_MAX_URBAIN, LA_MIN, LE4_MAX, LS_MAX, M, NB_BRANCHES_MAX,
                         NB_BRANCHES_MIN, Q_MAX, QP_MAX, R_MAX, RG_MIN, RG_MINI_MAX, RG_MINI_MIN, Milieu,
                         UniteAngle)
from .modele import Giratoire, Periode

RC, PU, CV = Milieu.RASE_CAMPAGNE, Milieu.PERIURBAIN, Milieu.CENTRE_VILLE


@dataclass
class Remarque:
    texte: str
    branche: Optional[int] = None      # indice de branche concerné, None pour le giratoire
    champ: Optional[str] = None        # champ de saisie concerné (R, LA, Bf, le4, ls, ...)

    def __str__(self) -> str:
        return self.texte


def _fmt(x: float) -> str:
    return f"{x:g}".replace(".", ",")


# ---------------------------------------------------------------------------
# Validité (bloque le calcul)
# ---------------------------------------------------------------------------
def demi_angles_branche(le4: float, li: float, ls: float, rg: float) -> Optional[tuple[float, float]]:
    """Demi-ouvertures angulaires (entrée, sortie) d'une branche sur le cercle extérieur (calculBord).

    Retourne None si la branche est plus large que le giratoire.
    """
    li2 = li / 2
    if le4 == 0 or ls == 0:
        largeur = ls if le4 == 0 else le4
        if largeur > rg:
            return None
        a = math.asin(largeur / rg)
        return (0.0, a) if le4 == 0 else (a, 0.0)
    if le4 + li2 > rg or ls + li2 > rg:
        return None
    return math.asin((le4 + li2) / rg), math.asin((ls + li2) / rg)


def erreurs(g: Giratoire) -> list[Remarque]:
    """Données invalides : le calcul n'est pas possible tant qu'elles subsistent."""
    err: list[Remarque] = []
    n = g.n
    if g.milieu is None:
        err.append(Remarque("Le type de site (environnement) doit être choisi.", champ="milieu"))
    if not NB_BRANCHES_MIN <= n <= NB_BRANCHES_MAX:
        err.append(Remarque(f"Le giratoire doit avoir entre {NB_BRANCHES_MIN} et {NB_BRANCHES_MAX} branches."))
        return err
    noms = [b.nom.strip() for b in g.branches]
    if any(not x for x in noms):
        err.append(Remarque("Chaque branche doit avoir un nom."))
    if len(set(noms)) != len(noms):
        err.append(Remarque("Nom de branche déjà utilisé."))
    tour = 2 * g.unite_angle.demi_tour
    if g.branches[0].angle != 0:
        err.append(Remarque("La branche n° 1 doit avoir un angle nul.", branche=0, champ="angle"))
    for k in range(1, n):
        a, a0 = g.branches[k].angle, g.branches[k - 1].angle
        if not (a0 < a < tour):
            err.append(Remarque(f"Les angles doivent être croissants et inférieurs à {tour} {g.unite_angle.libelle} "
                                f"(branche {g.branches[k].nom}).", branche=k, champ="angle"))
    # Anneau
    if not 0 <= g.R <= R_MAX:
        err.append(Remarque(f"Le rayon de l'îlot infranchissable doit être compris entre 0 et {R_MAX:g} m.", champ="R"))
    if g.R == 0 and g.milieu == RC:
        err.append(Remarque(M["RNulEnRC"], champ="R"))
    if g.R == 0 and any(b.tad for b in g.branches):
        err.append(Remarque("Les voies de tourne-à-droite sont interdites sur un mini-giratoire.", champ="R"))
    if not 0 <= g.Bf <= BF_MAX:
        err.append(Remarque(f"La valeur doit être comprise entre 0 et {_fmt(BF_MAX)} m (bande franchissable).", champ="Bf"))
    la_max = LA_MAX_RC if g.milieu == RC else LA_MAX_URBAIN
    if not LA_MIN <= g.LA <= la_max:
        err.append(Remarque(f"La largeur d'anneau doit être comprise entre {_fmt(LA_MIN)} et {_fmt(la_max)} m.", champ="LA"))
    rg = g.Rg
    if g.R == 0:
        if not RG_MINI_MIN <= rg <= RG_MINI_MAX:
            err.append(Remarque(f"La valeur du rayon extérieur doit être comprise entre {_fmt(RG_MINI_MIN)} et "
                                f"{_fmt(RG_MINI_MAX)} m (mini-giratoire).", champ="Rg"))
        if not 1.5 <= g.Bf <= 2.5:
            err.append(Remarque(M["BfTropPetitPourMiniG"], champ="Bf"))
    elif rg < RG_MIN:
        err.append(Remarque(f"La valeur du rayon extérieur doit être supérieure à {_fmt(RG_MIN)} m.", champ="Rg"))
    # Branches
    for k, b in enumerate(g.branches):
        if not 0 <= b.le4 <= LE4_MAX:
            err.append(Remarque(f"{b.nom} : la largeur d'entrée doit être comprise entre 0 et {LE4_MAX:g} m.", k, "le4"))
        if not 0 <= b.ls <= LS_MAX:
            err.append(Remarque(f"{b.nom} : la largeur de sortie doit être comprise entre 0 et {LS_MAX:g} m.", k, "ls"))
        if b.li < 0 or b.le15 < 0:
            err.append(Remarque(f"{b.nom} : la valeur doit être positive ou nulle.", k, "li"))
        if b.le4 == 0 and b.ls == 0:
            err.append(Remarque(f"{b.nom} : la largeur d'entrée et la largeur de sortie ne peuvent être toutes "
                                f"deux nulles.", k, "le4"))
        if b.le4 == 0 and b.tad:
            err.append(Remarque(f"{b.nom} : une largeur d'entrée nulle n'est pas compatible avec la présence "
                                f"d'une voie de tourne-à-droite.", k, "tad"))
        if b.evasee:
            rapport = 10 if b.le15 == 0 else b.le4 / b.le15
            if rapport < 1 or rapport > 2.5:
                err.append(Remarque(f"{b.nom} : {M['RapportLE']}", k, "le15"))
    err.extend(_chevauchements(g))
    # Trafics
    if not g.periodes_reelles():
        err.append(Remarque("Aucun trafic n'a été saisi."))
    for p in g.periodes_reelles():
        err.extend(erreurs_periode(g, p))
    return err


def _chevauchements(g: Giratoire) -> list[Remarque]:
    """VerifierAngleBranche : les branches ne doivent pas se chevaucher sur le cercle extérieur."""
    out: list[Remarque] = []
    rg = g.Rg
    n = g.n
    demi = []
    for k, b in enumerate(g.branches):
        d = demi_angles_branche(b.le4, b.li if not (b.entree_nulle or b.sortie_nulle) else 0.0, b.ls, rg)
        if d is None:
            out.append(Remarque(f"{b.nom} : le rayon extérieur n'est pas compatible avec la dimension de la "
                                f"branche (entrée + îlot ou sortie + îlot plus large que le rayon).", k, "le4"))
            return out
        demi.append(d)
    for k in range(n):
        k2 = (k + 1) % n
        a1 = g.angle_rad(k) + demi[k][0]             # bord de l'entrée de k
        a2 = g.angle_rad(k2) - demi[k2][1]           # bord de la sortie de la suivante
        if k2 == 0:
            a2 += 2 * math.pi
        if not a1 < a2:
            out.append(Remarque(f"Les branches {g.branches[k].nom} et {g.branches[k2].nom} se chevauchent : "
                                f"réduisez les largeurs ou augmentez l'écart angulaire ou le rayon extérieur.",
                                k2, "angle"))
    return out


def erreurs_periode(g: Giratoire, p: Periode) -> list[Remarque]:
    out: list[Remarque] = []
    uvp = p.matrice_uvp()
    for i, b in enumerate(g.branches):
        if b.entree_nulle and any((v or 0) > 0 for v in uvp[i]):
            out.append(Remarque(f"{p.nom} : trafic non nul en entrée de {b.nom} alors que sa largeur "
                                f"d'entrée est nulle.", i))
        if b.sortie_nulle and any((uvp[r][i] or 0) > 0 for r in range(g.n)):
            out.append(Remarque(f"{p.nom} : trafic non nul en sortie vers {b.nom} alors que sa largeur "
                                f"de sortie est nulle.", i))
    for mat in p.matrices_saisie().values():
        if any(v is not None and v < 0 for row in mat for v in row):
            out.append(Remarque(f"{p.nom} : les trafics doivent être positifs ou nuls."))
            break
    if any(v is not None and not 0 <= v <= QP_MAX for v in p.pietons):
        out.append(Remarque(f"{p.nom} : le trafic piéton doit être compris entre 0 et {QP_MAX} p/h."))
    return out


def avertissements_domaine(g: Giratoire, p: Periode) -> list[Remarque]:
    """Mouvements hors du domaine de validité (2500 uvp/h), par exemple après multiplication."""
    uvp = p.matrice_uvp()
    hors = [(i, j) for i in range(g.n) for j in range(g.n) if (uvp[i][j] or 0) > Q_MAX]
    if hors:
        i, j = hors[0]
        return [Remarque(f"{p.nom} : {len(hors)} mouvement(s) dépassent {Q_MAX} uvp/h (ex. {g.branches[i].nom} → "
                         f"{g.branches[j].nom}), hors du domaine de validité de Girabase.")]
    return []


# ---------------------------------------------------------------------------
# Recommandations de saisie (ControleRecommandations)
# ---------------------------------------------------------------------------
def _ecart_mini(g: Giratoire, k: int) -> Optional[int]:
    """ControleCarBranches (mini-giratoire) : -1 angle < 70°, +1 angle < 80°, 0 sinon."""
    b = g.branches[k]
    if b.entree_nulle:
        return 0
    if k == 0:
        valeur = g.branches[-1].angle
        ecart = (400 - valeur) * 0.9 if g.unite_angle is UniteAngle.GRADE else 360 - valeur
    else:
        ecart = b.angle - g.branches[k - 1].angle
        if g.unite_angle is UniteAngle.GRADE:
            ecart *= 0.9
        if ecart < 0:
            ecart += 360
    if ecart < 70:
        return -1
    if ecart < 80:
        return 1
    return 0


def recommandations_saisie(g: Giratoire, periode: Optional[Periode] = None) -> list[Remarque]:
    """Recommandations affichées pendant la saisie (n'empêchent pas le calcul)."""
    rec: list[Remarque] = []

    def add(cle_ou_texte: str, branche=None, champ=None) -> None:
        texte = M.get(cle_ou_texte, cle_ou_texte)
        if branche is not None:
            texte = f"{g.branches[branche].nom} : {texte}"
        if all(r.texte != texte for r in rec):
            rec.append(Remarque(texte, branche, champ))

    rg = g.Rg
    mil = g.milieu
    if mil == RC and g.n > 6:
        add("TropDeBranchesEnRC", champ="milieu")
    if 0 < g.R < 3.5:
        add("RTropGrandPourMiniG", champ="R")
    if g.R > 25:
        add("RTropGrand", champ="R")
    if g.R == 0 and mil == PU and rg < 12:
        add("RNulEnPU", champ="R")
    if g.LA < 6 and mil == RC:
        add("LATropEtroit", champ="LA")
    elif (g.LA > 9 and mil == RC) or g.LA > 12:
        add("LATropGrand", champ="LA")
    if g.R == 0 and rg < 7.5:
        add("RgTropPetitPourMiniG", champ="Rg")
    if g.R == 0 and rg > 12:
        add("RgTropGrandPourMiniG", champ="Rg")
    if 12 < rg < 15 and mil == RC:
        add("RgVoirGirationEnRC", champ="Rg")
    if 12 < rg < 15 and mil in (PU, CV):
        add("RgVoirGiration", champ="Rg")
    if g.LA + g.Bf < 7 and mil is not None and mil != RC:
        add("LATropEtroit", champ="LA")
    if g.R == 0 and not 1.5 <= g.Bf <= 2.5:
        add("BfTropPetitPourMiniG", champ="Bf")
    elif 12 < rg < 15 and (g.Bf < 1.5 or g.Bf > 2.0):
        add("Bf", champ="Bf")

    limax = None
    if mil is not None and g.LA + g.Bf > (3.5 if g.R == 0 else 0):
        try:
            limax = parametres_giratoire(g).LImax
        except (ValueError, ZeroDivisionError):
            limax = None
    for k, b in enumerate(g.branches):
        # ControleDimensionnement1
        if b.le4 == 0:
            add("LENul", k, "le4")
        elif b.le4 < 1.5:
            add("LETropPetit", k, "le4")
        if 1.5 <= b.le4 < 2.5:
            add("LE2Roues", k, "le4")
        elif 2.5 <= b.le4 < 3:
            add("LEPetit", k, "le4")
        elif b.le4 > 8 and mil == RC:
            add("LETropLargeEnRC", k, "le4")
        if b.le4 >= 9 and mil != RC:
            add("LETropLargePourPietons", k, "le4")
        if b.ls == 0:
            add("LSNul", k, "ls")
        elif b.ls < 1.5:
            add("LSTropPetit", k, "ls")
        elif b.ls < 2.75:
            add("LS2Roues", k, "ls")
        elif b.ls < 3.5:
            add("LSPetit", k, "ls")
        elif b.ls > 7:
            add("LSTropLarge", k, "ls")
        if limax is not None and b.li > limax:
            add("LITropGrand", k, "li")
        # ControleDimensionnementN
        if b.evasee:
            rapport = 10 if b.le15 == 0 else b.le4 / b.le15
            if rapport < 1 or rapport > 2.5:
                add("RapportLE", k, "le15")
            if mil == RC and rapport > 1:
                add("EvasementEnRC", k, "le15")
            if mil != RC and rapport > 1.5:
                add("EvasementTropPetit", k, "le15")
        if b.li < 2 and not b.entree_nulle and not b.sortie_nulle and mil == CV and g.R > 0:
            add("LITropPetit", k, "li")
        if b.le4 + b.li + b.ls >= 2 * rg:
            add("LTropGrand", k, "le4")
        if g.R == 0:
            e = _ecart_mini(g, k)
            if e and e < 0:
                add("AngleTropPetitPourMiniG", k, "angle")
            elif e:
                add("AnglePourMiniG", k, "angle")
    # ControleLE4Max
    if g.branches:
        kmax = max(range(g.n), key=lambda i: g.branches[i].le4)
        le4max = g.branches[kmax].le4
        if 6 <= le4max < 8 and rg < 20 and mil == RC:
            add("RgTropPetit", champ="Rg")
        if g.LA + 0.5 * g.Bf < le4max * 1.2:
            add(M["LATropEtroitPourEntrer"] + g.branches[kmax].nom + ".", champ="LA")
    # Trafics
    for p in ([periode] if periode is not None else g.periodes_reelles()):
        uvp = p.matrice_uvp()
        if any((v or 0) > 999 for v in p.pietons):
            add(f"{p.nom} : {M['QPTropGrand']}")
        if any((v or 0) > 1500 for row in uvp for v in row):
            add(f"{p.nom} : {M['QTropGrand']}")
        for k, b in enumerate(g.branches):
            q = uvp[k][g.suivante(k)]
            if b.tad and q is not None and q < 100:
                add(f"{p.nom} : {b.nom} : {M['QTropPetitPourTAD']}")
    return rec


# ---------------------------------------------------------------------------
# Conseils sur les résultats
# ---------------------------------------------------------------------------
def remarques_conception(g: Giratoire, res: Optional[ResultatPeriode] = None) -> list[Remarque]:
    """Onglet « Remarques de conception » (AfficheConception + AfficheConceptionBranches)."""
    out: list[Remarque] = []
    mil = g.milieu
    pg = parametres_giratoire(g)
    rg = g.Rg
    kmax = max(range(g.n), key=lambda i: (g.branches[i].le4, -i))
    le4max = g.branches[kmax].le4
    if mil == RC and g.n > 6:
        out.append(Remarque(M["TropDeBranchesEnRC"]))
    if g.R > 25:
        out.append(Remarque(M["RTropGrand"] + " " + M["RTropGrand2"]))
    if g.LA < 6 and mil == RC:
        out.append(Remarque(M["LATropEtroit"]))
    elif (g.LA > 9 and mil == RC) or g.LA > 12:
        out.append(Remarque(M["LATropGrand"]))
    if pg.LAU < 1.2 * le4max:
        out.append(Remarque(M["LATropEtroitPourEntrer"] + g.branches[kmax].nom))
    if g.LA + g.Bf < 7 and mil != RC:
        out.append(Remarque(M["LATropEtroit"]))
    if 12 < rg < 15 and (g.Bf < 1.5 or g.Bf > 2.5):
        out.append(Remarque(M["Bf"]))
    if 12 < rg < 15 and mil == RC:
        out.append(Remarque(M["RgVoirGirationEnRC"]))
    elif 12 < rg < 15:
        out.append(Remarque(M["RgVoirGiration"]))
    if 6 <= le4max < 8 and rg < 20 and mil == RC:
        out.append(Remarque(M["RgTropPetit"]))

    for k, b in enumerate(g.branches):
        if not b.entree_nulle:
            if b.le4 < 3:
                out.append(Remarque(M["LEPetit"], k))
            elif b.le4 > 8 and mil == RC:
                out.append(Remarque(M["LETropLargeEnRC"], k))
            if b.le4 >= 9:
                out.append(Remarque(M["LETropLargePourPietons"], k))
        if not b.sortie_nulle:
            if b.ls < 3.5:
                out.append(Remarque(M["LSPetit"], k))
            elif b.ls > 7:
                out.append(Remarque(M["LSTropLarge"], k))
        if b.evasee and b.le15 > 0:
            rapport = b.le4 / b.le15
            if mil == RC and rapport > 1:
                out.append(Remarque(M["EvasementEnRC"], k))
            elif mil != RC and rapport > 1.5:
                out.append(Remarque(M["EvasementTropPetit"], k))
        bidir = not b.entree_nulle and not b.sortie_nulle
        if b.li < 2 and bidir and mil == CV and g.R > 0:
            out.append(Remarque(M["LITropPetit"], k))
        if b.li > pg.LImax:
            out.append(Remarque(M["LITropGrand"], k))
        if b.li < 0.85 and bidir and g.R == 0:
            out.append(Remarque(M["IlotASeparer"], k))
        if g.R == 0:
            e = _ecart_mini(g, k)
            if e and e < 0:
                out.append(Remarque(M["AngleTropPetitPourMiniG"], k))
            elif e:
                out.append(Remarque(M["AnglePourMiniG"], k))
        if bidir and mil != RC:
            for p in g.periodes_reelles():
                qp = p.pietons[k] or 0
                if p.est_complete(g.branches) and b.li < qp / 300 and (mil != CV or b.li >= 2):
                    out.append(Remarque(M["IlotEtroit"], k))
                    break
    return out


def remarques_trafics(g: Giratoire, res: ResultatPeriode) -> list[Remarque]:
    """Onglet « Remarques sur les trafics » (AffichePériode)."""
    out: list[Remarque] = []
    if not res.complete:
        return [Remarque(M["TraficsIncomplets"])]
    total = sum(b.QE for b in res.branches)
    if g.R == 0:
        if 1500 < total <= 1800:
            out.append(Remarque(M["QEGrandPourMiniG"]))
        elif total > 1800:
            out.append(Remarque(M["QETropGrandPourMiniG"]))
    elif total > 5000:
        out.append(Remarque(M["QETropGrand"]))
    uvp = res.periode.matrice_uvp()
    for k, b in enumerate(g.branches):
        rb = res.branches[k]
        if b.tad and (uvp[k][g.suivante(k)] or 0) < 100:
            out.append(Remarque(M["QTropPetitPourTAD"], k))
        if rb.QE <= 0 and not b.entree_nulle:
            out.append(Remarque(M["QEnul"], k))
        if rb.QS <= 0 and not b.sortie_nulle:
            out.append(Remarque(M["QSnul"], k))
    return out


def remarques_fonctionnement(g: Giratoire, res: ResultatPeriode) -> list[Remarque]:
    """Onglet « Fonctionnement » (AfficheFonctionnement), une liste par branche."""
    out: list[Remarque] = []
    if not res.complete:
        return [Remarque(M["TraficsIncomplets"])]
    mil = g.milieu
    pg = res.params
    uvp = res.periode.matrice_uvp()

    def add(texte: str, k: int) -> None:
        out.append(Remarque(texte, k))

    for k, b in enumerate(g.branches):
        rb = res.branches[k]
        if res.periode.branche_saturee == k:
            add(M["MatriceSaturation"], k)
            continue
        if b.entree_nulle:
            add(M["BrancheSortie"], k)
            continue
        suiv, prec = g.suivante(k), g.precedente(k)
        q_immediat = uvp[k][suiv] or 0
        q_sortant = rb.QS
        q_entrant = rb.QE
        q_tournant = rb.QTournant
        if b.tad:
            q_entrant -= q_immediat
            q_immediat = 0
        if g.branches[prec].tad:
            q_sortant -= uvp[prec][k] or 0
        if b.sortie_nulle:
            add(M["BrancheEntree"], k)
        if b.li < 0.85 and not b.sortie_nulle and g.R == 0:
            add(M["IlotASeparer"], k)
        # Largeur de sortie
        if b.ls < 6:
            pieton = " " + M["TraverseePietons"] if mil != RC else ""
            if q_sortant > 1200:
                add(M["LS2voiesN"].strip() + pieton, k)
            elif (q_sortant > 600 and pg.LAU >= 10.5) or \
                    (q_sortant > max(3 * q_tournant, 900) and pg.LAU > 8 and mil != CV):
                add(M["LS2voiesP"].strip() + pieton, k)
        le = b.largeur_entree
        # Réserve de capacité
        rc_pct = 100.0 * rb.RC / rb.C if rb.C else -100.0
        if rc_pct < 15:
            lignes = [M["RCfaible"] if rc_pct >= 0 else M["RCnegative"]]
            avert = False
            if q_immediat > 0.33 * q_entrant and q_entrant > 600:
                lignes.append(M["RC1"])
                avert = True
            if 6 < le < min(pg.LEU, 9) and q_entrant > 0.5 * rb.QG:
                lignes.append(M["RC3"] + (M["RC3p"] if mil != RC else ""))
                avert = True
            if le < min(pg.LEU, 6) and q_entrant > 0.5 * rb.QG:
                lignes.append(M["RC2"] + (M["RC2p"] if mil != RC else ""))
                avert = True
            if le > pg.LEU:
                lignes.append(M["RC4"])
                avert = True
            if res.params_branches[k].KS > 0.5 and 300 < q_sortant < q_tournant:
                lignes.append(M["RC5"])
                avert = True
            if not avert:
                lignes.append(M["RC6"])
            add("\n".join(lignes), k)
        if any((uvp[k][j] or 0) >= 1000 for j in range(g.n)):
            add(M["RC11"], k)
        if rc_pct > 50 and 6 < le < 9 and q_entrant < 1000:
            add(M["RC12"] if mil != CV else M["RC13"], k)
        if rc_pct > 50 and le >= 9:
            add(M["RC14"], k)
        # Temps moyen d'attente
        tma = rb.TMA
        if tma >= 120 and mil != RC:
            add(M["TMA2"], k)
        elif tma >= 60 and mil != RC:
            add(M["TMA1"], k)
        elif tma >= 40 and mil == RC:
            add(M["TMA2"], k)
        elif tma >= 20 and mil == RC:
            add(M["TMA1"], k)
        # Longueurs de stockage
        lk, lkm = rb.LK, rb.LKM
        if lk >= 40 and mil != RC:
            add(M["LK4"], k)
        elif lk >= 20 and mil != RC:
            add(M["LK3"], k)
        elif lk >= 20 and mil == RC:
            add(M["LK2"], k)
        elif lk >= 10 and mil == RC:
            add(M["LK1"], k)
        if lkm >= 30 and lk < 20 and mil != RC:
            add(M["LK6"], k)
        elif lkm >= 25 and lk < 10 and mil == RC:
            add(M["LK5"], k)
    return out
