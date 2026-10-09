"""Onglet « Géométrie » : anneau et caractéristiques des branches."""
from __future__ import annotations

from PySide6.QtCore import QLocale, Qt, QTimer, Signal
from PySide6.QtWidgets import (QAbstractItemView, QDoubleSpinBox, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout,
                               QHeaderView, QLabel, QVBoxLayout, QWidget)

from ..calcul import parametres_giratoire
from ..constantes import AIDE_BF, AIDE_LE4, AIDE_LS, BF_MAX, LE4_MAX, LS_MAX, R_MAX
from ..modele import Giratoire
from .tableaux import DelegueEntier, DelegueReel, TableSaisie, fmt_reel, item_case, item_nombre, lire_entier, lire_reel

COLS = ["Nom", "Angle", "Écart", "Rampe\n> 3 %", "Tourne-à-\ndroite", "Entrée\nà 4 m", "Entrée\névasée",
        "Entrée\nà 15 m", "Îlot\nséparateur", "Sortie"]
C_NOM, C_ANGLE, C_ECART, C_RAMPE, C_TAD, C_LE4, C_EVASEE, C_LE15, C_LI, C_LS = range(10)
FR = QLocale(QLocale.French, QLocale.France)


def spin(mini: float, maxi: float, pas: float = 0.5) -> QDoubleSpinBox:
    s = QDoubleSpinBox()
    s.setLocale(FR)
    s.setRange(mini, maxi)
    s.setDecimals(2)
    s.setSingleStep(pas)
    s.setSuffix(" m")
    s.setKeyboardTracking(False)
    s.setAlignment(Qt.AlignRight)
    return s


