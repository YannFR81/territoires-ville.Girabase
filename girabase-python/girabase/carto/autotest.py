"""Auto-contrôle de la localisation sur la carte, enchaîné par « Girabase.exe --autotest [dossier] ».

Rejoue hors ligne le cas du giratoire D71 / D41 à Lombers (Tarn) à partir d'un extrait de la BD TOPO
embarqué : détection de l'anneau et des branches, coordonnées Lambert-93 et CC44, export KML et
projet Girabase. Ouvre ensuite la fenêtre hors écran, en fait une capture, et teste l'accès aux
services de l'IGN (information seulement : l'absence de réseau n'est pas un échec).
Compte rendu dans autotest_localisation.txt ; code de sortie 0 si tout est conforme.
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

CLIC = (43.816139, 2.169778)          # centre relevé sur Google Maps : 43°48'58.1"N 2°10'11.2"E


def _donnees(nom: str = "bdtopo_lombers_d71_d41.json") -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent.parent))
    for p in (base / "girabase" / "carto" / "donnees", Path(__file__).resolve().parent / "donnees"):
        if (p / nom).exists():
            return p / nom
    raise FileNotFoundError(nom)


def _verifier(lignes: list[str], libelle: str, obtenu, attendu) -> bool:
    ok = obtenu == attendu
    lignes.append(f"{'OK   ' if ok else 'ÉCART'} {libelle} : {obtenu!r}" + ("" if ok else f" (attendu {attendu!r})"))
    return ok


def _test_reseau(lignes: list[str]) -> None:
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtNetwork import QNetworkReply

    from .geoservices import FONDS, url_tuile
    from .gui.client import creer_gestionnaire, requete
    nam = creer_gestionnaire()
    boucle = QEventLoop()
    rep = nam.get(requete(url_tuile(FONDS["ortho"], 265173, 191013, 19)))
    rep.finished.connect(boucle.quit)
    QTimer.singleShot(20000, boucle.quit)
    boucle.exec()
    if rep.isFinished() and rep.error() == QNetworkReply.NoError:
        lignes.append(f"Réseau : tuile IGN reçue ({len(bytes(rep.readAll()))} octets)")
    else:
        lignes.append(f"Réseau : services IGN injoignables ({rep.errorString() or 'délai dépassé'}) "
                      "— information, pas un échec")


def executer(dossier: str | None = None) -> int:
    sortie = Path(dossier) if dossier else Path.cwd()
    sortie.mkdir(parents=True, exist_ok=True)
    lignes: list[str] = []
    ok = True
    try:
        from .. import __version__, gbs
        from . import analyse as A
        from .geoservices import Commune, lire_routes
        from .kml import exporter_kml
        from .projections import format_dms
        from .site import SiteCarto
        lignes.append(f"Girabase {__version__} — localisation — auto-contrôle")
        troncons = lire_routes(json.loads(_donnees().read_text(encoding="utf-8")))
        an = A.detecter_anneau(troncons, *CLIC)
        ok &= _verifier(lignes, "Centre de l'anneau", format_dms(an.lat, an.lon), "43°48'58.1\"N 2°10'11.2\"E")
        lignes.append(f"      rayon de l'axe {an.rayon_axe:.2f} m, écart-type {an.ecart_type:.2f} m")
        site = SiteCarto(lat=an.lat, lon=an.lon, commune=Commune("Lombers", "81147", "", "81"), R=4, Bf=2, LA=7,
                         rayon_axe_bdtopo=an.rayon_axe)
        for b in A.detecter_branches(troncons, an.lat, an.lon, an.rayon_axe):
            site.ajouter_branche(b.azimut, b.numero, b.nom_voie, "BD TOPO")
        site.choisir_branche1_nord()
        g = site.vers_giratoire()
        ok &= _verifier(lignes, "Branches", [b.nom for b in g.branches],
                        ["D71 Nord", "D41 Ouest", "D71 Sud", "D41 Est"])
        ok &= _verifier(lignes, "Angles Girabase", [b.angle for b in g.branches], [0, 81, 186, 270])
        from .projections import CC, LAMBERT93, zone_cc
        x, y = LAMBERT93.depuis_geo(*CLIC)                       # coordonnée Google Maps convertie
        z = zone_cc(CLIC[0])
        xc, yc = CC[z].depuis_geo(*CLIC)
        ok &= _verifier(lignes, "Lambert-93 du point Google (m)", (round(x, 1), round(y, 1)), (633197.5, 6302254.0))
        ok &= _verifier(lignes, f"CC{z} du point Google (m)", (round(xc, 1), round(yc, 1)), (1633212.2, 3179909.0))
        ok &= _verifier(lignes, "Anneau estimé (R, Bf, LA)", A.estimer_anneau(an.rayon_axe), (5.0, 2.0, 7.0))
        # Carrefour plan en T (D612 / D141 près de Réalmont) : nœud du réseau et branches
        tr_t = lire_routes(json.loads(_donnees("bdtopo_realmont_d612_d141.json").read_text(encoding="utf-8")))
        car = A.detecter_carrefour(tr_t, 43.76120, 2.17490)
        ok &= _verifier(lignes, "Carrefour en T", (car.degre, [b.nom for b in A.detecter_branches(tr_t, car.lat,
                        car.lon, None)]), (3, ["D612 Nord", "D612 Sud", "D141 Nord"]))
        # Outre-mer : UTM du système légal (La Réunion, valeur de référence PROJ)
        from .projections import systeme_legal
        leg = systeme_legal(-20.8789, 55.4481)
        ok &= _verifier(lignes, "Saint-Denis (La Réunion)", (leg.nom, round(leg.x, 2), round(leg.y, 2)),
                        ("RGR92 / UTM 40S", 338568.32, 7690475.44))
        exporter_kml(site, sortie / "autotest_localisation.kml")
        lignes.append("KML : autotest_localisation.kml")
        from ..constantes import Milieu
        g.milieu = Milieu.RASE_CAMPAGNE
        gbs.ecrire(g, sortie / "autotest_localisation.gbs")
        relu = gbs.lire(sortie / "autotest_localisation.gbs")
        ok &= _verifier(lignes, "Projet .gbs relu", [(b.nom, b.angle) for b in relu.branches],
                        [(b.nom, b.angle) for b in g.branches])

        # Fenêtre hors écran (données embarquées, sans attendre le réseau)
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        from .gui.fenetre import FenetreLocalisation
        fen = FenetreLocalisation()
        fen.resize(1500, 900)
        fen.troncons, fen.troncons_ou = troncons, CLIC
        fen.site.R = 4
        fen._detecter_giratoire(*CLIC)
        fen.show()
        for _ in range(20):
            app.processEvents()
        ok &= _verifier(lignes, "Fenêtre : branches détectées", fen.table.rowCount(), 4)
        fen.grab().save(str(sortie / "autotest_localisation.png"))
        lignes.append("Capture : autotest_localisation.png")
        fen.modifie = False
        _test_reseau(lignes)
        fen.close()
    except Exception:  # noqa: BLE001 — compte rendu complet en cas d'échec
        ok = False
        lignes.append(traceback.format_exc())
    lignes.append("RÉSULTAT : CONFORME" if ok else "RÉSULTAT : ÉCHEC")
    (sortie / "autotest_localisation.txt").write_text("\n".join(lignes), encoding="utf-8")
    return 0 if ok else 1
