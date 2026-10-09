"""Assemble girabase.mcpb (extension MCP installable d'un double-clic dans Claude Desktop).

Utilisation : python outils/creer_mcpb.py dist/girabase-mcp.exe dist/girabase.mcpb
"""
import json
import sys
import zipfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from girabase import __version__                      # noqa: E402
from girabase.mcp.outils import INSTRUCTIONS, OUTILS  # noqa: E402


def manifeste() -> dict:
    return {
        "manifest_version": "0.3",
        "name": "girabase",
        "display_name": "Girabase — capacité des giratoires",
        "version": __version__,
        "description": "Calcul de capacité des carrefours giratoires (portage Python de GIRABASE 4, CERTU/CEREMA) "
                       "et analyse des carrefours sur les données de l'IGN.",
        "long_description": INSTRUCTIONS,
        "author": {"name": "Yann Steffan — portage Python de Girabase",
                   "url": "https://github.com/YannFR81/territoires-ville.Girabase"},
        "homepage": "https://github.com/YannFR81/territoires-ville.Girabase",
        "repository": {"type": "git", "url": "https://github.com/YannFR81/territoires-ville.Girabase"},
        "license": "GPL-3.0-or-later",
        "keywords": ["giratoire", "carrefour", "capacité", "Girabase", "CEREMA", "IGN", "voirie"],
        "icon": "icon.png",
        "server": {"type": "binary", "entry_point": "server/girabase-mcp.exe",
                   "mcp_config": {"command": "${__dirname}/server/girabase-mcp.exe", "args": [], "env": {}}},
        "tools": [{"name": o["name"], "description": o["title"]} for o in OUTILS],
        "tools_generated": False,
        "compatibility": {"platforms": ["win32"]},
    }


def main(exe: str, sortie: str) -> None:
    with zipfile.ZipFile(sortie, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifeste(), ensure_ascii=False, indent=2))
        z.write(exe, "server/girabase-mcp.exe")
        z.write(RACINE / "girabase" / "ressources" / "girabase.png", "icon.png")
        z.write(RACINE / "LICENSE", "LICENSE")
    print(f"{sortie} créé")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
