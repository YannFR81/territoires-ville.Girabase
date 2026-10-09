"""Serveur MCP de Girabase : protocole (stdio, JSON-RPC 2.0) et outils, sans réseau."""
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from girabase.mcp.outils import OUTILS, ErreurOutil, Girabase

RACINE = Path(__file__).resolve().parent.parent
GUIDE = RACINE / "exemples" / "exemple_guide_certu.gbs"
DONNEES = RACINE / "tests" / "donnees" / "bdtopo_lombers_d71_d41.json"


class FauxClient:
    def __init__(self):
        self.urls = []

    def obtenir_json(self, url):
        self.urls.append(url)
        if "troncon_de_route" in url:
            return json.loads(DONNEES.read_text(encoding="utf-8"))
        if "commune" in url:
            return {"features": [{"properties": {"nom_officiel": "Lombers", "code_insee": "81147"}}]}
        return {"features": [{"properties": {"label": "Lombers", "type": "municipality"},
                              "geometry": {"coordinates": [2.1427, 43.8085]}}]}


def _echanger(messages):
    entree = "\n".join(json.dumps(m) for m in messages) + "\n"
    proc = subprocess.run([sys.executable, "-m", "girabase.mcp"], input=entree, capture_output=True, text=True,
                          encoding="utf-8", cwd=RACINE, timeout=60)
    return [json.loads(l) for l in proc.stdout.splitlines() if l.strip()], proc.stderr


def test_protocole_stdio():
    reponses, journal = _echanger([
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "calculer_capacite", "arguments": {"fichier_gbs": str(GUIDE)}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "inexistant", "arguments": {}}},
        {"jsonrpc": "2.0", "id": 5, "method": "ping"},
        {"jsonrpc": "2.0", "id": 6, "method": "resources/list"},
    ])
    assert [r["id"] for r in reponses] == [1, 2, 3, 4, 5, 6]          # pas de réponse à la notification
    init = reponses[0]["result"]
    assert init["protocolVersion"] == "2025-06-18" and init["serverInfo"]["name"] == "girabase"
    assert "tools" in init["capabilities"]
    noms = [t["name"] for t in reponses[1]["result"]["tools"]]
    assert noms == ["calculer_capacite", "lire_projet_gbs", "ecrire_projet_gbs", "analyser_carrefour",
                    "convertir_coordonnees", "rechercher_lieu", "exporter_kml"]
    res = reponses[2]["result"]
    assert not res["isError"]
    br = res["structuredContent"]["resultats"][0]["branches"]
    # Figure 2.6 du guide Girabase 4 : résultats identiques au logiciel d'origine
    assert [b["affichage_girabase"]["reserve_pct"] for b in br] == ["-122 %", "-5 %", "0 %", "-16 %"]
    assert [b["affichage_girabase"]["attente_moyenne"] for b in br] == ["2193 s", "145 s", "101 s", "290 s"]
    assert json.loads(res["content"][0]["text"]) == res["structuredContent"]
    assert reponses[3]["error"]["code"] == -32602
    assert reponses[4]["result"] == {}
    assert reponses[5]["error"]["code"] == -32601
    assert "prêt" in journal                                        # journal sur stderr, stdout réservé


def test_version_ancienne_et_json_invalide():
    reponses, _ = _echanger([{"jsonrpc": "2.0", "id": 1, "method": "initialize",
                              "params": {"protocolVersion": "2024-11-05"}}])
    assert reponses[0]["result"]["protocolVersion"] == "2024-11-05"
    proc = subprocess.run([sys.executable, "-m", "girabase.mcp"], input="pas du json\n", capture_output=True,
                          text=True, cwd=RACINE, timeout=60)
    assert json.loads(proc.stdout)["error"]["code"] == -32700


def test_schemas_des_outils():
    for o in OUTILS:
        assert o["inputSchema"]["type"] == "object" and o["description"] and o["title"]
        assert "readOnlyHint" in o["annotations"]


