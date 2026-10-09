"""Guide d'utilisation (docs/guide-utilisateur.md), affiché dans le logiciel."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QImage, QTextCursor
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTextBrowser, QVBoxLayout, QWidget

LARGEUR_IMAGES = 820           # px : captures ramenées à la largeur de la fenêtre d'aide


def dossier_guide() -> Path:
    """docs/ du dépôt, ou sa copie « ressources/guide » dans l'exécutable."""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "ressources" / "guide"
    return Path(__file__).resolve().parent.parent.parent / "docs"


def texte_guide() -> str:
    chemin = dossier_guide() / "guide-utilisateur.md"
    return chemin.read_text(encoding="utf-8") if chemin.exists() else "# Guide d'utilisation\n\nGuide introuvable."


def afficher_guide(parent: QWidget) -> None:
    dlg = QDialog(parent)
    dlg.setWindowTitle("Girabase — Guide d'utilisation")
    dlg.resize(900, 760)
    v = QVBoxLayout(dlg)
    tb = QTextBrowser()
    tb.setOpenExternalLinks(True)
    tb.document().setBaseUrl(QUrl.fromLocalFile(str(dossier_guide()) + "/"))
    tb.setSearchPaths([str(dossier_guide())])
    tb.setMarkdown(texte_guide())
    reduire_images(tb)
    v.addWidget(tb)
    bb = QDialogButtonBox(QDialogButtonBox.Close)
    bb.rejected.connect(dlg.reject)
    v.addWidget(bb)
    dlg.exec()


def reduire_images(tb: QTextBrowser, largeur: int = LARGEUR_IMAGES) -> int:
    """Ramène les captures d'écran du guide à la largeur de la fenêtre (proportions conservées)."""
    doc = tb.document()
    curseur = QTextCursor(doc)
    nb = 0
    bloc = doc.begin()
    while bloc.isValid():
        it = bloc.begin()
        while not it.atEnd():
            frag = it.fragment()
            if frag.isValid() and frag.charFormat().isImageFormat():
                fmt = frag.charFormat().toImageFormat()
                image = QImage(str(dossier_guide() / fmt.name()))
                if not image.isNull() and image.width() > largeur:
                    fmt.setWidth(largeur)
                    fmt.setHeight(image.height() * largeur / image.width())
                    curseur.setPosition(frag.position())
                    curseur.setPosition(frag.position() + frag.length(), QTextCursor.KeepAnchor)
                    curseur.setCharFormat(fmt)
                    nb += 1
            it += 1
        bloc = bloc.next()
    return nb
