"""Outil « Localisation du giratoire » seul (développement) : python -m girabase.carto.gui.app

Dans Girabase, la carte s'ouvre par le menu Outils > Localiser sur la carte IGN."""
from __future__ import annotations

import sys

from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from ...gui.app import STYLE, chemin_ressource, journal_plantage


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    if "--autotest" in argv:
        from ..autotest import executer
        i = argv.index("--autotest")
        return executer(argv[i + 1] if i + 1 < len(argv) else None)
    journal_plantage("girabase_localisation_plantage.txt")
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Girabase.Localisation")
        except (AttributeError, OSError):
            pass
    QLocale.setDefault(QLocale(QLocale.French, QLocale.France))
    app = QApplication(argv)
    app.setApplicationName("Girabase")
    app.setOrganizationName("Girabase-Py")
    trad = QTranslator(app)
    if trad.load(QLocale(), "qtbase", "_", QLibraryInfo.path(QLibraryInfo.TranslationsPath)):
        app.installTranslator(trad)
    icone = chemin_ressource("girabase.png")
    if icone.exists():
        app.setWindowIcon(QIcon(str(icone)))
    app.setStyleSheet(STYLE)
    from .fenetre import FenetreLocalisation
    fichier = next((a for a in argv[1:] if a.lower().endswith(".gsite")), None)
    fen = FenetreLocalisation(fichier)
    fen.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
