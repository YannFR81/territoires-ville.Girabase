"""Schéma de principe du giratoire (vue graphique), avec diagramme de flux et réserves de capacité."""
from __future__ import annotations

import math
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics, QImage, QPainter, QPainterPath, QPen, QTransform
from PySide6.QtWidgets import (QGraphicsEllipseItem, QGraphicsPathItem, QGraphicsScene, QGraphicsSimpleTextItem,
                               QGraphicsView)

from ..calcul import Flux, ResultatPeriode
from ..formats import niveau_rc
from ..geometrie import Primitive, emprise, primitives_flux, schema
from ..modele import Giratoire

# Charte graphique du Tarn : lie-de-vin, orange, vert, bleu pastel
COULEURS_RC = {"sature": "#7F0541", "faible": "#DD590A", "correct": "#179D87", "surdim": "#5E99C5"}


def couleurs_theme(sombre: bool) -> dict[str, QColor]:
    if sombre:
        return {"fond": QColor("#1f2329"), "trait": QColor("#d8dde3"), "ilot": QColor("#2f5e3a"),
                "anneau": QColor("#3a3f47"), "bande": QColor("#4b515a"), "axe": QColor("#e06c5f"),
                "texte": QColor("#f0f2f4"), "flux": QColor(88, 160, 255, 150)}
    return {"fond": QColor("#ffffff"), "trait": QColor("#2b2f33"), "ilot": QColor("#c9e4c5"),
            "anneau": QColor("#eceff2"), "bande": QColor("#d5d9de"), "axe": QColor("#c0392b"),
            "texte": QColor("#1b1e21"), "flux": QColor(31, 111, 209, 120)}


def construire_scene(scene: QGraphicsScene, g: Giratoire, res: Optional[ResultatPeriode] = None,
                     fl: Optional[Flux] = None, sombre: bool = False, textes_fixes: bool = True,
                     echelle_texte: float = 1.0) -> None:
    scene.clear()
    c = couleurs_theme(sombre)
    scene.setBackgroundBrush(QBrush(c["fond"]))
    if g.n < 1:
        return
    pen = QPen(c["trait"], 0)
    pen.setCosmetic(True)
    pen.setWidthF(1.4)
    rg = g.Rg
    # Surfaces : chaussée annulaire, bande franchissable, îlot central
    disque = QGraphicsEllipseItem(-rg, -rg, 2 * rg, 2 * rg)
    disque.setBrush(QBrush(c["anneau"]))
    disque.setPen(Qt.NoPen)
    scene.addItem(disque)
    if g.Bf > 0:
        r = g.R + g.Bf
        e = QGraphicsEllipseItem(-r, -r, 2 * r, 2 * r)
        e.setBrush(QBrush(c["bande"]))
        e.setPen(Qt.NoPen)
        scene.addItem(e)
    if g.R > 0:
        e = QGraphicsEllipseItem(-g.R, -g.R, 2 * g.R, 2 * g.R)
        e.setBrush(QBrush(c["ilot"]))
        e.setPen(Qt.NoPen)
        scene.addItem(e)

    police = QFont()
    police.setPointSizeF(9)
    police_num = QFont(police)
    police_num.setBold(True)

    def texte(t: str, x: float, y: float, couleur: QColor, f: QFont = police, fond: Optional[QColor] = None):
        it = QGraphicsSimpleTextItem(t)
        it.setFont(f)
        it.setBrush(QBrush(couleur))
        if textes_fixes:
            it.setFlag(QGraphicsSimpleTextItem.ItemIgnoresTransformations, True)
        br = it.boundingRect()
        if fond is not None:
            pad = 3
            bg = scene.addRect(QRectF(br.x() - pad, br.y() - pad, br.width() + 2 * pad, br.height() + 2 * pad),
                               QPen(Qt.NoPen), QBrush(fond))
            bg.setFlag(QGraphicsSimpleTextItem.ItemIgnoresTransformations, textes_fixes)
            bg.setPos(x, -y)
            bg.setTransform(_centrage(br, 1.0 if textes_fixes else echelle_texte))
            bg.setZValue(9)
        it.setPos(x, -y)
        it.setTransform(_centrage(br, 1.0 if textes_fixes else echelle_texte))
        it.setZValue(10)
        scene.addItem(it)

    if fl is not None:
        _dessiner_flux(scene, primitives_flux(g, fl.entrants, fl.sortants, fl.anneau), c, texte)

    for p in schema(g):
        if p.type == "texte":
            continue
        if p.type == "cercle":
            q = QPen(pen)
            if p.style == "tirets":
                q.setStyle(Qt.DashLine)
            e = QGraphicsEllipseItem(-p.rayon, -p.rayon, 2 * p.rayon, 2 * p.rayon)
            e.setPen(q)
            e.setZValue(2)
            scene.addItem(e)
            continue
        path = QPainterPath(QPointF(p.points[0][0], -p.points[0][1]))
        for x, y in p.points[1:]:
            path.lineTo(x, -y)
        q = QPen(pen)
        if p.style == "axe":
            q = QPen(c["axe"], 0)
            q.setCosmetic(True)
            q.setStyle(Qt.DashDotLine)
        item = QGraphicsPathItem(path)
        item.setPen(q)
        if p.calque == "GIRA_ILOTS_SEPARATEURS":
            path.closeSubpath()
            item.setPath(path)
            item.setBrush(QBrush(c["ilot"]))
        item.setZValue(3)
        scene.addItem(item)

    # Noms et numéros des branches, réserve de capacité
    from ..geometrie import longueur_ilot
    from ..constantes import LONGUEUR_BRANCHE_DESSIN
    for k, b in enumerate(g.branches):
        th = g.angle_rad(k)
        lil = longueur_ilot(b.li) if not (b.entree_nulle or b.sortie_nulle) else 0.0
        xfin = rg + max(LONGUEUR_BRANCHE_DESSIN, lil + 4) + 4
        nom = f"{k + 1}. {b.nom}"
        fond = QColor(c["fond"])
        couleur = c["texte"]
        if res is not None and res.complete and k < len(res.branches) and not b.entree_nulle:
            rb = res.branches[k]
            pct = rb.RC_pct
            if pct is not None:
                nom += f"\nRC {pct:.0f} %"
                fond = QColor(COULEURS_RC[niveau_rc(pct)])
                couleur = QColor("#ffffff")
        texte(nom, xfin * math.cos(th), xfin * math.sin(th), couleur, police_num, fond)
    m = emprise(g) + 6
    scene.setSceneRect(QRectF(-m, -m, 2 * m, 2 * m))


