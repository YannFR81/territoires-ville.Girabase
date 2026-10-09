"""Vue cartographique : tuiles web (IGN, OSM) à opacité réglable et dessin du giratoire à l'échelle."""
from __future__ import annotations

import math
from typing import Optional

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QPixmap, QPolygonF, QTransform
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (QGraphicsEllipseItem, QGraphicsItem, QGraphicsPathItem, QGraphicsPixmapItem,
                               QGraphicsRectItem, QGraphicsScene, QGraphicsSimpleTextItem, QGraphicsView)

from ..analyse import cardinal8
from ..geoservices import CADASTRE, FONDS, ROUTES, Fond, Troncon, fond_effectif, url_tuile
from ..projections import (DEMI_MONDE, azimut, coin_tuile, depuis_mercator, point_azimut, taille_tuile, tuile_de,
                           vers_mercator)
from ..site import SiteCarto
from .client import delai_reessai, requete

ORANGE, BLEU, VERT, LIE = QColor("#DD590A"), QColor("#5E99C5"), QColor("#179D87"), QColor("#7F0541")
NIVEAU_MIN, NIVEAU_MAX = 5.0, 21.0
FRANCE = (46.6, 2.45, 560000.0)          # centre et rayon (m) de la vue « France entière »
MAX_TUILES = 450


def geo_vers_scene(lat: float, lon: float) -> QPointF:
    x, y = vers_mercator(lat, lon)
    return QPointF(x, -y)


def scene_vers_geo(p: QPointF) -> tuple[float, float]:
    return depuis_mercator(p.x(), -p.y())


def _crayon(couleur: QColor, largeur: float, style=Qt.SolidLine) -> QPen:
    p = QPen(couleur, largeur, style)
    p.setCosmetic(True)
    p.setCapStyle(Qt.RoundCap)
    p.setJoinStyle(Qt.RoundJoin)
    return p


