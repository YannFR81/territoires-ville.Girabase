"""Onglet « Résultats » : capacités, réserves, attentes, conseils et courbes."""
from __future__ import annotations

import html
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QGuiApplication
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QHBoxLayout, QHeaderView, QLabel, QPushButton,
                               QSplitter, QTableWidget, QTabWidget, QTextBrowser, QVBoxLayout, QWidget)

from .. import formats as F
from ..calcul import ResultatPeriode
from ..conseils import Remarque, remarques_conception, remarques_fonctionnement, remarques_trafics
from ..modele import Giratoire
from .courbe import CourbeCapacite, PointPeriode
from ..carto.gui.theme import couleur_texte
from .schema import COULEURS_RC  # noqa: F401
from .tableaux import item_nombre

COLS = ["Trafic\nentrant", "Trafic\ngênant", "Capacité", "Réserve\n(uvp/h)", "Réserve\n(%)", "File\nmoyenne",
        "File\nmaximale", "Attente\nmoyenne", "Attente\ntotale"]


def html_remarques(g: Giratoire, rems: list[Remarque]) -> str:
    if not rems:
        return "<p><i>Aucune remarque.</i></p>"
    blocs: dict[Optional[int], list[str]] = {}
    for r in rems:
        blocs.setdefault(r.branche, []).append(html.escape(r.texte).replace("\n", "<br>"))
    out = []
    if None in blocs:
        out.append("<p><b>Giratoire</b></p><ul>" + "".join(f"<li>{t}</li>" for t in blocs.pop(None)) + "</ul>")
    for k in sorted(blocs):
        out.append(f"<p><b>Branche {k + 1} — {html.escape(g.branches[k].nom)}</b></p><ul>"
                   + "".join(f"<li>{t}</li>" for t in blocs[k]) + "</ul>")
    return "".join(out)


def points_courbe(g: Giratoire, resultats: list[ResultatPeriode], k: int) -> list[PointPeriode]:
    pts = []
    for res in resultats:
        if not res.complete or k >= len(res.branches):
            continue
        rb = res.branches[k]
        if rb.entree_nulle:
            continue
        y = rb.QE / (1 - rb.Cp) if rb.Cp < 1 else rb.QE
        if g.branches[k].tad:
            y -= res.periode.matrice_uvp()[k][g.suivante(k)] or 0
        pts.append(PointPeriode(res.periode.nom, res.periode.couleur, rb.QG, y))
    return pts


