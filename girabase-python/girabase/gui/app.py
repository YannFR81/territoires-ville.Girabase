"""Point d'entrée de l'application de bureau."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QLocale, QTranslator, QLibraryInfo
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

STYLE = """
QLabel#aide { color: palette(placeholder-text); }
QLabel#valeur { font-weight: 600; }
QLabel#erreur { background: #f8e6ec; color: #7F0541; padding: 8px; border-radius: 4px; }
QTabBar::tab { padding: 6px 14px; }
QGroupBox { font-weight: 600; margin-top: 10px; }
QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; color: #DD590A; }
QHeaderView::section { padding: 3px 4px; }
"""


def chemin_ressource(nom: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / "ressources" / nom


_JOURNAL = None


def journal_plantage(nom: str = "girabase_plantage.txt") -> None:
    """En cas d'arrêt brutal, la pile d'appels est écrite dans %TEMP%\\girabase_plantage.txt (à joindre à un
    signalement d'anomalie)."""
    import faulthandler
    import tempfile
    global _JOURNAL
    try:
        _JOURNAL = open(Path(tempfile.gettempdir()) / nom, "w", encoding="utf-8")
        faulthandler.enable(_JOURNAL)
    except (OSError, RuntimeError):
        pass


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    if "--autotest" in argv:
        from ..autotest import executer
        i = argv.index("--autotest")
        return executer(argv[i + 1] if i + 1 < len(argv) else None)
    journal_plantage()
    if sys.platform == "win32":
        try:  # icône propre dans la barre des tâches Windows
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Girabase.PortagePython")
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
    from .fenetre import FenetrePrincipale
    fichier = next((a for a in argv[1:] if a.lower().endswith(".gbs")), None)
    fen = FenetrePrincipale(fichier)
    fen.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
