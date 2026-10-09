# -*- mode: python ; coding: utf-8 -*-
# Spécification PyInstaller : construit dist/girabase-mcp.exe, serveur MCP en console (sans Qt).
# Utilisation : pyinstaller --noconfirm girabase_mcp.spec   (ou construire_exe.bat)

a = Analysis(
    ["lancer_mcp.py"],
    pathex=[],
    binaries=[],
    datas=[("LICENSE", ".")],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=["PySide6", "shiboken6", "tkinter", "matplotlib", "PIL", "pytest", "numpy", "ezdxf", "fontTools",
              "girabase.gui", "girabase.carto.gui", "girabase.dxf_export", "girabase.autotest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="girabase-mcp",
    debug=False,
    strip=False,
    upx=False,
    console=True,
    icon="girabase/ressources/girabase.ico",
    version="version_mcp.txt",
)
