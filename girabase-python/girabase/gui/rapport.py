"""Note de calcul (PDF ou impression)."""
from __future__ import annotations

import datetime as _dt
import html
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QMarginsF, QRectF, QSizeF, Qt, QUrl
from PySide6.QtGui import QColor, QFont, QImage, QPageLayout, QPageSize, QPainter, QPdfWriter, QPen, QTextDocument

from .. import DEVISE, formats as F
from ..calcul import ResultatPeriode, flux
from ..conseils import remarques_conception, remarques_fonctionnement, remarques_trafics
from ..constantes import TE, TF1, TG, Milieu
from ..modele import Giratoire
from .courbe import image_courbe
from .onglet_resultats import points_courbe
from .schema import COULEURS_RC, image_schema

ORANGE, BLEU, VERT, LIE = "#DD590A", "#5E99C5", "#179D87", "#7F0541"


@dataclass
class EnteteRapport:
    """En-tête et pied de la note de calcul, modifiables dans Fichier > Paramètres de la note de calcul
    (organisme et service de la collectivité, par exemple)."""
    organisme: str = "Girabase — capacité des carrefours giratoires"
    service: str = DEVISE
    auteur: str = ""
    pied: str = ""


def _e(t: object) -> str:
    return html.escape(str(t))


def _n(x: float, d: int = 2) -> str:
    return F.nombre(x, d)


def _table(entetes: list[str], lignes: list[list[str]], largeurs: Optional[list[int]] = None,
           align_premiere_gauche: bool = True) -> str:
    th = "".join(f'<th bgcolor="{BLEU}" style="color:#ffffff;">{h}</th>' for h in entetes)
    corps = []
    for i, ligne in enumerate(lignes):
        fond = "#f4f7fa" if i % 2 else "#ffffff"
        tds = []
        for j, v in enumerate(ligne):
            align = "left" if (j == 0 and align_premiere_gauche) else "right"
            tds.append(f'<td align="{align}" bgcolor="{fond}">{v}</td>')
        corps.append("<tr>" + "".join(tds) + "</tr>")
    return ('<table width="100%" cellspacing="0" cellpadding="3" border="0.5" style="border-color:#c8d3dd;">'
            f"<tr>{th}</tr>{''.join(corps)}</table>")


def _remarques(g: Giratoire, rems) -> str:
    if not rems:
        return "<p><i>Aucune remarque.</i></p>"
    blocs: dict = {}
    for r in rems:
        blocs.setdefault(r.branche, []).append(_e(r.texte).replace("\n", "<br/>"))
    out = []
    if None in blocs:
        out.append("<p><b>Giratoire</b></p><ul>" + "".join(f"<li>{t}</li>" for t in blocs.pop(None)) + "</ul>")
    for k in sorted(blocs):
        out.append(f"<p><b>Branche {k + 1} — {_e(g.branches[k].nom)}</b></p><ul>"
                   + "".join(f"<li>{t}</li>" for t in blocs[k]) + "</ul>")
    return "".join(out)