class OngletResultats(QWidget):
    saturer = Signal(int, int)          # (indice période, branche)
    supprimer_saturee = Signal(int)
    periode_changee = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.g: Optional[Giratoire] = None
        self.resultats: list[ResultatPeriode] = []
        self.index = 0
        lay = QVBoxLayout(self)

        barre = QHBoxLayout()
        barre.addWidget(QLabel("Période"))
        self.combo = QComboBox()
        self.combo.setMinimumWidth(200)
        barre.addWidget(self.combo)
        self.bt_saturer = QPushButton("Saturer la branche")
        self.bt_saturer.setToolTip("Recalcule le giratoire avec un trafic entrant limité à la capacité de la "
                                   "branche sélectionnée (aide Girabase §2.5.4.1).")
        self.bt_copier = QPushButton("Copier le tableau")
        self.bt_copier.setToolTip("Copie le tableau des résultats pour le coller dans Excel ou Word.")
        barre.addWidget(self.bt_saturer)
        barre.addWidget(self.bt_copier)
        barre.addStretch()
        lay.addLayout(barre)

        self.bandeau = QLabel()
        self.bandeau.setWordWrap(True)
        self.bandeau.setObjectName("erreur")
        self.bandeau.setVisible(False)
        lay.addWidget(self.bandeau)

        split = QSplitter(Qt.Vertical)
        self.table = QTableWidget(0, len(COLS))
        self.table.setHorizontalHeaderLabels(COLS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        aide_file = ("Nombre de véhicules en attente sur l'ensemble de l'entrée. Pour une entrée à plusieurs "
                     "voies, diviser par le nombre de voies pour obtenir la longueur de file (la voie de gauche "
                     "est souvent moins chargée).")
        for c in (5, 6):
            self.table.horizontalHeaderItem(c).setToolTip(aide_file)
        self.table.horizontalHeaderItem(7).setToolTip(
            "Temps moyen d'attente d'un véhicule ; il tient compte du nombre de voies (capacité globale de l'entrée).")
        split.addWidget(self.table)

        self.onglets = QTabWidget()
        self.txt_fonct = QTextBrowser()
        self.txt_trafics = QTextBrowser()
        self.txt_conception = QTextBrowser()
        courbe_w = QWidget()
        vc = QVBoxLayout(courbe_w)
        self.lbl_courbe = QLabel("Sélectionnez une branche dans le tableau.")
        self.lbl_courbe.setObjectName("aide")
        self.courbe = CourbeCapacite()
        vc.addWidget(self.lbl_courbe)
        vc.addWidget(self.courbe, 1)
        self.onglets.addTab(self.txt_fonct, "Fonctionnement")
        self.onglets.addTab(self.txt_trafics, "Remarques sur les trafics")
        self.onglets.addTab(self.txt_conception, "Remarques de conception")
        self.onglets.addTab(courbe_w, "Courbe de capacité")
        split.addWidget(self.onglets)
        split.setSizes([260, 340])
        lay.addWidget(split, 1)

        self.combo.currentIndexChanged.connect(self._choix)
        self.table.currentCellChanged.connect(lambda *_: self._maj_selection())
        self.bt_saturer.clicked.connect(self._saturer)
        self.bt_copier.clicked.connect(self.copier)

    # ------------------------------------------------------------------
    def charger(self, g: Giratoire, resultats: list[ResultatPeriode], erreurs: list[Remarque]) -> None:
        self.g = g
        self.resultats = resultats if not erreurs else []
        self.bandeau.setVisible(bool(erreurs))
        if erreurs:
            self.bandeau.setText("<b>Calcul impossible — données à corriger :</b><br>"
                                 + "<br>".join("• " + html.escape(e.texte) for e in erreurs))
        self.combo.blockSignals(True)
        self.combo.clear()
        for res in self.resultats:
            nom = res.periode.nom
            if not res.complete:
                nom += "  (incomplète)"
            self.combo.addItem(nom)
        self.index = max(0, min(self.index, len(self.resultats) - 1))
        self.combo.setCurrentIndex(self.index)
        self.combo.blockSignals(False)
        self._afficher()

    def selectionner_periode(self, nom: str) -> None:
        for i, res in enumerate(self.resultats):
            if res.periode.nom == nom:
                self.combo.setCurrentIndex(i)
                return

    def resultat_courant(self) -> Optional[ResultatPeriode]:
        if not self.resultats:
            return None
        return self.resultats[self.index]

    def _choix(self, idx: int) -> None:
        self.index = max(idx, 0)
        self._afficher()
        self.periode_changee.emit(self.index)

    def _afficher(self) -> None:
        g = self.g
        res = self.resultat_courant()
        t = self.table
        ligne = max(t.currentRow(), 0)
        t.setRowCount(0)
        if res is None:
            for w in (self.txt_fonct, self.txt_trafics, self.txt_conception):
                w.setHtml("")
            self.courbe.afficher("", None, None, [])
            self.bt_saturer.setEnabled(False)
            return
        t.setRowCount(g.n)
        t.setVerticalHeaderLabels([f"{k + 1}. {b.nom}" for k, b in enumerate(g.branches)])
        gras = QFont()
        gras.setBold(True)
        for k, rb in enumerate(res.branches):
            if rb.entree_nulle:
                vals = [str(rb.QE), "", "", "", "", "", "", "", ""]
                vals[1] = "sortie seule"
            elif not res.complete:
                vals = [str(rb.QE)] + [""] * 8
            else:
                vals = [str(rb.QEntrant), str(rb.QG),
                        F.nombre(rb.C), F.rc(rb), F.rc_pct(rb), F.lk(rb), F.lkm(rb), F.tma(rb), F.tta(rb)]
            for c, v in enumerate(vals):
                it = item_nombre(v, editable=False)
                if c in (3, 4) and res.complete and not rb.entree_nulle:
                    niv = F.niveau_rc(rb.RC_pct)
                    it.setForeground(QBrush(QColor(couleur_texte(niv))))
                    it.setFont(gras)
                t.setItem(k, c, it)
            if g.branches[k].tad and res.complete and not rb.entree_nulle:
                t.item(k, 0).setToolTip(f"Trafic entrant sur l'anneau, hors voie directe de tourne-à-droite "
                                        f"(total de la branche : {rb.QE} uvp/h).")
        t.setCurrentCell(min(ligne, g.n - 1), 0)
        hauteur = t.horizontalHeader().height() + sum(t.rowHeight(i) for i in range(g.n)) + 2 * t.frameWidth() + 4
        t.setMaximumHeight(max(hauteur, 120))
        rems_c = remarques_conception(g, res)
        self.txt_conception.setHtml(html_remarques(g, rems_c))
        if res.complete:
            self.txt_fonct.setHtml(html_remarques(g, remarques_fonctionnement(g, res)))
            self.txt_trafics.setHtml(html_remarques(g, remarques_trafics(g, res)))
        else:
            msg = "<p>Les trafics de la période en cours sont incomplets ; les conseils relatifs à cette " \
                  "période ne peuvent être édités.</p>"
            self.txt_fonct.setHtml(msg)
            self.txt_trafics.setHtml(msg)
        self._maj_selection()

    def _maj_selection(self) -> None:
        res = self.resultat_courant()
        g = self.g
        k = self.table.currentRow()
        if res is None or k < 0 or k >= g.n:
            self.bt_saturer.setEnabled(False)
            return
        rb = res.branches[k]
        sat = res.periode.branche_saturee is not None
        if sat:
            self.bt_saturer.setText("Supprimer cette période saturée")
            self.bt_saturer.setEnabled(True)
        else:
            self.bt_saturer.setText(f"Saturer la branche {k + 1}")
            self.bt_saturer.setEnabled(res.complete and not rb.entree_nulle and rb.RC < 0)
        if rb.entree_nulle:
            self.lbl_courbe.setText(f"Branche {k + 1} — {g.branches[k].nom} : sortie seule, pas de courbe.")
            self.courbe.afficher("", None, None, [])
            return
        pb = res.params_branches[k] if res.params_branches else None
        self.lbl_courbe.setText(f"Branche {k + 1} — {g.branches[k].nom} : capacité en fonction du trafic gênant ; "
                                f"un point au-dessus de la courbe signale une entrée saturée.")
        self.courbe.afficher(f"Branche {k + 1} — {g.branches[k].nom}", res.params, pb,
                             points_courbe(g, [r for r in self.resultats if r.periode.branche_saturee is None], k))

    def _saturer(self) -> None:
        res = self.resultat_courant()
        if res is None:
            return
        if res.periode.branche_saturee is not None:
            self.supprimer_saturee.emit(self.index)
        else:
            self.saturer.emit(self.index, self.table.currentRow())

    def copier(self) -> None:
        t = self.table
        lignes = ["Branche\t" + "\t".join(c.replace("\n", " ") for c in COLS)]
        for i in range(t.rowCount()):
            cel = [t.verticalHeaderItem(i).text()]
            cel += [(t.item(i, j).text() if t.item(i, j) else "") for j in range(t.columnCount())]
            lignes.append("\t".join(cel))
        QGuiApplication.clipboard().setText("\n".join(lignes))
