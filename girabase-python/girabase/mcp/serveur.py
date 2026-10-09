"""Serveur MCP sur l'entrée et la sortie standard (JSON-RPC 2.0, un message JSON par ligne).

Implémente le strict nécessaire de la spécification Model Context Protocol pour exposer des outils :
initialize, notifications/initialized, ping, tools/list et tools/call. Aucune dépendance externe.
"""
from __future__ import annotations

import json
import sys
import traceback
from typing import Any, Optional, TextIO

from .. import __version__
from .outils import INSTRUCTIONS, OUTILS, ErreurOutil, Girabase

VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")


def _journal(texte: str) -> None:
    print(f"[girabase-mcp] {texte}", file=sys.stderr, flush=True)       # stdout est réservé au protocole


class ServeurMCP:
    def __init__(self, girabase: Optional[Girabase] = None):
        self.girabase = girabase or Girabase()

    def traiter(self, message: dict) -> Optional[dict]:
        """Réponse JSON-RPC à un message (None pour une notification)."""
        ident = message.get("id")
        methode = message.get("method")
        if methode is None:                      # réponse d'un client : rien à faire
            return None
        params = message.get("params")
        try:
            if not isinstance(methode, str):
                raise _ErreurRPC(-32600, "Requête invalide : « method » doit être une chaîne.")
            if params is None:
                params = {}
            elif not isinstance(params, dict):
                raise _ErreurRPC(-32602, "Paramètres invalides : « params » doit être un objet JSON.")
            resultat = self._executer(methode, params)
        except _ErreurRPC as exc:
            return None if ident is None else {"jsonrpc": "2.0", "id": ident,
                                               "error": {"code": exc.code, "message": exc.message}}
        if ident is None:
            return None
        return {"jsonrpc": "2.0", "id": ident, "result": resultat}

    def _executer(self, methode: str, params: dict) -> Any:
        if methode == "initialize":
            demandee = params.get("protocolVersion")
            return {"protocolVersion": demandee if demandee in VERSIONS else VERSIONS[0],
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "girabase", "title": "Girabase (portage Python de GIRABASE 4)",
                                   "version": __version__},
                    "instructions": INSTRUCTIONS}
        if methode.startswith("notifications/"):
            return None
        if methode == "ping":
            return {}
        if methode == "tools/list":
            return {"tools": OUTILS}
        if methode == "tools/call":
            nom, arguments = params.get("name", ""), params.get("arguments")
            if not isinstance(nom, str):
                raise _ErreurRPC(-32602, "Paramètres invalides : « name » doit être une chaîne.")
            if arguments is None:
                arguments = {}
            elif not isinstance(arguments, dict):
                raise _ErreurRPC(-32602, "Paramètres invalides : « arguments » doit être un objet JSON.")
            return self._appel_outil(nom, arguments)
        raise _ErreurRPC(-32601, f"Méthode inconnue : {methode}")

    def _appel_outil(self, nom: str, arguments: dict) -> dict:
        if nom not in self.girabase.traitements:
            raise _ErreurRPC(-32602, f"Outil inconnu : {nom}")
        try:
            donnees = self.girabase.appeler(nom, arguments)
        except ErreurOutil as exc:
            return {"content": [{"type": "text", "text": str(exc)}], "isError": True}
        except Exception as exc:                 # erreur inattendue : message utile, serveur maintenu
            _journal(traceback.format_exc())
            return {"content": [{"type": "text", "text": f"Erreur de Girabase : {exc}"}], "isError": True}
        texte = json.dumps(donnees, ensure_ascii=False, indent=1)
        return {"content": [{"type": "text", "text": texte}], "structuredContent": donnees, "isError": False}


class _ErreurRPC(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def _traiter_sans_risque(serveur: ServeurMCP, message: Any) -> Optional[dict]:
    """Traite un message sans jamais interrompre la boucle : toute anomalie devient une erreur JSON-RPC."""
    if not isinstance(message, dict):
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Requête invalide"}}
    ident = message.get("id")
    if not isinstance(ident, (str, int, float, type(None))) or isinstance(ident, bool):
        ident = None
    try:
        return serveur.traiter(message)
    except Exception as exc:                     # filet de sécurité : le serveur reste disponible
        _journal(traceback.format_exc())
        if "method" not in message or ident is None:
            return None
        return {"jsonrpc": "2.0", "id": ident, "error": {"code": -32603, "message": f"Erreur interne : {exc}"}}


def boucle(entree: TextIO, sortie: TextIO, serveur: Optional[ServeurMCP] = None) -> None:
    serveur = serveur or ServeurMCP()
    for ligne in entree:
        ligne = ligne.strip()
        if not ligne:
            continue
        try:
            message = json.loads(ligne)
        except ValueError:
            reponse = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "JSON invalide"}}
        else:
            if isinstance(message, list):        # lot JSON-RPC (anciennes versions du protocole)
                reponses = [r for r in (_traiter_sans_risque(serveur, m) for m in message) if r]
                reponse = reponses or None
            else:
                reponse = _traiter_sans_risque(serveur, message)
        if reponse is not None:
            sortie.write(json.dumps(reponse, ensure_ascii=False) + "\n")
            sortie.flush()


def main(argv: Optional[list[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--version" in argv:
        print(f"girabase-mcp {__version__}")
        return 0
    if "--aide" in argv or "--help" in argv:
        print("Serveur MCP de Girabase (stdio). À déclarer dans le client d'IA, par exemple Claude Desktop :\n"
              '  "mcpServers": {"girabase": {"command": "C:\\\\Outils\\\\girabase-mcp.exe"}}\n'
              "Outils : " + ", ".join(o["name"] for o in OUTILS))
        return 0
    # Entrées/sorties en UTF-8, fins de ligne « \n » (Windows) ; journal en UTF-8 sur stderr
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    entree = open(sys.stdin.fileno(), "r", encoding="utf-8", closefd=False)
    sortie = open(sys.stdout.fileno(), "w", encoding="utf-8", newline="\n", closefd=False)
    _journal(f"Girabase {__version__} prêt ({len(OUTILS)} outils).")
    try:
        boucle(entree, sortie)
    except KeyboardInterrupt:
        pass
    return 0
