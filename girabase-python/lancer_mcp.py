"""Lanceur du serveur MCP de Girabase (utilisé par PyInstaller pour girabase-mcp.exe)."""
import sys

from girabase.mcp.serveur import main

if __name__ == "__main__":
    sys.exit(main())