def test_chaine_complete_hors_ligne(tmp_path):
    gb = Girabase(FauxClient())
    a = gb.appeler("analyser_carrefour", {"position": "43°48'58.1\"N 2°10'11.2\"E", "milieu": "rase_campagne"})
    assert a["nature"] == "giratoire existant" and a["commune"] == {"nom": "Lombers", "insee": "81147"}
    assert [(b["nom"], round(b["angle_girabase_deg"])) for b in a["branches"]] == [
        ("D71 Nord", 0), ("D41 Ouest", 81), ("D71 Sud", 186), ("D41 Est", 270)]
    assert a["centre"]["systeme_legal"]["nom"] == "RGF93 Lambert-93" and a["centre"]["cc"]["nom"] == "RGF93 CC44"
    assert a["anneau_propose"] == {"R": 5.0, "Bf": 2.0, "LA": 7.0, "Rg": 14.0}
    assert "Etalab 2.0" in a["sources"]
    # L'IA complète les trafics puis calcule
    g = a["giratoire"]
    g["periodes"] = [{"nom": "HPM", "trafics_uvp": [[0, 150, 380, 90], [120, 0, 110, 230],
                                                    [340, 70, 0, 80], [100, 250, 70, 0]]}]
    r = gb.appeler("calculer_capacite", {"giratoire": g})
    assert r["erreurs"] == [] and r["milieu"] == "rase_campagne"
    assert all(b["capacite_uvp_h"] > 0 and b["niveau"] for b in r["resultats"][0]["branches"])
    # Projet .gbs et KML
    projet = tmp_path / "lombers.gbs"
    gb.appeler("ecrire_projet_gbs", {"fichier": str(projet), "giratoire": g})
    relu = gb.appeler("lire_projet_gbs", {"fichier": str(projet)})
    assert [b["angle"] for b in relu["branches"]] == [0, 81, 186, 270]
    assert relu["periodes"][0]["trafics_uvp"][0] == [0, 150, 380, 90]
    with pytest.raises(ErreurOutil):                                   # pas d'écrasement implicite
        gb.appeler("ecrire_projet_gbs", {"fichier": str(projet), "giratoire": g})
    kml = tmp_path / "lombers.kml"
    gb.appeler("exporter_kml", {"fichier": str(kml), "site": a["site"]})
    noms = [n.text for n in ET.parse(kml).getroot().iter("{http://www.opengis.net/kml/2.2}name")]
    assert "1. D71 Nord" in noms and noms.count("Îlot séparateur") == 4


def test_erreurs_claires():
    gb = Girabase(FauxClient())
    with pytest.raises(ErreurOutil, match="milieu"):
        gb.appeler("calculer_capacite", {"giratoire": {"branches": [{"nom": "A", "angle": 0},
                                                                    {"nom": "B", "angle": 120},
                                                                    {"nom": "C", "angle": 240}]}})
    with pytest.raises(ErreurOutil, match="3 à 8 branches"):
        gb.appeler("calculer_capacite", {"giratoire": {"milieu": "periurbain", "branches": []}})
    with pytest.raises(ErreurOutil, match="matrice 3 × 3"):
        gb.appeler("calculer_capacite", {"giratoire": {"milieu": "periurbain", "branches": [
            {"nom": "A", "angle": 0}, {"nom": "B", "angle": 120}, {"nom": "C", "angle": 240}],
            "periodes": [{"nom": "HPM", "trafics_uvp": [[0, 1], [1, 0]]}]}})
    with pytest.raises(ErreurOutil, match="introuvable"):
        gb.appeler("lire_projet_gbs", {"fichier": "/nulle/part.gbs"})
    c = gb.appeler("convertir_coordonnees", {"position": "633197.48 6302254.01"})
    assert c["format_reconnu"] == "Lambert-93" and c["wgs84"]["dms"] == "43°48'58.1\"N 2°10'11.2\"E"
    r = gb.appeler("convertir_coordonnees", {"position": "-21.3314, 55.4721"})
    assert r["systeme_legal"]["nom"] == "RGR92 / UTM 40S" and "cc" not in r


def test_messages_mal_formes_sans_arret_du_serveur():
    reponses, journal = _echanger([
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": "pas un objet"},
        {"jsonrpc": "2.0", "id": 2, "method": 42},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": 7}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "calculer_capacite",
                                                                       "arguments": [1, 2]}},
        [1, "x"],
        "texte",
        {"jsonrpc": "2.0", "id": 5, "method": "initialize", "params": {"protocolVersion": "2025-11-25"}},
        {"jsonrpc": "2.0", "id": 6, "method": "ping"},
    ])
    par_id = {r["id"]: r for r in reponses if isinstance(r, dict) and r.get("id") is not None}
    assert par_id[1]["error"]["code"] == -32602
    assert par_id[2]["error"]["code"] == -32600
    assert par_id[3]["error"]["code"] == -32602 and par_id[4]["error"]["code"] == -32602
    assert par_id[5]["result"]["protocolVersion"] == "2025-11-25"
    assert par_id[6]["result"] == {}                          # toujours en service


def test_outils_d_ecriture_signales_destructifs():
    for o in OUTILS:
        if "remplacer" in o["inputSchema"]["properties"]:
            assert o["annotations"]["destructiveHint"] is True and o["annotations"]["readOnlyHint"] is False
