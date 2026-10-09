"""Guide d'utilisation en PDF (A4) à partir de docs/guide-utilisateur.md.

Utilisation : python outils/guide_pdf.py dist/Guide-utilisateur-Girabase.pdf
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
RACINE = Path(__file__).resolve().parent.parent

from PySide6.QtCore import QMarginsF, QSizeF, QUrl         # noqa: E402
from PySide6.QtGui import (QFont, QImage, QPageLayout, QPageSize, QPdfWriter, QTextCursor,  # noqa: E402
                           QTextDocument)
from PySide6.QtWidgets import QApplication                  # noqa: E402


def main(sortie: str) -> None:
    app = QApplication.instance() or QApplication([])
    docs = RACINE / "docs"
    texte = (docs / "guide-utilisateur.md").read_text(encoding="utf-8")
    doc = QTextDocument()
    doc.setDefaultFont(QFont("Arial", 11))
    doc.setBaseUrl(QUrl.fromLocalFile(str(docs) + "/"))
    doc.setMarkdown(texte)
    ecrivain = QPdfWriter(sortie)
    ecrivain.setPageLayout(QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Portrait, QMarginsF(16, 14, 16, 14),
                                       QPageLayout.Millimeter))
    ecrivain.setResolution(144)
    ecrivain.setTitle("Girabase — Guide d'utilisation")
    ecrivain.setCreator("Girabase (portage Python)")
    largeur_page = ecrivain.pageLayout().paintRectPixels(ecrivain.resolution()).width()
    # Captures ramenées à la largeur de la page
    curseur = QTextCursor(doc)
    bloc = doc.begin()
    while bloc.isValid():
        it = bloc.begin()
        while not it.atEnd():
            frag = it.fragment()
            if frag.isValid() and frag.charFormat().isImageFormat():
                fmt = frag.charFormat().toImageFormat()
                image = QImage(str(docs / fmt.name()))
                if not image.isNull():
                    l = min(largeur_page * 0.98, image.width())
                    fmt.setWidth(l)
                    fmt.setHeight(image.height() * l / image.width())
                    curseur.setPosition(frag.position())
                    curseur.setPosition(frag.position() + frag.length(), QTextCursor.KeepAnchor)
                    curseur.setCharFormat(fmt)
            it += 1
        bloc = bloc.next()
    doc.setPageSize(QSizeF(ecrivain.pageLayout().paintRectPixels(ecrivain.resolution()).size()))
    doc.print_(ecrivain)
    del app
    print(f"{sortie} : {doc.pageCount()} pages")


if __name__ == "__main__":
    main(sys.argv[1])