def _centrage(br: QRectF, echelle: float) -> QTransform:
    """Centre le texte sur sa position puis le met à l'échelle (translation exprimée avant l'échelle)."""
    return QTransform().scale(echelle, echelle).translate(-br.width() / 2, -br.height() / 2)


def _dessiner_flux(scene: QGraphicsScene, prims: list[Primitive], c: dict, texte) -> None:
    for p in prims:
        q = QPen(c["flux"], p.epaisseur)
        q.setCapStyle(Qt.FlatCap)
        if p.type == "arc":
            r = p.rayon
            path = QPainterPath()
            a0, a1 = math.degrees(p.angle_debut), math.degrees(p.angle_fin)
            path.arcMoveTo(QRectF(-r, -r, 2 * r, 2 * r), a0)
            path.arcTo(QRectF(-r, -r, 2 * r, 2 * r), a0, a1 - a0)
            item = QGraphicsPathItem(path)
            am = (p.angle_debut + p.angle_fin) / 2
            pos = (r * math.cos(am), r * math.sin(am))
        else:
            (x1, y1), (x2, y2) = p.points
            path = QPainterPath(QPointF(x1, -y1))
            path.lineTo(x2, -y2)
            item = QGraphicsPathItem(path)
            pos = (x1 + 0.6 * (x2 - x1), y1 + 0.6 * (y2 - y1))
        item.setPen(q)
        item.setZValue(4)
        scene.addItem(item)
        texte(p.texte, pos[0], pos[1], QColor("#0b3d91") if c["fond"].lightness() > 128 else QColor("#cfe3ff"))


class VueSchema(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self._zoom_utilisateur = False
        self.setMinimumSize(320, 320)

    def sombre(self) -> bool:
        return self.palette().window().color().lightness() < 110

    def afficher(self, g: Giratoire, res: Optional[ResultatPeriode], fl: Optional[Flux]) -> None:
        self._g = g
        construire_scene(self.scene(), g, res, fl, sombre=self.sombre())
        if not self._zoom_utilisateur:
            self.ajuster()

    def ajuster(self) -> None:
        """Cadre le schéma en laissant la place aux étiquettes, dont la taille est fixe à l'écran."""
        self._zoom_utilisateur = False
        g = getattr(self, "_g", None)
        if g is None or g.n == 0:
            self.fitInView(self.scene().sceneRect(), Qt.KeepAspectRatio)
            return
        police = QFont()
        police.setPointSizeF(9)
        police.setBold(True)
        fm = QFontMetrics(police)
        l_px = max(fm.horizontalAdvance(f"{k + 1}. {b.nom}") for k, b in enumerate(g.branches)) + 12
        vue = max(1, min(self.viewport().width(), self.viewport().height()))
        e0 = emprise(g) + 6
        ratio = min(l_px / vue, 0.45)
        e = max(e0, (e0 - 12) / (1 - ratio))
        self.scene().setSceneRect(QRectF(-e, -e, 2 * e, 2 * e))
        self.fitInView(self.scene().sceneRect(), Qt.KeepAspectRatio)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        if not self._zoom_utilisateur:
            self.ajuster()

    def wheelEvent(self, ev):
        f = 1.15 if ev.angleDelta().y() > 0 else 1 / 1.15
        self.scale(f, f)
        self._zoom_utilisateur = True

    def mouseDoubleClickEvent(self, ev):
        self.ajuster()


def image_schema(g: Giratoire, res: Optional[ResultatPeriode], fl: Optional[Flux], taille: int = 1400) -> QImage:
    scene = QGraphicsScene()
    largeur_m = 2 * (emprise(g) + 6)
    # Textes d environ 2 % de la largeur de l image, quelle que soit la taille du giratoire
    echelle = 0.021 * largeur_m / 12
    construire_scene(scene, g, res, fl, sombre=False, textes_fixes=False, echelle_texte=echelle)
    img = QImage(taille, taille, QImage.Format_ARGB32)
    img.fill(QColor("#ffffff"))
    painter = QPainter(img)
    painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
    scene.render(painter, QRectF(0, 0, taille, taille), scene.sceneRect())
    painter.end()
    return img