def construire_document(g: Giratoire, resultats: list[ResultatPeriode], entete: EnteteRapport,
                        largeur_px: float) -> QTextDocument:
    doc = QTextDocument()
    police = QFont("Arial")
    police.setPointSizeF(9)
    doc.setDefaultFont(police)
    doc.setDefaultStyleSheet(
        f"h1 {{ color:{ORANGE}; font-size:17pt; margin-bottom:2px; }}"
        f"h2 {{ color:{ORANGE}; font-size:12.5pt; margin-top:14px; border-bottom:1px solid {ORANGE}; }}"
        f"h3 {{ color:{LIE}; font-size:10.5pt; margin-top:10px; }}"
        "td, th { font-size:8.5pt; } p { margin:2px 0; } li { margin:1px 0; }"
        ".note { color:#555555; font-size:8pt; }")
    img_l = int(largeur_px)

    def ajouter_image(nom: str, img: QImage) -> None:
        doc.addResource(QTextDocument.ImageResource, QUrl(nom), img)

    milieu = g.milieu.libelle if g.milieu is not None else "non défini"
    h = [f"<h1>Capacité du carrefour giratoire — {_e(g.nom)}</h1>",
         f"<p><b>Variante :</b> {_e(g.variante)} &nbsp;&nbsp; <b>Environnement :</b> {_e(milieu)} &nbsp;&nbsp; "
         f"<b>Date :</b> {_dt.date.today():%d/%m/%Y}"
         + (f" &nbsp;&nbsp; <b>Établi par :</b> {_e(entete.auteur)}" if entete.auteur else "") + "</p>"]
    if g.localisation.strip():
        h.append(f"<p><b>Localisation :</b> {_e(g.localisation).replace(chr(10), '<br/>')}</p>")

    # Synthèse
    h.append("<h2>Synthèse</h2>")
    lignes = []
    for res in resultats:
        if not res.complete:
            lignes.append([_e(res.periode.nom), "période incomplète", "", ""])
            continue
        entrees = [b for b in res.branches if not b.entree_nulle]
        pire = min(entrees, key=lambda b: b.RC_pct if b.RC_pct is not None else 1e9)
        pct = pire.RC_pct or 0.0
        coul = COULEURS_RC[F.niveau_rc(pct)]
        lignes.append([_e(res.periode.nom), f"{res.total_entrant} uvp/h",
                       f"{pire.index + 1}. {_e(pire.nom)}",
                       f'<font color="{coul}"><b>{F.nombre(pct)} %</b></font>'])
    h.append(_table(["Période", "Trafic total entrant", "Entrée la plus chargée", "Réserve de capacité mini"],
                    lignes))
    h.append('<p class="note">Lecture (aide Girabase) : en heure de pointe, le bon fonctionnement correspond à une '
             'réserve de capacité de 25 à 80 % sur toutes les entrées ; entre 5 et 25 %, des files d\'attente '
             'assez longues sont possibles aux hyper-pointes ; sous 5 %, et a fortiori en réserve négative, de fortes '
             'perturbations sont à craindre.</p>')

    # Géométrie
    h.append("<h2>1. Géométrie</h2>")
    try:
        pg = resultats[0].params if resultats else None
    except IndexError:
        pg = None
    anneau = [["Rayon de l'îlot infranchissable R", f"{_n(g.R)} m"],
              ["Largeur de la bande franchissable Bf", f"{_n(g.Bf)} m"],
              ["Largeur de l'anneau LA", f"{_n(g.LA)} m"],
              ["Rayon extérieur Rg", f"{_n(g.Rg)} m"]]
    if pg is not None:
        anneau += [["Rayon utile RU / anneau utile LAU", f"{_n(pg.RU)} m / {_n(pg.LAU)} m"],
                   ["Largeur d'entrée utile maximale LEU", f"{_n(pg.LEU)} m"],
                   ["Largeur d'îlot maximale utile LImax", f"{_n(pg.LImax)} m"]]
    h.append(_table(["Anneau", "Valeur"], anneau))
    u = "°" if g.unite_angle.libelle == "degrés" else " gr"
    lb = []
    for k, b in enumerate(g.branches):
        ecart = "" if k == 0 else f"{b.angle - g.branches[k - 1].angle}{u}"
        lb.append([f"{k + 1}. {_e(b.nom)}", f"{b.angle}{u}", ecart, "oui" if b.rampe else "",
                   "oui" if b.tad else "", _n(b.le4), _n(b.le15) if b.evasee else "", _n(b.li), _n(b.ls)])
    h.append("<p></p>" + _table(["Branche", "Angle", "Écart", "Rampe &gt;3 %", "TAD", "Entrée 4 m (m)",
                                 "Entrée 15 m (m)", "Îlot (m)", "Sortie (m)"], lb))

    # Conception
    h.append("<h2>2. Remarques de conception</h2>")
    h.append(_remarques(g, remarques_conception(g, resultats[0] if resultats else None)))

    # Périodes
    for idx, res in enumerate(resultats):
        p = res.periode
        titre = f"{idx + 3}. Période « {_e(p.nom)} »"
        if p.branche_saturee is not None:
            titre += f" — branche {p.branche_saturee + 1} saturée (trafic entrant limité à sa capacité)"
        h.append(f'<h2 style="page-break-before:always;">{titre}</h2>')
        nom_img = f"schema_{idx}.png"
        ajouter_image(nom_img, image_schema(g, res if res.complete else None, flux(g, p), 1300))
        h.append(f'<p align="center"><img src="{nom_img}" width="{int(img_l * 0.56)}"/></p>')
        h.append('<p class="note" align="center">Diagramme de flux (uvp/h, hors voies directes de tourne-à-droite) '
                 'et réserve de capacité par entrée.</p>')
        uvp = p.matrice_uvp()
        noms = [f"{k + 1}" for k in range(g.n)]
        lm = []
        for i in range(g.n):
            row = [("—" if (g.branches[i].entree_nulle or g.branches[j].sortie_nulle) else
                    ("" if uvp[i][j] is None else str(uvp[i][j]))) for j in range(g.n)]
            lm.append([f"{i + 1}. {_e(g.branches[i].nom)}"] + row + [f"<b>{sum(v or 0 for v in uvp[i])}</b>"])
        lm.append(["<b>Total sortant</b>"] + [f"<b>{sum((uvp[i][j] or 0) for i in range(g.n))}</b>"
                                               for j in range(g.n)] + [f"<b>{p.total()}</b>"])
        lm.append(["Piétons (p/h)"] + ["" if v is None else str(v) for v in p.pietons] + [""])
        h.append("<h3>Trafics (uvp/h)" + ("" if p.mode_uvp else " — saisis par catégorie : 1 PL = 2 uvp, "
                                          "1 2R = 0,5 uvp") + "</h3>")
        h.append(_table(["Origine \\ destination"] + noms + ["Total entrant"], lm))
        h.append("<h3>Résultats</h3>")
        if not res.complete:
            h.append("<p>Les trafics de cette période sont incomplets : pas de résultat.</p>")
            continue
        lr = []
        for rb in res.branches:
            nom = f"{rb.index + 1}. {_e(rb.nom)}"
            if rb.entree_nulle:
                lr.append([nom, str(rb.QE), "sortie seule", "", "", "", "", "", "", ""])
                continue
            coul = COULEURS_RC[F.niveau_rc(rb.RC_pct)]
            lr.append([nom, str(rb.QEntrant), str(rb.QG), F.nombre(rb.C), f'<font color="{coul}"><b>{F.rc(rb)}</b></font>',
                       f'<font color="{coul}"><b>{F.rc_pct(rb)}</b></font>', F.lk(rb), F.lkm(rb), F.tma(rb),
                       F.tta(rb)])
        h.append(_table(["Branche", "Trafic entrant", "Trafic gênant", "Capacité", "Réserve (uvp/h)", "Réserve (%)",
                         "File moy.", "File max.", "Attente moy.", "Attente totale"], lr))
        if any(b.le4 >= 6 for b in g.branches):
            h.append('<p class="note">Files exprimées en véhicules pour l\'ensemble de l\'entrée : pour une entrée '
                     'à plusieurs voies, diviser par le nombre de voies pour obtenir la longueur de file.</p>')
        h.append("<h3>Fonctionnement</h3>" + _remarques(g, remarques_fonctionnement(g, res)))
        rt = remarques_trafics(g, res)
        if rt:
            h.append("<h3>Remarques sur les trafics</h3>" + _remarques(g, rt))


    # Courbes
    reelles = [r for r in resultats if r.periode.branche_saturee is None and r.complete]
    if reelles:
        h.append(f'<h2 style="page-break-before:always;">{len(resultats) + 3}. Courbes de capacité</h2>')
        h.append('<p class="note">Capacité de chaque entrée en fonction du trafic gênant ; chaque point représente '
                 'une période (trafic entrant ramené hors effet piéton). Un point au-dessus de la courbe signale une '
                 'entrée saturée.</p>')
        cellules = []
        ref = reelles[0]
        for k, b in enumerate(g.branches):
            if b.entree_nulle:
                continue
            nom_img = f"courbe_{k}.png"
            ajouter_image(nom_img, image_courbe(f"Branche {k + 1} — {b.nom}", ref.params, ref.params_branches[k],
                                                points_courbe(g, reelles, k), 900, 600))
            cellules.append(f'<td align="center"><img src="{nom_img}" width="{int(img_l * 0.47)}"/></td>')
        lignes_c = ["<tr>" + "".join(cellules[i:i + 2]) + "</tr>" for i in range(0, len(cellules), 2)]
        h.append('<table width="100%" cellspacing="4">' + "".join(lignes_c) + "</table>")

    # Méthode
    h.append("<h2>Annexe — Méthode</h2>")
    h.append("<p>Calcul selon la méthode GIRABASE 4 (CERTU, CETE de l'Ouest) : la capacité d'une entrée dépend "
             "du trafic gênant au droit de l'entrée (trafic tournant pondéré selon sa position sur l'anneau et "
             "part du trafic sortant), de la largeur d'entrée et de la traversée des piétons. "
             "Capacité Cvh = 3600 / Tf · exp(−Qg / 3600 · (Tg − Tf / 2)) · (LE / 3,5)<sup>Te</sup>.</p>")
    coefs = [[m.libelle, _n(TG[m]), _n(TF1[m]), _n(TE[m])] for m in Milieu]
    h.append(_table(["Environnement", "Tg (s)", "Tf (s)", "Te"], coefs))
    h.append('<p class="note">Tf majoré de 35 % en cas de rampe supérieure à 3 % ; coefficients de rase campagne '
             'pour les mini-giratoires. Calcul effectué avec le portage Python (licence GNU GPL v3) du code source '
             'GIRABASE 4 publié par le CEREMA.</p>')
    doc.setHtml("".join(h))
    return doc


