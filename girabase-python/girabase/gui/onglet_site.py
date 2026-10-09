"""Onglet « Site » : identification, environnement, nombre de branches."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QButtonGroup, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
                               QPushButton, QRadioButton, QSizePolicy, QSpinBox, QVBoxLayout, QWidget)

from ..constantes import NB_BRANCHES_MAX, NB_BRANCHES_MIN, Milieu
from ..modele import Giratoire

AIDE_MILIEU = {
    Milieu.RASE_CAMPAGNE: "Hors agglomération. Les mini-giratoires y sont interdits ; anneau de 4,5 à 12 m.",
    Milieu.PERIURBAIN: "Entrée d'agglomération, zones d'activités, contournements. Anneau de 4,5 à 18 m.",
    Milieu.CENTRE_VILLE: "Milieu urbain dense, présence de piétons. Anneau de 4,5 à 18 m.",
}


class OngletSite(QWidget):
    modifie = Signal(bool)          # True si modification de structure (nombre de branches)
    basculer_angles = Signal()
    localiser = Signal()            # ouvrir la localisation sur la carte IGN

    def __init__(self, parent=None):
        super().__init__(parent)
        self.g: Giratoire | None = None
        lay = QVBoxLayout(self)

        ident = QGroupBox("Identification")
        f = QFormLayout(ident)
        f.setRowWrapPolicy(QFormLayout.DontWrapRows)
        self.nom = QLineEdit()
        self.variante = QLineEdit()
        self.localisation = QPlainTextEdit()
        self.localisation.setPlaceholderText("Commune, route départementale, PR, commentaire…")
        self.localisation.setFixedHeight(80)
        self.date = QLabel()
        self.date.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        f.addRow("Nom du carrefour", self.nom)
        f.addRow("Variante", self.variante)
        f.addRow("Localisation", self.localisation)
        h_carte = QHBoxLayout()
        self.bt_carte = QPushButton("◎  Localiser sur la carte IGN…")
        self.bt_carte.setToolTip("Photo aérienne et BD TOPO de l'IGN : centre, anneau existant, branches, noms de "
                                 "routes, orientations et angles, commune et coordonnées (Ctrl+L)")
        self.bt_carte.clicked.connect(self.localiser)
        h_carte.addWidget(self.bt_carte)
        aide_carte = QLabel("Pointez le carrefour sur la photo aérienne : les branches et leurs angles sont "
                            "repris dans le projet.")
        aide_carte.setObjectName("aide")
        aide_carte.setWordWrap(True)
        h_carte.addWidget(aide_carte, 1)
        f.addRow("", h_carte)
        f.addRow("Dernière modification", self.date)
        lay.addWidget(ident)

        env = QGroupBox("Environnement")
        v = QVBoxLayout(env)
        self.groupe_milieu = QButtonGroup(self)
        h = QHBoxLayout()
        for m in Milieu:
            rb = QRadioButton(m.libelle)
            self.groupe_milieu.addButton(rb, int(m))
            h.addWidget(rb)
        h.addStretch()
        v.addLayout(h)
        self.aide_milieu = QLabel()
        self.aide_milieu.setWordWrap(True)
        self.aide_milieu.setObjectName("aide")
        v.addWidget(self.aide_milieu)
        lay.addWidget(env)

        br = QGroupBox("Branches")
        f2 = QFormLayout(br)
        f2.setRowWrapPolicy(QFormLayout.DontWrapRows)
        self.nb = QSpinBox()
        self.nb.setRange(NB_BRANCHES_MIN, NB_BRANCHES_MAX)
        self.nb.setMaximumWidth(90)
        f2.addRow("Nombre de branches", self.nb)
        h2 = QHBoxLayout()
        self.unite = QLabel()
        self.bt_unite = QPushButton("Convertir les angles")
        h2.addWidget(self.unite)
        h2.addWidget(self.bt_unite)
        h2.addStretch()
        f2.addRow("Unité d'angle", h2)
        note = QLabel("Numérotez les branches dans le sens de giration (sens inverse des aiguilles d'une "
                      "montre) ; la branche n° 1 sert de référence des angles.")
        note.setWordWrap(True)
        note.setObjectName("aide")
        f2.addRow(note)
        lay.addWidget(br)
        lay.addStretch()

        self.nom.textEdited.connect(self._texte)
        self.variante.textEdited.connect(self._texte)
        self.localisation.textChanged.connect(self._texte)
        self.groupe_milieu.idClicked.connect(self._milieu)
        self.nb.valueChanged.connect(self._nb)
        self.bt_unite.clicked.connect(self.basculer_angles)

    def charger(self, g: Giratoire) -> None:
        self.g = g
        for w in (self.nom, self.variante, self.localisation, self.nb):
            w.blockSignals(True)
        self.nom.setText(g.nom)
        self.variante.setText(g.variante)
        if self.localisation.toPlainText() != g.localisation:
            self.localisation.setPlainText(g.localisation)
        self.date.setText(g.date_modif.strftime("%d/%m/%Y"))
        self.groupe_milieu.setExclusive(False)
        for b in self.groupe_milieu.buttons():
            b.setChecked(g.milieu is not None and self.groupe_milieu.id(b) == int(g.milieu))
        self.groupe_milieu.setExclusive(True)
        self.aide_milieu.setText(AIDE_MILIEU[g.milieu] if g.milieu is not None else
                                 "Choisissez l'environnement : il détermine les coefficients du calcul.")
        self.nb.setValue(g.n)
        autre = "grades" if g.unite_angle.libelle == "degrés" else "degrés"
        self.unite.setText(g.unite_angle.libelle.capitalize())
        self.bt_unite.setText(f"Convertir en {autre}")
        for w in (self.nom, self.variante, self.localisation, self.nb):
            w.blockSignals(False)

    def _texte(self) -> None:
        if self.g is None:
            return
        self.g.nom = self.nom.text()
        self.g.variante = self.variante.text()
        self.g.localisation = self.localisation.toPlainText()
        self.modifie.emit(False)

    def _milieu(self, ident: int) -> None:
        if self.g is None:
            return
        self.g.milieu = Milieu(ident)
        self.aide_milieu.setText(AIDE_MILIEU[self.g.milieu])
        self.modifie.emit(False)

    def _nb(self, n: int) -> None:
        if self.g is None:
            return
        while self.g.n < n:
            self.g.ajouter_branche()
        while self.g.n > n:
            self.g.supprimer_branche(self.g.n - 1)
        self.modifie.emit(True)