class CarteVue(QGraphicsView):
    centre_place = Signal(float, float)
    axe_trace = Signal(float, float)
    centre_deplace = Signal(float, float, bool)       # lat, lon, déplacement terminé
    branche_deplacee = Signal(int, float, bool)       # indice dans site.branches, azimut, terminé
    branche_cliquee = Signal(int)
    branche_menu = Signal(int, QPoint)                # clic droit sur une poignée de branche
    curseur = Signal(float, float)                    # position de la souris (lat, lon)
    carrefour_pointe = Signal(float, float)           # outil « Pointer le carrefour »
    menu_carte = Signal(float, float, QPoint)         # clic droit sur la carte
    mentions_cliquees = Signal()                      # clic sur les mentions de source (licences)
    vue_changee = Signal()

    def __init__(self, nam: QNetworkAccessManager, parent=None):
        super().__init__(parent)
        self.nam = nam
        scene = QGraphicsScene(self)
        scene.setSceneRect(-DEMI_MONDE, -DEMI_MONDE, 2 * DEMI_MONDE, 2 * DEMI_MONDE)
        self.setScene(scene)
        self.setBackgroundBrush(QColor("#ffffff"))
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform | QPainter.TextAntialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setTransformationAnchor(QGraphicsView.NoAnchor)
        self.setResizeAnchor(QGraphicsView.NoAnchor)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setMouseTracking(True)
        self.niveau = 6.0
        self.centre_vue = geo_vers_scene(*FRANCE[:2])
        self.mode_fond = "auto"
        self.fond: Fond = FONDS[fond_effectif(self.mode_fond, self.niveau)]
        self.opacite = 0.5
        self.cadastre = False
        self.routes = True
        self.consigne = ""
        # Voile blanc au-dessus de la photographie : opacité réglable sans superposition des niveaux de tuiles
        self.voile = QGraphicsRectItem(QRectF(-DEMI_MONDE, -DEMI_MONDE, 2 * DEMI_MONDE, 2 * DEMI_MONDE))
        self.voile.setPen(QPen(Qt.NoPen))
        self.voile.setZValue(-60)
        scene.addItem(self.voile)
        self.mode = "deplacer"
        self.tuiles: dict[tuple, QGraphicsPixmapItem] = {}
        self.attente: dict[tuple, QNetworkReply] = {}
        self.essais: dict[tuple, int] = {}
        self.elements: list[QGraphicsItem] = []
        self._pan: Optional[QPointF] = None
        self._appui: Optional[QPointF] = None
        self._deplacee = False
        self._glisse: Optional[tuple] = None
        self._ajustement: Optional[tuple] = None
        self.minuteur = QTimer(self)
        self.minuteur.setSingleShot(True)
        self.minuteur.setInterval(60)
        self.minuteur.timeout.connect(self._charger_tuiles)
        self._maj_voile()
        self._appliquer()

    # ------------------------------------------------------------------ vue
    @property
    def echelle(self) -> float:
        """Pixels écran par mètre Mercator."""
        return 256 * 2 ** self.niveau / (2 * DEMI_MONDE)

    def _opacite_routes(self) -> float:
        """Couche Routes plus discrète au-delà du niveau 18, où ses tuiles sont agrandies."""
        return 0.8 if self.niveau <= 18.25 else 0.45

    def _appliquer(self) -> None:
        self._maj_fond()
        op = self._opacite_routes()
        for cle, it in self.tuiles.items():
            if cle[0] == "routes":
                it.setOpacity(op)
        s = self.echelle
        self.setTransform(QTransform.fromScale(s, s))
        self.centerOn(self.centre_vue)
        self.minuteur.start()
        self.vue_changee.emit()
        self.viewport().update()

    def centrer(self, lat: float, lon: float, niveau: Optional[float] = None) -> None:
        self._ajustement = None                  # un centrage explicite annule un cadrage en attente
        if niveau is not None:
            self.niveau = max(NIVEAU_MIN, min(NIVEAU_MAX, niveau))
        self.centre_vue = geo_vers_scene(lat, lon)
        self._appliquer()

    def ajuster(self, lat: float, lon: float, rayon: float) -> None:
        """Centre la vue sur (lat, lon) avec un cercle de « rayon » mètres visible en entier."""
        if not self.isVisible():                 # taille de la vue encore inconnue : à l'affichage
            self.centrer(lat, lon, 19 if rayon < 1000 else 6)
            self._ajustement = (lat, lon, rayon)
            return
        self._ajustement = None
        demi = max(100.0, min(self.viewport().width(), self.viewport().height()) / 2 - 10)
        n = math.log2(demi * math.cos(math.radians(lat)) * 2 * DEMI_MONDE / (256 * max(rayon, 5.0)))
        self.centrer(lat, lon, min(20.0, math.floor(n * 4) / 4))

    def centre_geo(self) -> tuple[float, float]:
        return scene_vers_geo(self.centre_vue)

    def zoomer(self, delta: float, ancre: Optional[QPointF] = None) -> None:
        avant = self.echelle
        self.niveau = max(NIVEAU_MIN, min(NIVEAU_MAX, self.niveau + delta))
        apres = self.echelle
        if ancre is not None:
            milieu = QPointF(self.viewport().width() / 2, self.viewport().height() / 2)
            p = self.centre_vue + (ancre - milieu) / avant
            self.centre_vue = p - (ancre - milieu) / apres
        self._appliquer()

    def voir_france(self) -> None:
        self.ajuster(*FRANCE)

    def set_fond(self, mode: str) -> None:
        """Mode de fond : « auto » (Plan IGN puis photo), « auto_osm », « ortho », « plan » ou « osm »."""
        self.mode_fond = mode
        self._appliquer()

    def _maj_fond(self) -> None:
        code = fond_effectif(self.mode_fond, self.niveau)
        if code == self.fond.code:
            return
        self.fond = FONDS[code]
        for cle in [k for k in self.tuiles if k[0] not in (code, "cadastre", "routes")]:
            self.scene().removeItem(self.tuiles.pop(cle))
        for cle, it in self.tuiles.items():
            if cle[0] == "routes":
                it.setVisible(self.routes_visibles)
        self._maj_voile()

    @property
    def photo(self) -> bool:
        return self.fond.code == "ortho"

    @property
    def routes_visibles(self) -> bool:
        """La couche Routes de l'IGN est superposée à la photographie (le plan contient déjà les routes)."""
        return self.routes and self.photo

    def _maj_voile(self) -> None:
        self.voile.setBrush(QBrush(QColor(255, 255, 255, int(round(255 * (1 - self.opacite))))))
        self.voile.setVisible(self.photo and self.opacite < 1)

    def set_opacite(self, v: float) -> None:
        """Opacité de la photographie aérienne (0 à 1) ; les plans restent opaques."""
        self.opacite = v
        self._maj_voile()

    def set_routes(self, actif: bool) -> None:
        self.routes = actif
        for cle in [k for k in self.tuiles if k[0] == "routes"]:
            self.tuiles[cle].setVisible(self.routes_visibles)
        self.minuteur.start()
        self.viewport().update()

    def set_consigne(self, texte: str) -> None:
        if texte != self.consigne:
            self.consigne = texte
            self.viewport().update()

    def set_cadastre(self, actif: bool) -> None:
        self.cadastre = actif
        for cle in [k for k in self.tuiles if k[0] == "cadastre"]:
            self.tuiles[cle].setVisible(actif)
        self.minuteur.start()

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.viewport().setCursor(Qt.OpenHandCursor if mode == "deplacer" else
                                  Qt.PointingHandCursor if mode == "carrefour" else Qt.CrossCursor)

    # ------------------------------------------------------------------ tuiles
    def _charger_tuiles(self) -> None:
        r = self.mapToScene(self.viewport().rect()).boundingRect()
        couches = [self.fond]
        if self.cadastre and self.niveau >= 13:
            couches.append(CADASTRE)
        if self.routes_visibles and self.niveau >= 6:
            couches.append(ROUTES)
        for fond in couches:
            z = max(0, min(fond.zoom_max, int(round(self.niveau))))
            x0, y0 = tuile_de(r.left(), -r.top(), z)
            x1, y1 = tuile_de(r.right(), -r.bottom(), z)
            n = 2 ** z
            centre = tuile_de(self.centre_vue.x(), -self.centre_vue.y(), z)
            cles = [(fond.code, z, tx % n, ty) for tx in range(x0, x1 + 1) for ty in range(max(0, y0), min(n, y1 + 1))]
            cles.sort(key=lambda c: (c[2] - centre[0]) ** 2 + (c[3] - centre[1]) ** 2)
            for cle in cles:
                if cle not in self.tuiles and cle not in self.attente:
                    self._demander(fond, cle)
        self._nettoyer(r)

    def _demander(self, fond: Fond, cle: tuple) -> None:
        _, z, tx, ty = cle
        rep = self.nam.get(requete(url_tuile(fond, tx, ty, z)))
        self.attente[cle] = rep
        rep.finished.connect(lambda: self._recue(fond, cle, rep))

    def _recue(self, fond: Fond, cle: tuple, rep: QNetworkReply) -> None:
        self.attente.pop(cle, None)
        donnees = bytes(rep.readAll())
        ok = rep.error() == QNetworkReply.NoError
        statut = rep.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        rep.deleteLater()
        if fond.code not in ("cadastre", "routes") and fond.code != self.fond.code:
            return
        pm = QPixmap()
        if not ok or not pm.loadFromData(donnees):
            n = self.essais.get(cle, 0) + 1
            self.essais[cle] = n
            if n < 3:
                delai = int(delai_reessai(rep) * 1000) if statut == 429 else 700 * n
                QTimer.singleShot(delai, lambda: (cle not in self.tuiles and cle not in self.attente)
                                  and self._demander(fond, cle))
            return
        _, z, tx, ty = cle
        it = QGraphicsPixmapItem(pm)
        it.setTransformationMode(Qt.SmoothTransformation)
        it.setScale(taille_tuile(z) / pm.width())
        cx, cy = coin_tuile(tx, ty, z)
        it.setPos(cx, -cy)
        if fond.code == "cadastre":
            it.setZValue(-50 + z / 100)
            it.setOpacity(0.65)                  # parcelles discrètes sous le dessin du giratoire
            it.setVisible(self.cadastre)
        elif fond.code == "routes":
            it.setZValue(-40 + z / 100)
            it.setOpacity(self._opacite_routes())
            it.setVisible(self.routes_visibles)
        else:
            it.setZValue(-100 + z / 100)         # sous le voile (-60) : les niveaux se recouvrent
        self.scene().addItem(it)
        self.tuiles[cle] = it

    def _nettoyer(self, visible: QRectF) -> None:
        if len(self.tuiles) <= MAX_TUILES:
            return
        z_actuel = int(round(self.niveau))
        marge = visible.adjusted(-visible.width(), -visible.height(), visible.width(), visible.height())
        for cle, it in list(self.tuiles.items()):
            if abs(cle[1] - min(z_actuel, 19)) > 2 or not marge.intersects(it.sceneBoundingRect()):
                self.scene().removeItem(it)
                del self.tuiles[cle]

    # ------------------------------------------------------------------ dessin du site
    def _effacer(self) -> None:
        for it in self.elements:
            self.scene().removeItem(it)
        self.elements = []

    def _ajouter(self, it: QGraphicsItem, z: float) -> QGraphicsItem:
        it.setZValue(z)
        self.scene().addItem(it)
        self.elements.append(it)
        return it

    def _chemin(self, pts, ferme: bool = False) -> QPainterPath:
        poly = QPolygonF([geo_vers_scene(la, lo) for la, lo in pts])
        chemin = QPainterPath()
        chemin.addPolygon(poly)
        if ferme:
            chemin.closeSubpath()
        return chemin

    def _texte(self, texte: str, pos: QPointF, fond: QColor, z: float = 30) -> None:
        it = QGraphicsSimpleTextItem(texte)
        f = QFont()
        f.setPointSizeF(9)
        f.setBold(True)
        it.setFont(f)
        it.setBrush(QBrush(QColor("#ffffff")))
        it.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        br = it.boundingRect()
        cadre = QGraphicsRectItem(QRectF(-4, -3, br.width() + 8, br.height() + 6))
        cadre.setBrush(QBrush(fond))
        cadre.setPen(QPen(Qt.NoPen))
        cadre.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        for x in (cadre, it):
            x.setPos(pos)
            x.setTransform(QTransform().translate(-br.width() / 2, -br.height() / 2))
        self._ajouter(cadre, z)
        self._ajouter(it, z + 0.1)

    def _poignee(self, pos: QPointF, donnee: tuple, couleur: QColor, rayon: float = 7) -> None:
        e = QGraphicsEllipseItem(-rayon, -rayon, 2 * rayon, 2 * rayon)
        e.setBrush(QBrush(couleur))
        e.setPen(_crayon(QColor("#ffffff"), 2))
        e.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        e.setPos(pos)
        e.setData(0, donnee)
        e.setCursor(Qt.SizeAllCursor)
        self._ajouter(e, 40)

    def dessiner(self, site: SiteCarto, troncons: Optional[list[Troncon]] = None, selection: Optional[int] = None,
                 schema: bool = True) -> None:
        self._effacer()
        if troncons:
            for t in troncons:
                coul = QColor(0, 160, 220, 200) if not t.anneau else QColor(0, 160, 220, 120)
                it = QGraphicsPathItem(self._chemin(t.points))
                it.setPen(_crayon(coul, 1.5, Qt.DashLine))
                self._ajouter(it, 5)
        if not site.centre_defini:
            return
        c = geo_vers_scene(site.lat, site.lon)
        # Chaussée annulaire, bande franchissable, îlot central
        anneau = QPainterPath()
        anneau.addPath(self._chemin(site.cercle(site.Rg), True))
        if site.R + site.Bf > 0:
            anneau.addPath(self._chemin(site.cercle(site.R + site.Bf), True))
        it = QGraphicsPathItem(anneau)
        it.setBrush(QBrush(QColor(255, 255, 255, 70)))
        it.setPen(_crayon(ORANGE, 2.5))
        self._ajouter(it, 10)
        if site.Bf > 0:
            it = QGraphicsPathItem(self._chemin(site.cercle(site.R + site.Bf), True))
            it.setPen(_crayon(BLEU, 1.6, Qt.DashLine))
            it.setBrush(QBrush(QColor(94, 153, 197, 60)))
            self._ajouter(it, 11)
        if site.R > 0:
            it = QGraphicsPathItem(self._chemin(site.cercle(site.R), True))
            it.setPen(_crayon(VERT, 2))
            it.setBrush(QBrush(QColor(23, 157, 135, 90)))
            self._ajouter(it, 12)
        # Schéma des voies d'entrée et de sortie
        if schema:
            for calque, pts in site.schema_geo():
                it = QGraphicsPathItem(self._chemin(pts, calque == "GIRA_ILOTS_SEPARATEURS"))
                if calque == "GIRA_ILOTS_SEPARATEURS":
                    it.setBrush(QBrush(QColor(23, 157, 135, 110)))
                    it.setPen(_crayon(VERT, 1.5))
                else:
                    it.setPen(_crayon(ORANGE, 2))
                self._ajouter(it, 13)
        # Axes des branches, poignées et étiquettes
        for k, (b, angle) in enumerate(site.ordre_girabase()):
            i = site.branches.index(b)
            p1 = geo_vers_scene(*point_azimut(site.lat, site.lon, b.azimut, 0.0))
            p2 = geo_vers_scene(*point_azimut(site.lat, site.lon, b.azimut, site.Rg + 35))
            chemin = QPainterPath(p1)
            chemin.lineTo(p2)
            it = QGraphicsPathItem(chemin)
            it.setPen(_crayon(LIE if i == selection else QColor("#ffffff"), 3 if i == selection else 2,
                              Qt.DashDotLine))
            self._ajouter(it, 20)
            self._poignee(p2, ("branche", i), LIE if i == selection else ORANGE)
            pos = geo_vers_scene(*point_azimut(site.lat, site.lon, b.azimut, site.Rg + 52))
            self._texte(f"{k + 1}. {b.nom}\n{b.azimut:.0f}° {cardinal8(b.azimut)}  ·  angle {angle:.0f}°", pos,
                        LIE if i == selection else ORANGE)
        # Centre
        croix = QPainterPath()
        for dx, dy in ((-1, 0), (0, -1)):
            croix.moveTo(c + QPointF(dx * 1.5, dy * 1.5))
            croix.lineTo(c - QPointF(dx * 1.5, dy * 1.5))
        it = QGraphicsPathItem(croix)
        it.setPen(_crayon(LIE, 2))
        self._ajouter(it, 35)
        self._poignee(c, ("centre",), LIE, 6)

    # ------------------------------------------------------------------ souris
    def _donnee_sous(self, pos) -> Optional[tuple]:
        for it in self.items(pos):
            d = it.data(0)
            if d:
                return d
        return None

    SEUIL_GLISSER = 5          # pixels : en deçà, c'est un clic (action de l'outil) ; au-delà, on déplace la carte

    def mousePressEvent(self, ev):
        pos = ev.position().toPoint()
        if ev.button() == Qt.MiddleButton:
            self._pan, self._appui, self._deplacee = ev.position(), None, True
            return
        d = self._donnee_sous(pos)
        if ev.button() == Qt.RightButton:
            if d is not None and d[0] == "branche":
                self.branche_menu.emit(d[1], ev.globalPosition().toPoint())
            else:
                lat, lon = scene_vers_geo(self.mapToScene(pos))
                self.menu_carte.emit(lat, lon, ev.globalPosition().toPoint())
            return
        if ev.button() != Qt.LeftButton:
            return super().mousePressEvent(ev)
        if getattr(self, "_rect_mentions", None) is not None and self._rect_mentions.contains(ev.position()):
            self.mentions_cliquees.emit()        # sources et licences des fonds de carte
            return
        if d is not None:                        # poignée du centre ou d'un axe
            self._glisse = d
            if d[0] == "branche":
                self.branche_cliquee.emit(d[1])
            return
        # Dans tous les modes, glisser déplace la carte ; un simple clic déclenche l'outil au relâchement
        self._pan, self._appui, self._deplacee = ev.position(), ev.position(), False

    def mouseMoveEvent(self, ev):
        lat, lon = scene_vers_geo(self.mapToScene(ev.position().toPoint()))
        self.curseur.emit(lat, lon)
        if self._glisse is not None:
            self._emettre_glisse(lat, lon, False)
            return
        if self._pan is not None:
            if not self._deplacee:
                if (ev.position() - self._appui).manhattanLength() < self.SEUIL_GLISSER:
                    return
                self._deplacee = True
                self.viewport().setCursor(Qt.ClosedHandCursor)
            d = ev.position() - self._pan
            self._pan = ev.position()
            self.centre_vue = self.centre_vue - d / self.echelle
            self._appliquer()
            return
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        if self._glisse is not None:
            lat, lon = scene_vers_geo(self.mapToScene(ev.position().toPoint()))
            self._emettre_glisse(lat, lon, True)
            self._glisse = None
            return
        if self._pan is not None:
            clic = not self._deplacee and self._appui is not None
            appui = self._appui
            self._pan, self._appui, self._deplacee = None, None, False
            self.set_mode(self.mode)
            if clic:
                lat, lon = scene_vers_geo(self.mapToScene(appui.toPoint()))
                if self.mode == "carrefour":
                    self.carrefour_pointe.emit(lat, lon)
                elif self.mode == "centre":
                    self.centre_place.emit(lat, lon)
                elif self.mode == "axe":
                    self.axe_trace.emit(lat, lon)
            return
        super().mouseReleaseEvent(ev)

    def _emettre_glisse(self, lat: float, lon: float, fini: bool) -> None:
        if self._glisse[0] == "centre":
            self.centre_deplace.emit(lat, lon, fini)
        else:
            self._glisse_branche(lat, lon, fini)

    def _glisse_branche(self, lat: float, lon: float, fini: bool) -> None:
        site_lat, site_lon = getattr(self, "_centre_site", (None, None))
        if site_lat is None:
            return
        self.branche_deplacee.emit(self._glisse[1], azimut(site_lat, site_lon, lat, lon), fini)

    def memoriser_centre_site(self, site: SiteCarto) -> None:
        self._centre_site = (site.lat, site.lon) if site.centre_defini else (None, None)

    def mouseDoubleClickEvent(self, ev):
        if ev.button() == Qt.LeftButton and self.mode == "deplacer" and self._donnee_sous(ev.position().toPoint()) is None:
            self._pan = None
            self.zoomer(1.0, ev.position())
            return
        super().mouseDoubleClickEvent(ev)

    def wheelEvent(self, ev):
        crans = ev.angleDelta().y() / 120
        if crans:                                 # un niveau par cran (comme Google Maps) ; Maj : demi-niveau
            self.zoomer((0.5 if ev.modifiers() & Qt.ShiftModifier else 1.0) * crans, ev.position())

    def showEvent(self, ev):
        super().showEvent(ev)
        if self._ajustement:
            QTimer.singleShot(0, lambda: self._ajustement and self.ajuster(*self._ajustement))

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self.centerOn(self.centre_vue)
        self.minuteur.start()

    # ------------------------------------------------------------------ échelle et mentions
    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:
        painter.save()
        painter.resetTransform()
        h = self.viewport().height()
        w = self.viewport().width()
        lat, _ = self.centre_geo()
        m_par_px = math.cos(math.radians(lat)) / self.echelle
        cible = 120 * m_par_px
        puissance = 10 ** math.floor(math.log10(cible))
        longueur = max(v * puissance for v in (1, 2, 5) if v * puissance <= cible)
        px = longueur / m_par_px
        f = QFont()
        f.setPointSizeF(8.5)
        painter.setFont(f)
        painter.setRenderHint(QPainter.Antialiasing, True)
        x0, y0 = 14, h - 18
        rapport = m_par_px / 0.0254 * 96                  # échelle à l'écran (96 points par pouce)
        ordre = 10 ** max(0, math.floor(math.log10(rapport)) - 1)
        txt_echelle = "1/" + f"{round(rapport / ordre) * ordre:,.0f}".replace(",", "\u202f")
        lg_ech = painter.fontMetrics().horizontalAdvance(txt_echelle) + 14
        painter.fillRect(QRectF(x0 - 6, y0 - 22, px + 12 + lg_ech, 30), QColor(255, 255, 255, 200))
        painter.setPen(QColor("#444444"))
        painter.drawText(QRectF(x0 + px + 8, y0 - 14, lg_ech, 16), Qt.AlignLeft | Qt.AlignVCenter, txt_echelle)
        painter.setPen(QPen(QColor("#222222"), 2))
        painter.drawLine(QPointF(x0, y0), QPointF(x0 + px, y0))
        painter.drawLine(QPointF(x0, y0 - 5), QPointF(x0, y0 + 2))
        painter.drawLine(QPointF(x0 + px, y0 - 5), QPointF(x0 + px, y0 + 2))
        txt = f"{longueur:g} m" if longueur < 1000 else f"{longueur / 1000:g} km"
        painter.drawText(QRectF(x0, y0 - 22, px, 16), Qt.AlignCenter, txt)
        mention = (self.fond.attribution + (" · " + ROUTES.attribution if self.routes_visibles else "")
                   + (" · " + CADASTRE.attribution if self.cadastre and self.niveau >= 13 else "") + "  ⓘ")
        fm = painter.fontMetrics()
        lw = fm.horizontalAdvance(mention) + 12
        self._rect_mentions = QRectF(w - lw, h - 18, lw, 18)
        painter.fillRect(QRectF(w - lw, h - 18, lw, 18), QColor(255, 255, 255, 200))
        painter.setPen(QColor("#333333"))
        painter.drawText(QRectF(w - lw, h - 18, lw, 18), Qt.AlignCenter, mention)
        # Nord
        painter.setPen(QPen(QColor("#222222"), 1.5))
        painter.setBrush(QColor(255, 255, 255, 220))
        painter.drawEllipse(QPointF(w - 26, 28), 15, 15)
        fl = QPolygonF([QPointF(w - 26, 16), QPointF(w - 31, 32), QPointF(w - 26, 28), QPointF(w - 21, 32)])
        painter.setBrush(QColor("#7F0541"))
        painter.drawPolygon(fl)
        painter.drawText(QRectF(w - 41, 30, 30, 14), Qt.AlignCenter, "N")
        # Consigne (bandeau en haut de la carte)
        if self.consigne:
            f.setPointSizeF(10)
            f.setBold(True)
            painter.setFont(f)
            fm = painter.fontMetrics()
            lignes = self.consigne.split("\n")
            lw = max(fm.horizontalAdvance(t) for t in lignes) + 28
            lh = fm.height() * len(lignes) + 14
            cadre = QRectF((w - lw) / 2, 10, lw, lh)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(127, 5, 65, 225))
            painter.drawRoundedRect(cadre, 8, 8)
            painter.setPen(QColor("#ffffff"))
            painter.drawText(cadre, Qt.AlignCenter, self.consigne)
        painter.restore()
