"""Fenêtre « Sources des données et licences » (Licence Ouverte 2.0, ODbL, conditions de la Géoplateforme)."""
from __future__ import annotations

import html

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTextBrowser, QVBoxLayout, QWidget

from ..geoservices import AGENT, SOURCES, URL_CGU_GEOPF, URL_ETALAB, URL_LIMITES_GEOPF


def texte_sources() -> str:
    lignes = "".join(
        f"<tr><td>{html.escape(s.usage)}</td><td>{html.escape(s.donnees)}<br/><small>{html.escape(s.service)}</small>"
        f"</td><td>{html.escape(s.producteur)}</td><td><a href='{s.url_licence}'>{html.escape(s.licence)}</a></td></tr>"
        for s in SOURCES)
    return f"""
<h3>Sources des données cartographiques et licences</h3>
<p>La localisation du giratoire utilise les services publics de la <b>Géoplateforme de l'IGN</b>
(<code>data.geopf.fr</code>) et, en option, les tuiles d'<b>OpenStreetMap</b>. Les images et les objets sont
lus à la demande, pour la zone affichée, puis gardés dans un cache local. Seuls deux petits extraits de la
BD TOPO® (deux carrefours du Tarn, extraits le 9 octobre 2026) sont embarqués pour l'auto-contrôle hors
ligne.</p>
<table border="1" cellspacing="0" cellpadding="4">
<tr><th>Usage dans Girabase</th><th>Données / service</th><th>Producteur</th><th>Licence</th></tr>
{lignes}
</table>
<h4>Ce que ces licences demandent, et comment Girabase s'y conforme</h4>
<ul>
<li><b>Licence Ouverte Etalab 2.0</b> (données IGN) : réutilisation libre, y compris commerciale, à condition
de mentionner la source (au minimum le producteur) et la date de dernière mise à jour.
Girabase affiche « © IGN – Géoplateforme » sur la carte et écrit la mention des sources (BD TOPO®,
ADMIN EXPRESS, date de consultation et date de mise à jour des tronçons utilisés ; à défaut, le fond IGN
consulté) dans la localisation du projet .gbs, dans le fichier de site et dans l'export KML. <a href="{URL_ETALAB}">Texte de la licence</a>.</li>
<li><b>Conditions générales d'utilisation de la Géoplateforme</b> : usage raisonnable des API, sans entraver
leur fonctionnement. Limites par adresse IP : 30 requêtes/s pour le WFS, 50 requêtes/s pour le géocodage ; le
WMTS (tuiles) n'est pas limité. Girabase envoie quelques requêtes par analyse de carrefour, respecte le délai
indiqué par le serveur en cas de refus (HTTP 429) et met les tuiles en cache.
<a href="{URL_CGU_GEOPF}">CGU</a> · <a href="{URL_LIMITES_GEOPF}">Limites d'usage</a>.</li>
<li><b>OpenStreetMap</b> : « © contributeurs OpenStreetMap » affiché sur la carte, avec lien vers
<a href="https://www.openstreetmap.org/copyright">openstreetmap.org/copyright</a> (clic sur la mention).
Conformément à la <a href="https://operations.osmfoundation.org/policies/tiles/">politique d'usage des tuiles</a> :
identification de l'application ({html.escape(AGENT)}), cache local respecté, aucun téléchargement en masse ni
préchargement hors de la zone affichée, pas d'usage hors ligne. Pour un usage intensif, préférer le Plan IGN.</li>
<li><b>Google Maps / Street View</b> : non utilisés comme fond de carte (leurs conditions l'interdisent hors de
leurs propres API) ; Girabase ouvre seulement le lieu dans votre navigateur.</li>
</ul>
<p>Les résultats de la localisation (centre, anneau, branches) sont des <b>propositions schématiques</b> à
vérifier sur plan topographique ; l'IGN n'est pas responsable de leur usage.</p>
<p><small>Le logiciel Girabase (portage Python) est distribué sous licence GNU GPL v3 ; il utilise Qt for Python
(PySide6, LGPL v3).</small></p>
"""


def dialogue_sources(parent: QWidget) -> None:
    dlg = QDialog(parent)
    dlg.setWindowTitle("Sources des données et licences")
    dlg.resize(820, 640)
    v = QVBoxLayout(dlg)
    tb = QTextBrowser()
    tb.setOpenExternalLinks(True)
    tb.setHtml(texte_sources())
    v.addWidget(tb)
    bb = QDialogButtonBox(QDialogButtonBox.Close)
    bb.rejected.connect(dlg.reject)
    v.addWidget(bb)
    dlg.exec()