def _peindre_pages(painter: QPainter, device, doc: QTextDocument, rect_page: QRectF, entete: EnteteRapport,
                   titre: str, echelle: float) -> int:
    """Pagination manuelle avec en-tête et pied de page à chaque page."""
    h_ent, h_pied = 18 * echelle, 12 * echelle
    corps = QRectF(rect_page.left(), rect_page.top() + h_ent, rect_page.width(), rect_page.height() - h_ent - h_pied)
    doc.setPageSize(QSizeF(corps.width(), corps.height()))
    nb = doc.pageCount()
    f = QFont("Arial")
    for page in range(nb):
        if page:
            device.newPage()
        # En-tête : bandeau orange
        painter.save()
        painter.fillRect(QRectF(rect_page.left(), rect_page.top(), 6 * echelle, h_ent - 6 * echelle), QColor(ORANGE))
        f.setPointSizeF(9)
        f.setBold(True)
        painter.setFont(f)
        painter.setPen(QColor(ORANGE))
        painter.drawText(QRectF(rect_page.left() + 10 * echelle, rect_page.top(), rect_page.width(), 7 * echelle),
                         Qt.AlignLeft | Qt.AlignVCenter,
                         entete.organisme or "Girabase — capacité des carrefours giratoires")
        f.setBold(False)
        f.setPointSizeF(8)
        painter.setFont(f)
        painter.setPen(QColor("#444444"))
        painter.drawText(QRectF(rect_page.left() + 10 * echelle, rect_page.top() + 6 * echelle, rect_page.width(),
                                6 * echelle), Qt.AlignLeft | Qt.AlignVCenter, entete.service)
        painter.drawText(QRectF(rect_page.left(), rect_page.top(), rect_page.width(), 7 * echelle),
                         Qt.AlignRight | Qt.AlignVCenter, titre)
        painter.setPen(QPen(QColor(ORANGE), 0.4 * echelle))
        painter.drawLine(rect_page.left(), rect_page.top() + h_ent - 4 * echelle,
                         rect_page.right(), rect_page.top() + h_ent - 4 * echelle)
        # Pied
        yp = rect_page.bottom() - h_pied + 4 * echelle
        painter.setPen(QPen(QColor(BLEU), 0.3 * echelle))
        painter.drawLine(rect_page.left(), yp, rect_page.right(), yp)
        painter.setPen(QColor("#444444"))
        painter.drawText(QRectF(rect_page.left(), yp, rect_page.width(), 7 * echelle),
                         Qt.AlignLeft | Qt.AlignVCenter, entete.pied)
        painter.drawText(QRectF(rect_page.left(), yp, rect_page.width(), 7 * echelle),
                         Qt.AlignHCenter | Qt.AlignVCenter, "Calcul Girabase (portage Python, GPL)")
        painter.drawText(QRectF(rect_page.left(), yp, rect_page.width(), 7 * echelle),
                         Qt.AlignRight | Qt.AlignVCenter, f"Page {page + 1} / {nb}")
        painter.restore()
        # Corps
        painter.save()
        painter.translate(corps.left(), corps.top() - page * corps.height())
        doc.drawContents(painter, QRectF(0, page * corps.height(), corps.width(), corps.height()))
        painter.restore()
    return nb


