"""Auto-contrôle de l'exécutable : « Girabase.exe --autotest [dossier] ».

Recalcule le cas de référence du guide Girabase 4 (résultats du logiciel d'origine), exporte une
note PDF et un DXF dans le dossier indiqué, et écrit le compte rendu dans autotest_girabase.txt.
Code de sortie 0 si tout est conforme.
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

# Figure 2.6 du guide « Girabase Version 4.0 » (CERTU/CEREMA)
ATTENDU = [
    ("-659", "-122 %", "330 véh", "629 véh", "2193 s", "731 h"),
    ("-25", "-5 %", "21 véh", "62 véh", "145 s", "21,6 h"),
    ("2", "0 %", "21 véh", "65 véh", "101 s", "21,0 h"),
    ("-124", "-16 %", "62 véh", "171 véh", "290 s", "71,9 h"),
]


def _dossier_exemples() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / "exemples"


def executer(dossier: str | None = None) -> int:
    sortie = Path(dossier) if dossier else Path.cwd()
    sortie.mkdir(parents=True, exist_ok=True)
    lignes: list[str] = []
    ok = True
    try:
        from . import __version__, formats as F, gbs
        from .calcul import calculer
        from .dxf_export import exporter_dxf
        lignes.append(f"Girabase {__version__} — auto-contrôle")
        g = gbs.lire(_dossier_exemples() / "exemple_guide_certu.gbs")
        res = calculer(g)
        for rb, att in zip(res[0].branches, ATTENDU):
            obtenu = (F.rc(rb), F.rc_pct(rb), F.lk(rb), F.lkm(rb), F.tma(rb), F.tta(rb))
            conforme = obtenu == att
            ok &= conforme
            lignes.append(f"{'OK ' if conforme else 'ÉCART'} {rb.nom}: {obtenu} (attendu {att})")
        exporter_dxf(g, sortie / "autotest_schema.dxf")
        lignes.append("DXF : autotest_schema.dxf")
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        from .gui.rapport import exporter_pdf
        nb = exporter_pdf(g, res, str(sortie / "autotest_note.pdf"))
        lignes.append(f"PDF : autotest_note.pdf ({nb} pages)")
        del app
    except Exception:  # noqa: BLE001 — compte rendu complet en cas d'échec
        ok = False
        lignes.append(traceback.format_exc())
    # Localisation sur la carte IGN (données BD TOPO embarquées, réseau testé à titre d'information)
    try:
        from .carto.autotest import executer as executer_localisation
        ok_loc = executer_localisation(str(sortie)) == 0
        lignes.append(f"Localisation : {'CONFORME' if ok_loc else 'ÉCHEC'} (voir autotest_localisation.txt)")
        ok &= ok_loc
    except Exception:  # noqa: BLE001
        ok = False
        lignes.append(traceback.format_exc())
    lignes.append("RÉSULTAT : CONFORME" if ok else "RÉSULTAT : ÉCHEC")
    (sortie / "autotest_girabase.txt").write_text("\n".join(lignes), encoding="utf-8")
    return 0 if ok else 1