class OngletGeometrie(QWidget):
    modifie = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.g: Giratoire | None = None
        lay = QVBoxLayout(self)

        haut = QHBoxLayout()
        anneau = QGroupBox("Anneau")
        f = QFormLayout(anneau)
        f.setRowWrapPolicy(QFormLayout.DontWrapRows)
        self.R = spin(0, R_MAX)
        self.Bf = spin(0, BF_MAX, 0.25)
        self.LA = spin(0, 20)
        self.Rg = QLabel()
        self.Rg.setObjectName("valeur")
        self.R.setToolTip("Rayon de l'îlot central infranchissable (0 pour un mini-giratoire).")
        self.Bf.setToolTip(AIDE_BF)
        self.LA.setToolTip("Mesurée entre marquages (rase campagne) ou à défaut entre bordures.")
        f.addRow("Rayon de l'îlot infranchissable R", self.R)
        f.addRow("Bande franchissable Bf", self.Bf)
        f.addRow("Largeur de l'anneau LA", self.LA)
        f.addRow("Rayon extérieur Rg = R + Bf + LA", self.Rg)
        haut.addWidget(anneau, 3)

        params = QGroupBox("Paramètres de calcul")
        self.grille = QGridLayout(params)
        self.lbl_params: dict[str, QLabel] = {}
        noms = [("RU", "Rayon utile"), ("LAU", "Anneau utile"), ("LEU", "Entrée utile max."),
                ("LImax", "Îlot max. utile"), ("KE", "Gêne tournant ext."), ("KI", "Gêne tournant int."),
                ("Tg", "Créneau critique"), ("Tf1", "Créneau complém."), ("Te", "Exposant largeur")]
        for i, (cle, lib) in enumerate(noms):
            lab = QLabel(lib)
            lab.setObjectName("aide")
            val = QLabel("—")
            val.setObjectName("valeur")
            val.setToolTip(cle)
            self.grille.addWidget(QLabel(cle), i % 5, (i // 5) * 3)
            self.grille.addWidget(val, i % 5, (i // 5) * 3 + 1)
            self.grille.addWidget(lab, i % 5, (i // 5) * 3 + 2)
            self.lbl_params[cle] = val
        haut.addWidget(params, 2)
        lay.addLayout(haut)

        grp = QGroupBox("Branches (largeurs en mètres, angles comptés depuis la branche 1 dans le sens de giration)")
        v = QVBoxLayout(grp)
        self.table = TableSaisie(0, len(COLS), reels=True)
        self.table.setHorizontalHeaderLabels(COLS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(C_NOM, QHeaderView.Stretch)
        self.table.horizontalHeader().setMinimumSectionSize(64)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setItemDelegateForColumn(C_ANGLE, DelegueEntier(0, 399, self))
        self.table.setItemDelegateForColumn(C_ECART, DelegueEntier(1, 399, self))
        for c, maxi in ((C_LE4, LE4_MAX), (C_LE15, LE4_MAX), (C_LI, 50.0), (C_LS, LS_MAX)):
            self.table.setItemDelegateForColumn(c, DelegueReel(0.0, maxi, 2, self))
        v.addWidget(self.table)
        self.aide = QLabel(AIDE_LE4)
        self.aide.setWordWrap(True)
        self.aide.setObjectName("aide")
        v.addWidget(self.aide)
        lay.addWidget(grp, 1)

        for s in (self.R, self.Bf, self.LA):
            s.valueChanged.connect(self._anneau)
        self.table.itemChanged.connect(self._cellule)
        self.table.colle.connect(self._colle)
        self.table.currentCellChanged.connect(self._aide)

    # ------------------------------------------------------------------
    def charger(self, g: Giratoire) -> None:
        self.g = g
        for s, v in ((self.R, g.R), (self.Bf, g.Bf), (self.LA, g.LA)):
            s.blockSignals(True)
            s.setValue(v)
            s.blockSignals(False)
        self._maj_derives()
        t = self.table
        t.blockSignals(True)
        t.setRowCount(g.n)
        t.setVerticalHeaderLabels([str(k + 1) for k in range(g.n)])
        unite = "°" if g.unite_angle.libelle == "degrés" else "gr"
        t.horizontalHeaderItem(C_ANGLE).setText(f"Angle\n({unite})")
        t.horizontalHeaderItem(C_ECART).setText(f"Écart\n({unite})")
        for k, b in enumerate(g.branches):
            t.setItem(k, C_NOM, QTableWidgetItem_(b.nom))
            a = item_nombre(f"{b.angle}", editable=k > 0)
            t.setItem(k, C_ANGLE, a)
            ecart = "" if k == 0 else f"{b.angle - g.branches[k - 1].angle}"
            t.setItem(k, C_ECART, item_nombre(ecart, editable=k > 0))
            t.setItem(k, C_RAMPE, item_case(b.rampe, not b.entree_nulle))
            t.setItem(k, C_TAD, item_case(b.tad, not b.entree_nulle and g.R > 0))
            t.setItem(k, C_LE4, item_nombre(fmt_reel(b.le4)))
            t.setItem(k, C_EVASEE, item_case(b.evasee, not b.entree_nulle))
            t.setItem(k, C_LE15, item_nombre(fmt_reel(b.le15) if b.evasee else "", editable=b.evasee))
            bidir = not (b.entree_nulle or b.sortie_nulle)
            t.setItem(k, C_LI, item_nombre(fmt_reel(b.li) if bidir else "0", editable=bidir))
            t.setItem(k, C_LS, item_nombre(fmt_reel(b.ls)))
        t.blockSignals(False)

    def _maj_derives(self) -> None:
        g = self.g
        self.Rg.setText(f"{g.Rg:.2f} m".replace(".", ","))
        try:
            pg = parametres_giratoire(g)
            vals = {"RU": f"{pg.RU:.2f} m", "LAU": f"{pg.LAU:.2f} m", "LEU": f"{pg.LEU:.2f} m",
                    "LImax": f"{pg.LImax:.2f} m", "KE": f"{pg.KE:.3f}", "KI": f"{pg.KI:.3f}",
                    "Tg": f"{pg.Tg:.2f} s", "Tf1": f"{pg.Tf1:.2f} s", "Te": f"{pg.Te:.2f}"}
        except (ValueError, ZeroDivisionError):
            vals = {}
        for cle, lab in self.lbl_params.items():
            lab.setText(vals.get(cle, "—").replace(".", ","))

    def _anneau(self) -> None:
        g = self.g
        if g is None:
            return
        g.R, g.Bf, g.LA = self.R.value(), self.Bf.value(), self.LA.value()
        if g.R == 0:
            for b in g.branches:
                b.tad = False
        self._maj_derives()
        self.modifie.emit(False)
        QTimer.singleShot(0, lambda: self.charger(g))

    def _aide(self, ligne: int, col: int, *_):
        if col in (C_LE4, C_LE15, C_EVASEE):
            self.aide.setText(AIDE_LE4)
        elif col == C_LS:
            self.aide.setText(AIDE_LS)
        elif col == C_LI:
            self.aide.setText("Largeur d'îlot séparateur mesurée à la base du triangle de construction ; "
                              "nulle pour une branche à sens unique.")
        elif col == C_RAMPE:
            self.aide.setText("Rampe supérieure à 3 % en approche : le créneau complémentaire est majoré de 35 %.")
        elif col == C_TAD:
            self.aide.setText("Voie directe de tourne-à-droite vers la branche suivante (interdite sur un "
                              "mini-giratoire). Seul ce mouvement est retiré du calcul : la matrice doit l'inclure "
                              "et les largeurs restent celles situées entre l'anneau et la voie directe.")
        elif col in (C_ANGLE, C_ECART):
            self.aide.setText("Angle entre les axes des routes, mesuré depuis la branche 1 ; l'écart est "
                              "l'angle avec la branche précédente.")

    def _colle(self) -> None:
        for k in range(self.table.rowCount()):
            for c in (C_LE4, C_LE15, C_LI, C_LS):
                self._cellule(self.table.item(k, c), recharger=False)
        self.charger(self.g)
        self.modifie.emit(True)

    def _cellule(self, it, recharger: bool = True) -> None:
        g = self.g
        if g is None or it is None:
            return
        k, c = it.row(), it.column()
        b = g.branches[k]
        structure = False
        if c == C_NOM:
            b.nom = it.text().strip() or b.nom
            structure = True
        elif c == C_ANGLE:
            v = lire_entier(it.text())
            if v is not None and k > 0:
                b.angle = v
        elif c == C_ECART:
            v = lire_entier(it.text())
            if v is not None and k > 0:
                b.angle = g.branches[k - 1].angle + v
        elif c in (C_RAMPE, C_TAD, C_EVASEE):
            coche = it.checkState() == Qt.Checked
            if c == C_RAMPE:
                b.rampe = coche
            elif c == C_TAD:
                b.tad = coche and g.R > 0 and not b.entree_nulle
            else:
                b.evasee = coche
                if coche and b.le15 <= 0:
                    b.le15 = b.le4
        else:
            v = lire_reel(it.text())
            if v is None:
                v = 0.0
            if c == C_LE4:
                avant = b.entree_nulle
                b.le4 = v
                if b.entree_nulle:
                    b.tad = b.evasee = b.rampe = False
                    b.li = 0.0
                elif avant and b.li == 0 and not b.sortie_nulle:
                    b.li = 3.0
                structure = avant != b.entree_nulle
            elif c == C_LE15:
                b.le15 = v
            elif c == C_LI:
                b.li = v
            elif c == C_LS:
                avant = b.sortie_nulle
                b.ls = v
                if b.sortie_nulle:
                    b.li = 0.0
                elif avant and b.li == 0 and not b.entree_nulle:
                    b.li = 3.0
                structure = avant != b.sortie_nulle
        if recharger:
            self.modifie.emit(structure)
            QTimer.singleShot(0, lambda: self._recharger(k, c))

    def _recharger(self, k: int, c: int) -> None:
        if self.g is None:
            return
        self._maj_derives()
        self.charger(self.g)
        if k < self.table.rowCount():
            self.table.setCurrentCell(k, c)


def QTableWidgetItem_(texte: str):
    from PySide6.QtWidgets import QTableWidgetItem
    return QTableWidgetItem(texte)
