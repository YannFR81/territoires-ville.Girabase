"""Encart repliable du panneau latéral : titre orange cliquable, résumé de deux lignes quand il est replié."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

FERME, OUVERT = "▸", "▾"


class Resume(QLabel):
    """Deux lignes au plus, chacune raccourcie par « … » à la largeur disponible ; un clic ouvre l'encart."""

    clique = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("resume")
        self.setTextFormat(Qt.PlainText)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self._lignes: list[str] = []

    def definir(self, lignes: list[str]) -> None:
        self._lignes = [t for t in lignes if t][:2]
        self.setToolTip("\n".join(self._lignes))
        self._raccourcir()

    def texte_complet(self) -> str:
        return "\n".join(self._lignes)

    def _raccourcir(self) -> None:
        fm = self.fontMetrics()
        largeur = max(60, self.width() - 4)
        self.setText("\n".join(fm.elidedText(t, Qt.ElideRight, largeur) for t in self._lignes))
        self.setFixedHeight(fm.lineSpacing() * max(1, len(self._lignes)) + 2)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._raccourcir()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self.clique.emit()
        super().mousePressEvent(ev)


class Encart(QFrame):
    """Section du panneau : l'en-tête ouvre ou ferme le contenu ; fermée, elle n'occupe que deux lignes."""

    bascule = Signal(str, bool)          # clé, ouvert

    def __init__(self, titre: str, cle: str, ouvert: bool = True, parent=None):
        super().__init__(parent)
        self.cle, self.titre = cle, titre
        self.setObjectName("encart")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 3, 8, 6)
        lay.setSpacing(2)
        self.entete = QPushButton()
        self.entete.setObjectName("entete")
        self.entete.setCheckable(True)
        self.entete.setFlat(True)
        self.entete.setCursor(Qt.PointingHandCursor)
        self.entete.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.entete.setToolTip("Cliquer pour ouvrir ou replier l'encart")
        self.resume = Resume()
        self.resume.clique.connect(lambda: self.ouvrir(True))
        self.corps = QWidget()
        self.corps.setObjectName("corps")
        lay.addWidget(self.entete)
        lay.addWidget(self.resume)
        lay.addWidget(self.corps)
        self.entete.toggled.connect(self._basculer)
        self.entete.setChecked(ouvert)
        self._basculer(ouvert)

    @property
    def ouvert(self) -> bool:
        return self.entete.isChecked()

    def ouvrir(self, ouvert: bool = True) -> None:
        self.entete.setChecked(ouvert)

    def definir_resume(self, *lignes: str) -> None:
        self.resume.definir(list(lignes))
        self.resume.setVisible(not self.ouvert and bool(self.resume.texte_complet()))

    def _basculer(self, ouvert: bool) -> None:
        self.entete.setText(f"{OUVERT if ouvert else FERME}  {self.titre}")
        self.corps.setVisible(ouvert)
        self.resume.setVisible(not ouvert and bool(self.resume.texte_complet()))
        self.bascule.emit(self.cle, ouvert)
