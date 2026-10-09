# -*- mode: python ; coding: utf-8 -*-
# Spécification PyInstaller : construit dist/Girabase/Girabase.exe (un dossier, démarrage rapide).
# Utilisation : pyinstaller --noconfirm girabase.spec   (ou construire_exe.bat)

# Modules Qt non utilisés : exclus pour réduire la taille
EXCLUS = [
    "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickWidgets", "PySide6.QtSql",
    "PySide6.QtTest", "PySide6.QtXml", "PySide6.QtDBus", "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets",
    "PySide6.QtSvg", "PySide6.QtSvgWidgets", "PySide6.QtConcurrent", "PySide6.QtDesigner", "PySide6.QtHelp",
    "PySide6.QtUiTools", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtMultimedia",
    "tkinter", "matplotlib", "PIL", "pytest", "numpy", "ezdxf", "fontTools",
]

# Fichiers Qt inutiles pour une application de bureau en widgets (allège l'exécutable de ~25 Mo).
# QtNetwork, le chiffrement TLS natif de Windows (Schannel) et le décodeur JPEG servent à la carte IGN.
DLL_INUTILES = ("opengl32sw.dll", "qt6pdf.dll", "qt6svg.dll", "qt6opengl.dll", "qt6qml.dll",
                "qt6qmlmodels.dll", "qt6quick.dll", "qt6virtualkeyboard.dll", "d3dcompiler_47.dll")


def _garder(entree):
    dest = entree[0].replace("\\", "/").lower()
    if dest.endswith(DLL_INUTILES):
        return False
    if "/translations/" in dest and not dest.endswith("qtbase_fr.qm"):
        return False
    if "/plugins/" in dest and not any(k in dest for k in ("/platforms/qwindows", "/platforms/qoffscreen",
                                                           "/styles/", "/imageformats/qico", "/imageformats/qjpeg",
                                                           "/tls/qschannelbackend")):
        return False
    return True


a = Analysis(
    ["lancer_girabase.py"],
    pathex=[],
    binaries=[],
    datas=[("girabase/ressources", "ressources"), ("exemples", "exemples"), ("LICENSE", "."),
           ("girabase/carto/donnees", "girabase/carto/donnees"),
           ("docs/guide-utilisateur.md", "ressources/guide"), ("docs/sources-et-licences.md", "ressources/guide"),
           ("docs/images", "ressources/guide/images")],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=EXCLUS,
    noarchive=False,
)
a.binaries = [b for b in a.binaries if _garder(b)]
a.datas = [d for d in a.datas if _garder(d)]
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Girabase",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon="girabase/ressources/girabase.ico",
    version="version_windows.txt",
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Girabase")
