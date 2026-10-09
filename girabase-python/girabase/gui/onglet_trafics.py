"""Onglet « Trafics » : périodes, matrices origine-destination, piétons."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QMenu,
                               QPushButton, QRadioButton, QTableWidgetItem, QToolButton, QVBoxLayout, QWidget)

from ..constantes import AIDE_QP, Q_MAX, QP_MAX
from ..modele import Giratoire, Periode
from .tableaux import DelegueEntier, TableSaisie, item_nombre, lire_entier

CATEGORIES = [("vl", "VL"), ("pl", "PL"), ("dr", "2 roues"), ("uvp", "uvp (calculé)")]


class OngletTrafics(QWidget):
    modifie = Signal(bool)
    action = Signal(str)            # nouvelle, dupliquer, renommer, supprimer, inverser, multiplier, importer
    periode_changee = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.g: Optional[Giratoire] = None
        self.index = 0
        self.categorie = "vl"
        lay = QVBoxLayout(self)

        barre = QHBoxLayout()
        barre.addWidget(QLabel("Période"))
        self.combo = QComboBox()
        self.combo.setMinimumWidth(180)
        barre.addWidget(self.combo)
        for code, lib in (("nouvelle", "Nouvelle"), ("dupliquer", "Dupliquer"), ("renommer", "Renommer"),
                          ("supprimer", "Supprimer")):
            b = QPushButton(lib)
            b.clicked.connect(lambda _=False, c=code: self.action.emit(c))
            barre.addWidget(b)
        outils = QToolButton()
        outils.setText("Opérations")
        outils.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(outils)
        for code, lib in (("inverser", "Inverser la matrice (HPM ↔ HPS)"),
                          ("multiplier", "Multiplier les trafics…"),
                          ("importer", "Importer les trafics d'un autre projet…"),
                          ("completer", "Remplacer les cases vides par 0")):
            menu.addAction(lib, lambda c=code: self.action.emit(c))
        outils.setMenu(menu)
        barre.addWidget(outils)
        barre.addStretch()
        lay.addLayout(barre)

        mode = QHBoxLayout()
        self.groupe_mode = QButtonGroup(self)
        self.rb_uvp = QRadioButton("Saisie en uvp/h")
        self.rb_cat = QRadioButton("Saisie par catégorie (1 PL = 2 uvp, 1 2R = 0,5 uvp)")
        self.groupe_mode.addButton(self.rb_uvp, 1)
        self.groupe_mode.addButton(self.rb_cat, 0)
        mode.addWidget(self.rb_uvp)
        mode.addWidget(self.rb_cat)
        mode.addStretch()
        lay.addLayout(mode)

        self.barre_cat = QWidget()
        hc = QHBoxLayout(self.barre_cat)
        hc.setContentsMargins(0, 0, 0, 0)
        self.groupe_cat = QButtonGroup(self)
        for i, (code, lib) in enumerate(CATEGORIES):
            b = QPushButton(lib)
            b.setCheckable(True)
            b.setProperty("code", code)
            self.groupe_cat.addButton(b, i)
            hc.addWidget(b)
        hc.addStretch()
        lay.addWidget(self.barre_cat)

        grp = QGroupBox("Matrice origine → destination (lignes : entrées, colonnes : sorties)")
        v = QVBoxLayout(grp)
        self.table = TableSaisie(0, 0)
        self.table.setItemDelegate(DelegueEntier(0, Q_MAX, self))
        v.addWidget(self.table)
        self.info = QLabel()
        self.info.setObjectName("aide")
        self.info.setWordWrap(True)
        v.addWidget(self.info)
        lay.addWidget(grp, 3)

        grp2 = QGroupBox("Piétons traversant chaque branche (piétons/h, deux sens confondus)")
        v2 = QVBoxLayout(grp2)
        self.pietons = TableSaisie(1, 0)
        self.pietons.setItemDelegate(DelegueEntier(0, QP_MAX, self))
        self.pietons.setVerticalHeaderLabels(["Piétons"])
        self.pietons.setFixedHeight(64)
        self.pietons.setToolTip(AIDE_QP)
        v2.addWidget(self.pietons)
        lay.addWidget(grp2)

        self.combo.currentIndexChanged.connect(self._choix_periode)
        self.groupe_mode.idClicked.connect(self._mode)
        self.groupe_cat.idClicked.connect(self._cat)
        self.table.itemChanged.connect(self._cellule)
        self.table.colle.connect(self._colle)
        self.pietons.itemChanged.connect(self._pieton)
        self.pietons.colle.connect(self._colle_pietons)

    # ------------------------------------------------------------------
    def periode(self) -> Optional[Periode]:
        if self.g is None:
            return None
        reelles = self.g.periodes_reelles()
        if not reelles:
            return None
        return reelles[min(self.index, len(reelles) - 1)]

    def charger(self, g: Giratoire, index: Optional[int] = None) -> None:
        self.g = g
        reelles = g.periodes_reelles()
        if index is not None:
            self.index = index
        self.index = max(0, min(self.index, len(reelles) - 1))
        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItems([p.nom for p in reelles])
        self.combo.setCurrentIndex(self.index)
        self.combo.blockSignals(False)
        self._afficher()

    def _afficher(self) -> None:
        g, p = self.g, self.periode()
        n = g.n
        actif = p is not None
        for w in (self.table, self.pietons, self.rb_uvp, self.rb_cat):
            w.setEnabled(actif)
        if p is None:
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            self.info.setText("Aucune période de trafic : créez-en une avec « Nouvelle ».")
            return
        (self.rb_uvp if p.mode_uvp else self.rb_cat).setChecked(True)
        self.barre_cat.setVisible(not p.mode_uvp)
        if p.mode_uvp:
            cle = "uvp"
        else:
            cle = self.categorie
            self.groupe_cat.button([c for c, _ in CATEGORIES].index(cle)).setChecked(True)
        mat = p.matrice_uvp() if cle == "uvp" else getattr(p, cle)
        lecture_seule = (cle == "uvp" and not p.mode_uvp)
        noms = [f"{k + 1}. {b.nom}" for k, b in enumerate(g.branches)]
        t = self.table
        t.blockSignals(True)
        t.setRowCount(n + 1)
        t.setColumnCount(n + 1)
        t.setHorizontalHeaderLabels(noms + ["Total entrant"])
        t.setVerticalHeaderLabels(noms + ["Total sortant"])
        t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        gris = QBrush(QColor(128, 128, 128, 60))
        gras = QFont()
        gras.setBold(True)
        for i in range(n):
            for j in range(n):
                nul = g.branches[i].entree_nulle or g.branches[j].sortie_nulle
                v = mat[i][j]
                it = item_nombre("—" if nul else ("" if v is None else str(v)),
                                 editable=not (nul or lecture_seule))
                if nul:
                    it.setBackground(gris)
                    it.setToolTip("Mouvement impossible (entrée ou sortie de largeur nulle)")
                elif g.branches[i].tad and j == g.suivante(i):
                    it.setToolTip("Mouvement empruntant la voie directe de tourne-à-droite")
                    it.setForeground(QBrush(QColor("#7f8c8d")))
                    f = QFont()
                    f.setItalic(True)
                    it.setFont(f)
                elif v is not None and v > 1500:
                    it.setForeground(QBrush(QColor("#d68910")))
                    it.setToolTip("Le trafic est très important. Vérifiez vos données.")
                if i == j and not nul:
                    it.setToolTip("Demi-tour")
                t.setItem(i, j, it)
        self._totaux(mat)
        t.blockSignals(False)
        vides = p.cases_vides(g.branches)
        total = p.total()
        txt = f"Trafic total entrant : {total} uvp/h" + ("." if p.mode_uvp else " (toutes catégories).")
        if vides:
            txt += (f"  {vides} case(s) à renseigner (demi-tours compris) avant de pouvoir calculer cette période "
                    f"— menu Opérations › « Remplacer les cases vides par 0 ».")
        txt += "  Collez directement une matrice depuis Excel (Ctrl+V)."
        self.info.setText(txt)
        # Piétons
        pt = self.pietons
        pt.blockSignals(True)
        pt.setColumnCount(n)
        pt.setHorizontalHeaderLabels(noms)
        pt.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        for k in range(n):
            v = p.pietons[k]
            pt.setItem(0, k, item_nombre("" if v is None else str(v)))
        pt.blockSignals(False)

    def _totaux(self, mat) -> None:
        g, t = self.g, self.table
        n = g.n
        gras = QFont()
        gras.setBold(True)
        fond = QBrush(QColor(31, 111, 209, 30))
        for i in range(n):
            it = item_nombre(str(sum(v or 0 for v in mat[i])), editable=False)
            it.setFont(gras)
            it.setBackground(fond)
            t.setItem(i, n, it)
        for j in range(n):
            it = item_nombre(str(sum((mat[i][j] or 0) for i in range(n))), editable=False)
            it.setFont(gras)
            it.setBackground(fond)
            t.setItem(n, j, it)
        it = item_nombre(str(sum(v or 0 for row in mat for v in row)), editable=False)
        it.setFont(gras)
        it.setBackground(fond)
        t.setItem(n, n, it)

    # ------------------------------------------------------------------
    def _choix_periode(self, idx: int) -> None:
        self.index = max(idx, 0)
        self._afficher()
        self.periode_changee.emit(self.index)

    def _mode(self, ident: int) -> None:
        p = self.periode()
        if p is None or p.mode_uvp == bool(ident):
            return
        from PySide6.QtWidgets import QMessageBox
        if p.total() > 0:
            r = QMessageBox.question(self, "Changer de mode de saisie",
                                     "Les trafics véhicules de cette période vont être réinitialisés "
                                     "(les piétons sont conservés). Continuer ?")
            if r != QMessageBox.Yes:
                (self.rb_uvp if p.mode_uvp else self.rb_cat).setChecked(True)
                return
        p.basculer_mode()
        self.categorie = "vl"
        self._afficher()
        self.modifie.emit(False)

    def _cat(self, ident: int) -> None:
        self.categorie = CATEGORIES[ident][0]
        self._afficher()

    def _matrice_editee(self):
        p = self.periode()
        return p.uvp if p.mode_uvp else getattr(p, self.categorie)

    def _cellule(self, it: QTableWidgetItem) -> None:
        p = self.periode()
        n = self.g.n
        i, j = it.row(), it.column()
        if p is None or i >= n or j >= n or not (it.flags() & Qt.ItemIsEditable):
            return
        mat = self._matrice_editee()
        v = lire_entier(it.text())
        mat[i][j] = None if v is None else max(0, min(v, Q_MAX))
        self.modifie.emit(False)
        QTimer.singleShot(0, lambda: self._apres_edition(i, j))

    def _apres_edition(self, i: int, j: int) -> None:
        self._afficher()
        self.table.setCurrentCell(i, j)

    def _colle(self) -> None:
        p = self.periode()
        if p is None:
            return
        mat = self._matrice_editee()
        n = self.g.n
        for i in range(n):
            for j in range(n):
                it = self.table.item(i, j)
                if it is not None and it.flags() & Qt.ItemIsEditable:
                    v = lire_entier(it.text())
                    mat[i][j] = None if v is None else max(0, min(v, Q_MAX))
        self._afficher()
        self.modifie.emit(False)

    def _pieton(self, it: QTableWidgetItem) -> None:
        p = self.periode()
        if p is None:
            return
        v = lire_entier(it.text())
        p.pietons[it.column()] = None if v is None else max(0, min(v, QP_MAX))
        self.modifie.emit(False)

    def _colle_pietons(self) -> None:
        p = self.periode()
        if p is None:
            return
        for k in range(self.g.n):
            v = lire_entier(self.pietons.item(0, k).text())
            p.pietons[k] = None if v is None else max(0, min(v, QP_MAX))
        self.modifie.emit(False)