def exporter_pdf(g: Giratoire, resultats: list[ResultatPeriode], chemin: str,
                 entete: Optional[EnteteRapport] = None) -> int:
    entete = entete or EnteteRapport()
    writer = QPdfWriter(chemin)
    writer.setResolution(300)
    writer.setPageLayout(QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Portrait, QMarginsF(14, 12, 14, 12),
                                     QPageLayout.Millimeter))
    writer.setTitle(f"Capacité giratoire — {g.nom}")
    writer.setCreator("Girabase (portage Python)")
    painter = QPainter(writer)
    rect = QRectF(writer.pageLayout().paintRectPixels(writer.resolution()))
    rect.moveTo(0, 0)
    echelle = writer.resolution() / 25.4          # pixels par mm
    doc = construire_document(g, resultats, entete, rect.width() * 96 / writer.resolution())
    doc.documentLayout().setPaintDevice(writer)
    nb = _peindre_pages(painter, writer, doc, rect, entete, f"{g.nom} — {g.variante}", echelle)
    painter.end()
    return nb


def imprimer(g: Giratoire, resultats: list[ResultatPeriode], printer, entete: Optional[EnteteRapport] = None) -> None:
    entete = entete or EnteteRapport()
    painter = QPainter(printer)
    rect = QRectF(printer.pageLayout().paintRectPixels(printer.resolution()))
    rect.moveTo(0, 0)
    echelle = printer.resolution() / 25.4
    doc = construire_document(g, resultats, entete, rect.width() * 96 / printer.resolution())
    doc.documentLayout().setPaintDevice(printer)
    _peindre_pages(painter, printer, doc, rect, entete, f"{g.nom} — {g.variante}", echelle)
    painter.end()
