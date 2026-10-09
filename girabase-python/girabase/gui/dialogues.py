"""Boîtes de dialogue : multiplication des trafics, import de trafics, à propos."""
from __future__ import annotations

from PySide6.QtCore import QLocale
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
                               QGridLayout, QLabel, QLineEdit, QListWidget, QRadioButton, QVBoxLayout)

from ..modele import Giratoire, Periode

FR = QLocale(QLocale.French, QLocale.France)


def _coef() -> QDoubleSpinBox:
    s = QDoubleSpinBox()
    s.setLocale(FR)
    s.setRange(0.0, 10.0)
    s.setDecimals(3)
    s.setSingleStep(0.05)
    s.setValue(1.0)
    return s


class DialogueMultiplier(QDialog):
    """Multiplier les trafics : coefficient global, par branche d'entrée ou par branche de sortie."""

    def __init__(self, g: Giratoire, src: Periode, parent=None):
        super().__init__(parent)
        self.g = g
        self.setWindowTitle(f"Multiplier les trafics de « {src.nom} »")
        lay = QVBoxLayout(self)
        f = QFormLayout()
        self.nom = QLineEdit(f"Multiplication de {src.nom}")
        f.addRow("Nom de la nouvelle période", self.nom)
        lay.addLayout(f)
        self.groupe = QButtonGroup(self)
        self.rb_total = QRadioButton("Même coefficient pour tous les mouvements")
        self.rb_entrant = QRadioButton("Coefficient par branche d'entrée")
        self.rb_sortant = QRadioButton("Coefficient par branche de sortie")
        for i, rb in enumerate((self.rb_total, self.rb_entrant, self.rb_sortant)):
            self.groupe.addButton(rb, i)
            lay.addWidget(rb)
        self.rb_total.setChecked(True)
        self.coef_general = _coef()
        f2 = QFormLayout()
        f2.addRow("Coefficient", self.coef_general)
        lay.addLayout(f2)
        grille = QGridLayout()
        self.cases, self.coefs = [], []
        for k, b in enumerate(g.branches):
            c = QCheckBox(f"{k + 1}. {b.nom}")
            c.setChecked(True)
            s = _coef()
            c.toggled.connect(s.setEnabled)
            grille.addWidget(c, k, 0)
            grille.addWidget(s, k, 1)
            self.cases.append(c)
            self.coefs.append(s)
        lay.addLayout(grille)
        note = QLabel("Exemple : coefficient 1,15 pour une hypothèse de croissance de 15 %. Les valeurs sont "
                      "arrondies à l'unité.")
        note.setObjectName("aide")
        note.setWordWrap(True)
        lay.addWidget(note)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.groupe.idClicked.connect(self._mode)
        self._mode(0)

    def _mode(self, ident: int) -> None:
        self.coef_general.setEnabled(ident == 0)
        for c, s in zip(self.cases, self.coefs):
            c.setEnabled(ident != 0)
            s.setEnabled(ident != 0 and c.isChecked())

    def parametres(self) -> dict:
        ident = self.groupe.checkedId()
        coefs = [s.value() if c.isChecked() else 1.0 for c, s in zip(self.cases, self.coefs)]
        if ident == 0:
            return {"coef_general": self.coef_general.value(), "nom": self.nom.text().strip()}
        if ident == 1:
            return {"coefs_entrants": coefs, "nom": self.nom.text().strip()}
        return {"coefs_sortants": coefs, "nom": self.nom.text().strip()}


class DialogueImport(QDialog):
    def __init__(self, autre: Giratoire, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Importer des trafics")
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"Périodes du projet « {autre.nom} » ({autre.n} branches) :"))
        self.liste = QListWidget()
        for p in autre.periodes_reelles():
            self.liste.addItem(p.nom)
        self.liste.setCurrentRow(0)
        self.liste.setSelectionMode(QListWidget.ExtendedSelection)
        lay.addWidget(self.liste)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def choix(self) -> list[int]:
        return sorted(self.liste.row(it) for it in self.liste.selectedItems())


TEXTE_A_PROPOS = """
<h3>Girabase — portage Python</h3>
<p>Calcul de capacité des carrefours giratoires.</p>
<p><i>L’intelligence artificielle au service de l’action publique efficiente.</i></p>
<p>Ce programme est un portage en Python du logiciel <b>GIRABASE 4</b> développé par le CERTU et le
CETE de l'Ouest, dont le CEREMA a publié le code source sous licence GNU GPL v3
(<a href="https://github.com/CEREMA/territoires-ville.Girabase">github.com/CEREMA/territoires-ville.Girabase</a>).
Les formules, coefficients, arrondis et conseils du logiciel d'origine sont repris à l'identique.</p>
<p>Ce portage est distribué sous la même licence GNU GPL v3. Il n'est ni édité ni validé par le CEREMA :
pour une étude engageante, vérifiez les résultats sur un cas de référence calculé avec le logiciel d'origine.</p>
"""
