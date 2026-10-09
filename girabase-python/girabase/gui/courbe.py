"""Courbe de capacité d'une entrée (Résultats.frm, CourbeCapacité)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from ..calcul import ParametresBranche, ParametresGiratoire, courbe_capacite

QG_MAX, QE_MAX = 2700, 1800


@dataclass
class PointPeriode:
    nom: str
    couleur: str
    qg: float
    qe: float      # trafic entrant ramené hors effet piéton : QE / (1 - Cp)


def dessiner_courbe(p: QPainter, rect: QRectF, titre: str, pg: Optional[ParametresGiratoire],
                    pb: Optional[ParametresBranche], points: list[PointPeriode], sombre: bool = False) -> None:
    fond = QColor("#1f2329") if sombre else QColor("#ffffff")
    trait = QColor("#d8dde3") if sombre else QColor("#2b2f33")
    grille = QColor("#3a3f47") if sombre else QColor("#e3e6ea")
    p.fillRect(rect, fond)
    f = QFont(p.font())
    f.setPointSizeF(max(7.0, rect.height() / 45))
    p.setFont(f)
    fm = p.fontMetrics()
    mg, md, mh, mb = fm.horizontalAdvance("00000") + 10, 16, fm.height() * 2 + 6, fm.height() * 2 + 10
    zone = QRectF(rect.left() + mg, rect.top() + mh, rect.width() - mg - md, rect.height() - mh - mb)

    def X(q: float) -> float:
        return zone.left() + zone.width() * q / QG_MAX

    def Y(q: float) -> float:
        return zone.bottom() - zone.height() * min(q, QE_MAX * 1.04) / QE_MAX

    p.setPen(QPen(trait))
    p.drawText(QRectF(rect.left(), rect.top() + 2, rect.width(), fm.height()), Qt.AlignHCenter, titre)
    for q in range(0, QG_MAX + 1, 100):
        p.setPen(QPen(grille, 1))
        p.drawLine(QPointF(X(q), zone.top()), QPointF(X(q), zone.bottom()))
        if q % 500 == 0:
            p.setPen(QPen(trait))
            p.drawText(QRectF(X(q) - 30, zone.bottom() + 3, 60, fm.height()), Qt.AlignHCenter, str(q))
    for q in range(0, QE_MAX + 1, 100):
        p.setPen(QPen(grille, 1))
        p.drawLine(QPointF(zone.left(), Y(q)), QPointF(zone.right(), Y(q)))
        if q % 500 == 0:
            p.setPen(QPen(trait))
            p.drawText(QRectF(rect.left(), Y(q) - fm.height() / 2, mg - 6, fm.height()),
                       Qt.AlignRight | Qt.AlignVCenter, str(q))
    p.setPen(QPen(trait, 1.2))
    p.drawLine(QPointF(zone.left(), zone.bottom()), QPointF(zone.right(), zone.bottom()))
    p.drawLine(QPointF(zone.left(), zone.bottom()), QPointF(zone.left(), zone.top()))
    p.drawText(QRectF(zone.left(), zone.bottom() + fm.height() + 4, zone.width(), fm.height()),
               Qt.AlignHCenter, "Trafic gênant (uvp/h)")
    p.drawText(QRectF(rect.left() + 4, rect.top() + fm.height() + 4, zone.width(), fm.height()),
               Qt.AlignLeft, "Trafic entrant (uvp/h)")
    if pg is None or pb is None:
        return
    p.setRenderHint(QPainter.Antialiasing, True)
    path = QPainterPath()
    premier = True
    for qg, cvh in courbe_capacite(pb, pg):
        pt = QPointF(X(qg), Y(cvh))
        if cvh > QE_MAX:
            premier = True
            continue
        if premier:
            path.moveTo(pt)
            premier = False
        else:
            path.lineTo(pt)
    p.setPen(QPen(QColor("#1f6fd1"), 2.2))
    p.drawPath(path)
    r = max(4.0, rect.height() / 90)
    for i, pt in enumerate(points):
        coul = QColor(pt.couleur)
        p.setPen(QPen(trait, 1))
        p.setBrush(QBrush(coul))
        y = Y(pt.qe)
        p.drawEllipse(QPointF(X(pt.qg), y), r, r)
        if pt.qe > QE_MAX:      # hors cadre : flèche vers le haut
            p.drawLine(QPointF(X(pt.qg), y - r), QPointF(X(pt.qg), y - 4 * r))
        p.setPen(QPen(coul))
        p.drawText(QPointF(zone.right() - fm.horizontalAdvance(pt.nom) - 6, zone.top() + (i + 1) * fm.height()),
                   pt.nom)
    p.setBrush(Qt.NoBrush)


class CourbeCapacite(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumHeight(260)
        self._args: tuple = ("", None, None, [])

    def afficher(self, titre: str, pg, pb, points: list[PointPeriode]) -> None:
        self._args = (titre, pg, pb, points)
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        sombre = self.palette().window().color().lightness() < 110
        dessiner_courbe(p, QRectF(self.rect()), *self._args, sombre=sombre)
        p.end()


def image_courbe(titre: str, pg, pb, points: list[PointPeriode], l: int = 900, h: int = 620) -> QImage:
    img = QImage(l, h, QImage.Format_ARGB32)
    img.fill(QColor("#ffffff"))
    p = QPainter(img)
    p.setRenderHint(QPainter.TextAntialiasing, True)
    dessiner_courbe(p, QRectF(0, 0, l, h), titre, pg, pb, points)
    p.end()
    return img
