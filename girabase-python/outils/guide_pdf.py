"""Guide d'utilisation en PDF (A4) à partir de docs/guide-utilisateur.md.

Utilisation : python outils/guide_pdf.py dist/Guide-utilisateur-Girabase.pdf
"""
import os
import sys
from pathlib import Path

# Sous Windows, le mode « offscreen » de Qt ne trouve aucune police : le texte sort en pavés noirs. On garde
# donc la plateforme normale de Windows, et on indique le dossier des polices si « offscreen » est imposé.
if sys.platform == "win32":
    if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
        os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
else:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
RACINE = Path(__file__).resolve().parent.parent

from PySide6.QtCore import QMarginsF, QSizeF, QUrl         # noqa: E402
from PySide6.QtGui import (QFont, QFontDatabase, QFontInfo, QFontMetrics, QImage, QPageLayout,  # noqa: E402
                           QPageSize, QPdfWriter, QTextCursor, QTextDocument)
from PySide6.QtWidgets import QApplication                  # noqa: E402


def verifier_polices(police: QFont) -> None:
    """Refuse de produire un PDF illisible : il faut une vraie police qui contient les lettres accentuées."""
    familles = QFontDatabase.families()
    m = QFontMetrics(police)
    manquants = [c for c in "AaÉéèàçœ’«»" if not m.inFontUcs4(ord(c))]
    if not familles or manquants:
        raise SystemExit(f"Polices indisponibles ({len(familles)} familles, police utilisée : "
                         f"{QFontInfo(police).family()!r}, caractères absents : {''.join(manquants)!r}) : "
                         "le PDF serait illisible.")


def main(sortie: str) -> None:
    app = QApplication.instance() or QApplication([])
    verifier_polices(QFont("Arial", 11))
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
