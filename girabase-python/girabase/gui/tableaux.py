"""Tableaux de saisie : délégués numériques, copier-coller depuis Excel."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDoubleValidator, QGuiApplication, QIntValidator, QKeySequence
from PySide6.QtWidgets import (QAbstractItemView, QHeaderView, QLineEdit, QStyledItemDelegate, QTableWidget,
                               QTableWidgetItem)


def lire_reel(texte: str) -> Optional[float]:
    t = texte.strip().replace(",", ".").replace(" ", "").replace(" ", "")
    if not t:
        return None
    try:
        return float(t)
    except ValueError:
        return None


def lire_entier(texte: str) -> Optional[int]:
    v = lire_reel(texte)
    return None if v is None else int(round(v))


def fmt_reel(x: float) -> str:
    return f"{x:.2f}".rstrip("0").rstrip(".").replace(".", ",") if x == x else ""


class DelegueReel(QStyledItemDelegate):
    def __init__(self, mini: float, maxi: float, decimales: int = 2, parent=None):
        super().__init__(parent)
        self.mini, self.maxi, self.decimales = mini, maxi, decimales

    def createEditor(self, parent, option, index):
        ed = QLineEdit(parent)
        v = QDoubleValidator(self.mini, self.maxi, self.decimales, ed)
        v.setNotation(QDoubleValidator.StandardNotation)
        ed.setValidator(v)
        ed.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        return ed


class DelegueEntier(QStyledItemDelegate):
    def __init__(self, mini: int, maxi: int, parent=None):
        super().__init__(parent)
        self.mini, self.maxi = mini, maxi

    def createEditor(self, parent, option, index):
        ed = QLineEdit(parent)
        ed.setValidator(QIntValidator(self.mini, self.maxi, ed))
        ed.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        return ed


def item_nombre(texte: str, editable: bool = True) -> QTableWidgetItem:
    it = QTableWidgetItem(texte)
    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    if not editable:
        it.setFlags(it.flags() & ~Qt.ItemIsEditable)
    return it


def item_case(coche: bool, active: bool = True) -> QTableWidgetItem:
    it = QTableWidgetItem()
    flags = Qt.ItemIsUserCheckable | Qt.ItemIsSelectable
    if active:
        flags |= Qt.ItemIsEnabled
    it.setFlags(flags)
    it.setCheckState(Qt.Checked if coche else Qt.Unchecked)
    return it


class TableSaisie(QTableWidget):
    """Tableau avec copier (Ctrl+C), coller (Ctrl+V, depuis Excel) et effacement (Suppr)."""

    colle = Signal()

    def __init__(self, *args, reels: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.reels = reels
        self.setSelectionMode(QAbstractItemView.ContiguousSelection)
        self.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed
                             | QAbstractItemView.AnyKeyPressed)
        self.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.verticalHeader().setDefaultSectionSize(26)
        self.setAlternatingRowColors(True)

    def keyPressEvent(self, ev):
        if ev.matches(QKeySequence.Copy):
            self.copier()
            return
        if ev.matches(QKeySequence.Paste):
            self.coller()
            return
        if ev.key() in (Qt.Key_Delete, Qt.Key_Backspace) and self.state() != QAbstractItemView.EditingState:
            self.blockSignals(True)
            for it in self.selectedItems():
                if it.flags() & Qt.ItemIsEditable:
                    it.setText("")
            self.blockSignals(False)
            self.colle.emit()
            return
        super().keyPressEvent(ev)

    def copier(self) -> None:
        rng = self.selectedRanges()
        if not rng:
            return
        r = rng[0]
        lignes = []
        for i in range(r.topRow(), r.bottomRow() + 1):
            cel = []
            for j in range(r.leftColumn(), r.rightColumn() + 1):
                it = self.item(i, j)
                cel.append(it.text() if it else "")
            lignes.append("\t".join(cel))
        QGuiApplication.clipboard().setText("\n".join(lignes))

    def coller(self) -> None:
        texte = QGuiApplication.clipboard().text()
        if not texte:
            return
        i0, j0 = max(self.currentRow(), 0), max(self.currentColumn(), 0)
        self.blockSignals(True)
        for di, ligne in enumerate(texte.rstrip("\r\n").splitlines()):
            for dj, val in enumerate(ligne.split("\t")):
                i, j = i0 + di, j0 + dj
                if i >= self.rowCount() or j >= self.columnCount():
                    continue
                it = self.item(i, j)
                if it is None or not (it.flags() & Qt.ItemIsEditable):
                    continue
                if self.reels:
                    x = lire_reel(val)
                    it.setText("" if x is None else fmt_reel(max(x, 0.0)))
                else:
                    v = lire_entier(val)
                    it.setText("" if v is None else str(max(v, 0)))
        self.blockSignals(False)
        self.colle.emit()
