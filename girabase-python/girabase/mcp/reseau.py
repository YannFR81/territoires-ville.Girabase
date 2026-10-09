"""Accès aux services de la Géoplateforme de l'IGN depuis le serveur MCP (sans Qt).

Respect des conditions d'utilisation : identification de l'application (User-Agent), au plus 5 requêtes par
seconde (limites Géoplateforme : WFS 30/s, géocodage 50/s), délai « Retry-After » respecté après un refus
HTTP 429, nouvelles tentatives limitées.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from typing import Optional

from ..carto.geoservices import AGENT

INTERVALLE_MIN = 0.2          # s entre deux requêtes (5 requêtes/s au plus)
ESSAIS = 3


class ErreurReseau(RuntimeError):
    pass


class ClientGeoplateforme:
    def __init__(self, delai: float = 20.0):
        self.delai = delai
        self._dernier = 0.0
        self._verrou = threading.Lock()

    def _attendre_tour(self) -> None:
        with self._verrou:
            attente = self._dernier + INTERVALLE_MIN - time.monotonic()
            if attente > 0:
                time.sleep(attente)
            self._dernier = time.monotonic()

    def obtenir_json(self, url: str) -> dict:
        derniere: Optional[str] = None
        for essai in range(1, ESSAIS + 1):
            self._attendre_tour()
            req = urllib.request.Request(url, headers={"User-Agent": AGENT, "Accept": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=self.delai) as rep:
                    return json.loads(rep.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                derniere = f"HTTP {exc.code}"
                if exc.code == 429 and essai < ESSAIS:
                    try:
                        attente = float(exc.headers.get("Retry-After") or 5)
                    except ValueError:
                        attente = 5.0
                    time.sleep(min(30.0, max(1.0, attente)))
                    continue
                if exc.code >= 500 and essai < ESSAIS:
                    time.sleep(1.0 * essai)
                    continue
                break
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                derniere = str(getattr(exc, "reason", exc))
                if essai < ESSAIS:
                    time.sleep(1.0 * essai)
                    continue
            except ValueError as exc:
                derniere = f"réponse illisible ({exc})"
                break
        raise ErreurReseau(f"Service de l'IGN injoignable ({derniere}). Vérifiez la connexion Internet ou le "
                           "proxy.")
