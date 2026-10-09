"""Fenêtre « Localisation du giratoire » : fond de carte, centre, axes des branches, anneau, exports."""
from __future__ import annotations

import math
import re
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QEvent, QPoint, QProcess, QSettings, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QDesktopServices, QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout,
                               QFrame, QGridLayout, QHBoxLayout, QHeaderView, QInputDialog, QLabel,
                               QLineEdit, QMainWindow, QMenu, QMessageBox, QPushButton, QScrollArea, QSlider,
                               QSplitter, QTableWidget, QTableWidgetItem, QToolBar, QToolButton, QVBoxLayout,
                               QWidget)

from ... import gbs
from ...constantes import NB_BRANCHES_MAX, NB_BRANCHES_MIN, Milieu
from .. import analyse as A
from ..geoservices import (MODES_FOND, SEUIL_PHOTO, Commune, Lieu, lire_commune, lire_recherche, lire_routes,
                           mention_fond, mention_sources, url_commune, url_recherche, url_routes)
from ..conception import site_depuis_troncons
from ..kml import exporter_kml
from ..projections import CC, analyser_saisie, azimut, en_metropole, format_dms, systeme_legal, vers_local, zone_cc
from ..site import SiteCarto
from .carte import CarteVue
from .client import ClientIGN, creer_gestionnaire
from .encart import Encart
from .theme import feuille_de_style, theme_sombre

TITRE = "Girabase — Localisation du giratoire"

EXT_SITE = ".gsite"
RAYON_ROUTES = 150.0                    # m, rayon de chargement des tronçons BD TOPO
COLONNES = ["N°", "Nom", "Route", "Voie", "Azimut", "Orient.", "Angle", "Entrée", "Îlot", "Sortie"]
AIDES_COLONNES = ["Numéro Girabase (sens de giration depuis la branche n° 1)", "Nom de la branche (modifiable)",
                  "Numéro de route (BD TOPO)", "Nom de la voie (BD TOPO)", "Azimut de l'axe en degrés, sens horaire "
                  "depuis le Nord", "Orientation cardinale", "Angle Girabase en degrés depuis la branche n° 1",
                  "Largeur d'entrée (m) pour le schéma", "Largeur de l'îlot séparateur (m)",
                  "Largeur de sortie (m)"]
EDITABLES = {1, 2, 3, 4, 7, 8, 9}
ZOOM_LIEU = {"municipality": 15, "street": 17, "locality": 17, "housenumber": 18}


def _nombre(texte: str) -> Optional[float]:
    try:
        return float(texte.replace(",", ".").replace("°", "").replace("m", "").strip())
    except ValueError:
        return None


def _fr(v: float, dec: int = 2) -> str:
    return f"{v:,.{dec}f}".replace(",", " ").replace(".", ",")


class FenetreLocalisation(QMainWindow):
    """Conception schématique géoréférencée d'un giratoire, à intégrer ensuite à Girabase."""

    giratoire_cree = Signal(object)          # Giratoire Girabase créé à partir du site
    envoi_demande = Signal(object)           # SiteCarto à reprendre dans la fenêtre principale de Girabase

    def __init__(self, chemin: Optional[str] = None, liee: bool = False):
        super().__init__()
        self.liee = liee                         # ouverte depuis Girabase : bouton « Envoyer dans Girabase »
        self.reglages = QSettings()
        self.site = SiteCarto()
        self.troncons: list = []
        self.troncons_ou: Optional[tuple[float, float]] = None
        self.selection: Optional[int] = None
        self.b1_manuel = False
        self.cc_auto = True
        self.chemin: Optional[Path] = None
        self.modifie = False
        self._remplissage = False
        self._jetons = {"commune": 0, "routes": 0}
        self._attente_routes: list = []
        self.nam = creer_gestionnaire(self)
        self.client = ClientIGN(self.nam, self)
        self.resize(1400, 860)
        self._sombre: Optional[bool] = None
        self._appliquer_theme()
        QGuiApplication.styleHints().colorSchemeChanged.connect(self._schema_couleurs_change)

        self.carte = CarteVue(self.nam, self)
        panneau = self._panneau()
        defil = QScrollArea()
        defil.setWidgetResizable(True)
        defil.setWidget(panneau)
        defil.setMinimumWidth(540)
        sep = QSplitter(Qt.Horizontal)
        sep.addWidget(self.carte)
        sep.addWidget(defil)
        sep.setStretchFactor(0, 1)
        sep.setSizes([1000, 560])
        self.setCentralWidget(sep)
        self._barre_outils()
        self._menus()
        self.lbl_curseur = QLabel()
        self.lbl_reseau = QLabel()
        self.statusBar().addPermanentWidget(self.lbl_curseur)
        self.statusBar().addPermanentWidget(self.lbl_reseau)

        c = self.carte
        c.centre_place.connect(self.placer_centre)
        c.axe_trace.connect(self.tracer_axe)
        c.centre_deplace.connect(self._centre_deplace)
        c.branche_deplacee.connect(self._branche_deplacee)
        c.branche_cliquee.connect(self._selectionner_branche)
        c.branche_menu.connect(self._menu_branche)
        c.curseur.connect(self._curseur)
        c.carrefour_pointe.connect(self.analyser_carrefour)
        c.menu_carte.connect(self._menu_carte)
        c.vue_changee.connect(self._maj_consigne)
        c.mentions_cliquees.connect(self.sources_et_licences)
        for touche, slot in ((Qt.Key_Escape, lambda: self.choisir_mode("deplacer")),
                             (Qt.Key_G, lambda: self.choisir_mode("carrefour")),
                             (Qt.Key_C, lambda: self.choisir_mode("centre")),
                             (Qt.Key_A, lambda: self.choisir_mode("axe")),
                             (Qt.Key_Delete, self.supprimer_branche)):
            # Touches actives quand la carte a le focus (un clic sur la carte le lui donne) : elles ne gênent ni
            # la saisie dans le tableau des branches ni la barre de recherche.
            raccourci = QShortcut(QKeySequence(touche), self.carte, slot)
            raccourci.setContext(Qt.WidgetWithChildrenShortcut)

        self._restaurer()
        if chemin:
            self.ouvrir(chemin)
        self._tout_rafraichir()
        self._titre()

    # ================================================================== construction
    def _barre_outils(self) -> None:
        """Une seule ligne : recherche, France entière, fond, opacité de la photo, couches."""
        tb = QToolBar("Carte")
        tb.setMovable(False)
        self.addToolBar(tb)
        self.saisie = QLineEdit()
        self.saisie.setPlaceholderText("Commune, adresse ou coordonnées (43°48'58.1\"N 2°10'11.2\"E · "
                                       "43.8161, 2.1698 · X Y Lambert-93 ou CC44)")
        self.saisie.setClearButtonEnabled(True)
        self.saisie.setMinimumWidth(300)
        self.saisie.returnPressed.connect(self.rechercher)
        tb.addWidget(self.saisie)
        b = QPushButton("Rechercher")
        b.clicked.connect(self.rechercher)
        tb.addWidget(b)
        b = QPushButton("France entière")
        b.setToolTip("Revenir à la carte de France (Ctrl+F)")
        b.clicked.connect(self.carte.voir_france)
        tb.addWidget(b)
        tb.addSeparator()
        tb.addWidget(QLabel(" Fond : "))
        self.cb_fond = QComboBox()
        for code, libelle in MODES_FOND.items():
            self.cb_fond.addItem(libelle, code)
        self.cb_fond.setToolTip(f"En mode automatique, la photographie aérienne remplace le plan à partir du "
                                f"niveau de zoom {SEUIL_PHOTO}")
        self.cb_fond.currentIndexChanged.connect(self._changer_fond)
        tb.addWidget(self.cb_fond)
        tb.addWidget(QLabel("  Opacité photo : "))
        self.sl_opacite = QSlider(Qt.Horizontal)
        self.sl_opacite.setRange(0, 100)
        self.sl_opacite.setValue(50)
        self.sl_opacite.setFixedWidth(90)
        self.sl_opacite.setToolTip("Transparence de la photographie aérienne sous le dessin du giratoire")
        self.sl_opacite.valueChanged.connect(self._changer_opacite)
        tb.addWidget(self.sl_opacite)
        self.lbl_opacite = QLabel("50 %")
        self.lbl_opacite.setMinimumWidth(40)
        tb.addWidget(self.lbl_opacite)
        tb.addSeparator()
        self.bt_couches = QToolButton()
        self.bt_couches.setText("Couches ")
        self.bt_couches.setToolTip("Couches affichées sur la carte")
        self.bt_couches.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(self.bt_couches)
        menu.setToolTipsVisible(True)

        def couche(texte: str, aide: str, coche: bool, slot) -> QAction:
            a = menu.addAction(texte)
            a.setCheckable(True)
            a.setChecked(coche)
            a.setToolTip(aide)
            a.toggled.connect(slot)
            return a

        self.ck_routes_ign = couche("Routes IGN (sur la photographie)", "Couche « Routes » de cartes.gouv.fr : "
                                    "numéros et noms des routes", True, self.carte.set_routes)
        self.ck_cadastre = couche("Parcelles cadastrales", "Parcellaire Express de l'IGN", False,
                                  self._changer_cadastre)
        self.ck_routes = couche("Tronçons BD TOPO analysés", "Axes des tronçons de la BD TOPO utilisés pour "
                                "l'analyse du carrefour", False, lambda _: self._dessiner())
        self.ck_schema = couche("Schéma des voies du projet", "Bords de chaussée et îlots séparateurs du schéma "
                                "Girabase", True, lambda _: self._dessiner())
        self.bt_couches.setMenu(menu)
        tb.addWidget(self.bt_couches)

    def _menus(self) -> None:
        m = self.menuBar().addMenu("&Fichier")
        self._act(m, "Nouveau site", self.nouveau, QKeySequence.New)
        self._act(m, "Ouvrir un site…", self.ouvrir_dialogue, QKeySequence.Open)
        self._act(m, "Enregistrer le site", self.enregistrer, QKeySequence.Save)
        self._act(m, "Enregistrer le site sous…", self.enregistrer_sous, QKeySequence.SaveAs)
        m.addSeparator()
        self._act(m, "Exporter en KML (Google Earth, QGIS)…", self.exporter_kml, "Ctrl+K")
        self._act(m, "Créer le projet Girabase (.gbs)…", self.creer_gbs, "Ctrl+G")
        if self.liee:
            self._act(m, "Envoyer dans Girabase", self.envoyer_dans_girabase, "Ctrl+Return")
        m.addSeparator()
        self._act(m, "Quitter", self.close, QKeySequence.Quit)
        m = self.menuBar().addMenu("&Carte")
        self._act(m, "France entière", self.carte.voir_france, "Ctrl+F")
        self._act(m, "Centrer sur le giratoire", self.centrer_giratoire, "Ctrl+Home")
        self._act(m, "Analyser le carrefour (BD TOPO)", self.detecter_giratoire, "Ctrl+D")
        self._act(m, "Détecter les branches (BD TOPO)", self.detecter_branches, "Ctrl+B")
        m.addSeparator()
        self._act(m, "Ouvrir dans Google Maps", lambda: self._ouvrir_web("gmaps"))
        self._act(m, "Ouvrir dans Street View", lambda: self._ouvrir_web("streetview"))
        self._act(m, "Ouvrir dans le Géoportail", lambda: self._ouvrir_web("geoportail"))
        m = self.menuBar().addMenu("&?")
        self._act(m, "Mode d'emploi", self.aide)
        self._act(m, "Sources des données et licences", self.sources_et_licences)

    def _act(self, menu, texte, slot, raccourci=None) -> QAction:
        a = QAction(texte, self)
        if raccourci:
            a.setShortcut(QKeySequence(raccourci))
        a.triggered.connect(slot)
        menu.addAction(a)
        return a

    def _selectionnable(self, texte: str = "—") -> QLabel:
        lbl = QLabel(texte)
        lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lbl.setObjectName("valeur")
        return lbl

    def _panneau(self) -> QWidget:
        """Panneau latéral : outils de la carte en tête, puis encarts repliables (résumé sur deux lignes)."""
        w = QWidget()
        w.setObjectName("panneau")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(6)

        # --- Outils de la carte (toujours visibles) ---------------------------
        cadre = QFrame()
        cadre.setObjectName("encart")
        v = QVBoxLayout(cadre)
        v.setContentsMargins(8, 4, 8, 8)
        v.setSpacing(6)
        tete = QHBoxLayout()
        titre = QLabel("Outils de la carte")
        titre.setObjectName("titre_outils")
        tete.addWidget(titre)
        tete.addStretch(1)
        for texte, ouvert, aide in (("Tout replier", False, "Replier tous les encarts (résumés sur deux lignes)"),
                                    ("Tout déplier", True, "Déplier tous les encarts")):
            b = QToolButton()
            b.setText(texte)
            b.setObjectName("lien")
            b.setAutoRaise(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip(aide)
            b.clicked.connect(lambda _=False, o=ouvert: self.tout_ouvrir(o))
            tete.addWidget(b)
        v.addLayout(tete)
        grille = QGridLayout()
        grille.setSpacing(6)
        self.modes = QButtonGroup(self)
        self.modes.setExclusive(True)
        for k, (code, texte, aide) in enumerate((
                ("deplacer", "✋  Déplacer", "Déplacer la carte (Échap) ; molette ou double-clic pour zoomer, "
                 "Maj + molette pour un zoom fin"),
                ("carrefour", "◎  Pointer le carrefour", "Cliquer sur le carrefour : centre, anneau, branches et "
                 "angles lus dans la BD TOPO de l'IGN (G)"),
                ("centre", "⊕  Placer le centre", "Cliquer le centre du giratoire (C)"),
                ("axe", "↗  Tracer un axe", "Cliquer sur chaque route, au-delà de l'anneau (A)"))):
            bt = QPushButton(texte)
            bt.setObjectName("outil")
            bt.setCheckable(True)
            bt.setProperty("mode", code)
            bt.setToolTip(aide + "\nDans tous les modes, glisser déplace la carte.")
            bt.setMinimumHeight(34)
            self.modes.addButton(bt)
            grille.addWidget(bt, k // 2, k % 2)
            if code == "deplacer":
                bt.setChecked(True)
        self.modes.buttonClicked.connect(lambda bt: self.choisir_mode(bt.property("mode")))
        v.addLayout(grille)
        self.bt_effacer = QPushButton("✕  Effacer le giratoire")
        self.bt_effacer.setObjectName("effacer")
        self.bt_effacer.setToolTip("Efface le centre et toutes les branches déjà créées ; la géométrie de l'anneau "
                                   "(R, Bf, LA) est conservée")
        self.bt_effacer.clicked.connect(self.effacer_giratoire)
        v.addWidget(self.bt_effacer)
        lay.addWidget(cadre)

        # --- Encarts repliables -----------------------------------------------
        self.encarts: dict[str, Encart] = {}

        def encart(titre: str, cle: str, defaut: bool) -> Encart:
            ouvert = self.reglages.value(f"loc/encart/{cle}", "true" if defaut else "false") in (True, "true")
            e = Encart(titre, cle, ouvert)
            e.bascule.connect(self._encart_bascule)
            self.encarts[cle] = e
            lay.addWidget(e)
            return e

        e = encart("Localisation", "localisation", False)
        f = QFormLayout(e.corps)
        f.setContentsMargins(0, 2, 0, 0)
        self.ed_nom = QLineEdit()
        self.ed_nom.textEdited.connect(self._nom_modifie)
        f.addRow("Nom du giratoire", self.ed_nom)
        self.lbl_commune = self._selectionnable()
        f.addRow("Commune", self.lbl_commune)
        self.lbl_dms = self._selectionnable()
        f.addRow("WGS84 (DMS)", self.lbl_dms)
        self.lbl_dec = self._selectionnable()
        f.addRow("WGS84 (décimal)", self.lbl_dec)
        self.lbl_l93 = self._selectionnable()
        self.lbl_l93_titre = QLabel("RGF93 Lambert-93")
        f.addRow(self.lbl_l93_titre, self.lbl_l93)
        ligne = QHBoxLayout()
        self.cb_cc = QComboBox()
        for z in CC:
            self.cb_cc.addItem(f"CC{z}", z)
        self.cb_cc.activated.connect(self._cc_choisie)
        self.lbl_cc = self._selectionnable()
        ligne.addWidget(self.cb_cc)
        ligne.addWidget(self.lbl_cc, 1)
        f.addRow("RGF93 CC", ligne)
        ligne = QHBoxLayout()
        b = QPushButton("Copier les coordonnées")
        b.clicked.connect(self.copier_coordonnees)
        ligne.addWidget(b)
        b = QPushButton("Centrer la carte")
        b.clicked.connect(self.centrer_giratoire)
        ligne.addWidget(b)
        f.addRow(ligne)

        e = encart("Anneau (saisie au clavier)", "anneau", True)
        g = QGridLayout(e.corps)
        g.setContentsMargins(0, 2, 0, 0)
        self.sp = {}
        for k, (cle, lib, maxi, aide) in enumerate((
                ("R", "R  îlot central", 100.0, "Rayon de l'îlot central infranchissable (0 = mini-giratoire)"),
                ("Bf", "Bf  bande franchissable", 3.0, "Largeur de la bande franchissable"),
                ("LA", "LA  largeur de l'anneau", 18.0, "Largeur de la chaussée annulaire"))):
            sp = QDoubleSpinBox()
            sp.setRange(0.0, maxi)
            sp.setDecimals(2)
            sp.setSingleStep(0.5)
            sp.setSuffix(" m")
            sp.setToolTip(aide)
            sp.valueChanged.connect(lambda v, c=cle: self._anneau_modifie(c, v))
            self.sp[cle] = sp
            g.addWidget(QLabel(lib), k // 2, (k % 2) * 2)
            g.addWidget(sp, k // 2, (k % 2) * 2 + 1)
        g.addWidget(QLabel("Rg  rayon extérieur"), 1, 2)
        self.lbl_rg = self._selectionnable()
        g.addWidget(self.lbl_rg, 1, 3)
        self.lbl_existant = QLabel()
        self.lbl_existant.setWordWrap(True)
        self.lbl_existant.setObjectName("aide")
        g.addWidget(self.lbl_existant, 2, 0, 1, 3)
        self.bt_caler = QPushButton("Reprendre l'existant")
        self.bt_caler.setToolTip("Recale R sur le giratoire existant : Rg = rayon de l'axe de l'anneau BD TOPO + "
                                 "LA/2 ; R = Rg − LA − Bf, arrondi au demi-mètre")
        self.bt_caler.clicked.connect(self.caler_anneau)
        g.addWidget(self.bt_caler, 2, 3, Qt.AlignTop)

        e = encart("Branches (ordre et angles de Girabase)", "branches", True)
        v = QVBoxLayout(e.corps)
        v.setContentsMargins(0, 2, 0, 0)
        self.table = QTableWidget(0, len(COLONNES))
        self.table.setHorizontalHeaderLabels(COLONNES)
        for col, aide in enumerate(AIDES_COLONNES):
            self.table.horizontalHeaderItem(col).setToolTip(aide)
        self.table.verticalHeader().setVisible(False)
        self.table.setTextElideMode(Qt.ElideRight)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed
                                   | QAbstractItemView.AnyKeyPressed)
        self.table.setToolTip("Double-clic pour modifier le nom, la route, l'azimut ou les largeurs. Sur la carte, "
                              "faites glisser les poignées orange pour ajuster les axes (clic droit : menu).\n"
                              "Les angles de Girabase sont comptés dans le sens de giration (inverse des "
                              "aiguilles d'une montre) depuis la branche n° 1.")
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.Stretch)
        hh.setMinimumSectionSize(34)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.itemChanged.connect(self._cellule_modifiee)
        self.table.itemSelectionChanged.connect(self._selection_table)
        v.addWidget(self.table)
        ligne = QHBoxLayout()
        for texte, slot, aide in (
                ("Détecter", self.detecter_branches, "Routes raccordées au centre, lues dans la BD TOPO (Ctrl+B)"),
                ("Branche n° 1", self.definir_branche1, "La branche sélectionnée devient la n° 1 de Girabase"),
                ("Supprimer", self.supprimer_branche, "Supprime la branche sélectionnée (Suppr)"),
                ("Effacer les branches", self.effacer_branches, "Supprime toutes les branches, garde le centre")):
            b = QPushButton(texte)
            b.setToolTip(aide)
            b.clicked.connect(slot)
            ligne.addWidget(b)
        v.addLayout(ligne)

        e = encart("Exports", "exports", True)
        g = QGridLayout(e.corps)
        g.setContentsMargins(0, 2, 0, 0)
        if self.liee:
            self.bt_envoyer = QPushButton("➜  Envoyer dans Girabase")
            self.bt_envoyer.setObjectName("envoyer")
            self.bt_envoyer.setMinimumHeight(32)
            self.bt_envoyer.setToolTip("Reprend le giratoire (branches, angles, anneau, localisation) dans la "
                                       "fenêtre de calcul de Girabase (Ctrl+Entrée)")
            self.bt_envoyer.clicked.connect(self.envoyer_dans_girabase)
            g.addWidget(self.bt_envoyer, 2, 0, 1, 2)
        for k, (texte, slot) in enumerate((("Exporter en KML…", self.exporter_kml),
                                           ("Créer le projet Girabase (.gbs)…", self.creer_gbs),
                                           ("Enregistrer le site…", self.enregistrer),
                                           ("Ouvrir un site…", self.ouvrir_dialogue))):
            b = QPushButton(texte)
            b.clicked.connect(slot)
            g.addWidget(b, k // 2, k % 2)
        lay.addStretch(1)
        return w

    # ================================================================== encarts
    def _encart_bascule(self, cle: str, ouvert: bool) -> None:
        self.reglages.setValue(f"loc/encart/{cle}", ouvert)

    def tout_ouvrir(self, ouvert: bool) -> None:
        for e in self.encarts.values():
            e.ouvrir(ouvert)

    def _maj_resumes(self) -> None:
        """Résumés de deux lignes affichés quand les encarts sont repliés."""
        if not getattr(self, "encarts", None):
            return
        s = self.site
        nom = s.nom or s.nom_propose()
        c = s.commune
        if s.centre_defini:
            leg = s.coordonnees_legales()
            court = ("L93" if leg.epsg == 2154 else leg.nom.split(" / ")[-1]) if leg else ""
            ligne2 = format_dms(s.lat, s.lon) + (f"   {court} X {_fr(leg.x)}  Y {_fr(leg.y)}" if leg else "")
            ligne1 = nom + (f" — {c.nom} ({c.insee})" if c.nom and c.nom not in nom else
                            f" ({c.insee})" if c.insee else "")
        else:
            ligne1, ligne2 = "Aucun emplacement", "Pointez le carrefour sur la carte"
        self.encarts["localisation"].definir_resume(ligne1, ligne2)
        existant = (f"Giratoire existant : Rg ≈ {_fr(s.rayon_axe_bdtopo + s.LA / 2, 1)} m (BD TOPO)"
                    if s.rayon_axe_bdtopo else "")
        self.encarts["anneau"].definir_resume(
            f"R {_fr(s.R)} m · Bf {_fr(s.Bf)} m · LA {_fr(s.LA)} m   →   Rg {_fr(s.Rg)} m"
            + ("  (mini-giratoire)" if s.R == 0 else ""), existant)
        ordre = s.ordre_girabase()
        if ordre:
            self.encarts["branches"].definir_resume(
                f"{len(ordre)} branche{'s' if len(ordre) > 1 else ''} · n° 1 : {ordre[0][0].nom}",
                ", ".join(f"{k + 1}. {b.nom} {a:.0f}°" for k, (b, a) in enumerate(ordre)))
        else:
            self.encarts["branches"].definir_resume("Aucune branche",
                                                    "Pointez le carrefour ou tracez les axes (A)")
        self.encarts["exports"].definir_resume(
            "KML (Google Earth, QGIS) · projet Girabase .gbs · site .gsite",
            f"Site : {self.chemin.name}{' (modifié)' if self.modifie else ''}" if self.chemin
            else "Site non enregistré")

    # ================================================================== réglages
    def _restaurer(self) -> None:
        r = self.reglages
        geo = r.value("loc/geometrie")
        if geo is not None:
            self.restoreGeometry(geo)
        fond = r.value("loc/fond_mode", "auto")
        self.cb_fond.setCurrentIndex(max(0, self.cb_fond.findData(fond)))
        self.sl_opacite.setValue(int(r.value("loc/opacite", 50)))
        self.ck_cadastre.setChecked(r.value("loc/cadastre", "false") in (True, "true"))
        self.ck_routes_ign.setChecked(r.value("loc/routes_ign", "true") in (True, "true"))
        self.carte.voir_france()                 # on choisit l'emplacement en partant de la carte de France
        for cle in ("R", "Bf", "LA"):
            self.sp[cle].setValue(getattr(self.site, cle))

    def _memoriser(self) -> None:
        r = self.reglages
        lat, lon = self.carte.centre_geo()
        r.setValue("loc/lat", lat)
        r.setValue("loc/lon", lon)
        r.setValue("loc/niveau", self.carte.niveau)
        r.setValue("loc/fond_mode", self.cb_fond.currentData())
        r.setValue("loc/routes_ign", self.ck_routes_ign.isChecked())
        r.setValue("loc/opacite", self.sl_opacite.value())
        r.setValue("loc/cadastre", self.ck_cadastre.isChecked())
        r.setValue("loc/geometrie", self.saveGeometry())

    def _dossier(self) -> str:
        return str(self.reglages.value("loc/dossier", str(Path.home())))

    def _retenir_dossier(self, chemin: str) -> None:
        self.reglages.setValue("loc/dossier", str(Path(chemin).parent))

    # ================================================================== affichage
    def statut(self, texte: str, duree: int = 8000) -> None:
        self.statusBar().showMessage(texte, duree)

    def _titre(self) -> None:
        nom = self.chemin.name if self.chemin else "nouveau site"
        self.setWindowTitle(f"{TITRE} — {nom}{' *' if self.modifie else ''}")
        self._maj_resumes()

    def _modif(self) -> None:
        self.modifie = True
        self._titre()

    def _dessiner(self) -> None:
        self.carte.memoriser_centre_site(self.site)
        self.carte.dessiner(self.site, self.troncons if self.ck_routes.isChecked() else None, self.selection,
                            self.ck_schema.isChecked())

    def _tout_rafraichir(self) -> None:
        self._maj_coordonnees()
        self._maj_anneau()
        self._maj_table()
        self._dessiner()
        self._maj_consigne()
        self._maj_resumes()
        self.bt_effacer.setEnabled(self.site.centre_defini or bool(self.site.branches))

    def _maj_consigne(self) -> None:
        """Bandeau d'aide sur la carte, selon l'étape : choisir l'emplacement, pointer, tracer."""
        mode, s = self.carte.mode, self.site
        if mode == "centre":
            texte = "Cliquez le centre du giratoire"
        elif mode == "axe":
            texte = ("Cliquez sur chaque route, au-delà de l'anneau, pour tracer son axe — Échap pour terminer"
                     if s.centre_defini else "Placez d'abord le centre du giratoire")
        elif s.centre_defini:
            texte = ""
        elif self.carte.niveau < SEUIL_PHOTO - 0.25:
            texte = ("Choisissez l'emplacement : rapprochez-vous du carrefour à la molette (ou double-clic)\n"
                     "La photographie aérienne et les routes de l'IGN s'affichent aux grandes échelles")
        elif mode == "carrefour":
            texte = "Cliquez sur le carrefour"
        else:
            texte = ("◎ Pointez le carrefour (bouton « Pointer le carrefour » ou clic droit)\n"
                     "pour obtenir les branches, leurs angles et l'anneau")
        self.carte.set_consigne(texte)

    def _maj_coordonnees(self) -> None:
        s = self.site
        self.ed_nom.setPlaceholderText(s.nom_propose())
        if self.ed_nom.text() != s.nom:
            self.ed_nom.setText(s.nom)
        c = s.commune
        self.lbl_commune.setText(f"{c.nom} ({c.insee})" if c.nom else "—")
        if not s.centre_defini:
            for lbl in (self.lbl_dms, self.lbl_dec, self.lbl_l93, self.lbl_cc):
                lbl.setText("— pointez le carrefour sur la carte —" if lbl is self.lbl_dms else "—")
            self.lbl_l93_titre.setText("RGF93 Lambert-93")
            return
        self.lbl_dms.setText(format_dms(s.lat, s.lon))
        self.lbl_dec.setText(f"{s.lat:.7f}, {s.lon:.7f}")
        leg = s.coordonnees_legales()
        self.lbl_l93_titre.setText(leg.nom if leg else "Système légal")
        self.lbl_l93.setText(f"X = {_fr(leg.x)} m   Y = {_fr(leg.y)} m" if leg else "— hors de France —")
        self.cb_cc.setEnabled(s.metropole)
        if not s.metropole:
            self.lbl_cc.setText("— France métropolitaine uniquement —")
            return
        if self.cc_auto:
            self.cb_cc.setCurrentIndex(self.cb_cc.findData(zone_cc(s.lat)))
        z, xc, yc = s.cc(self.cb_cc.currentData())
        self.lbl_cc.setText(f"X = {_fr(xc)} m   Y = {_fr(yc)} m")

    def _maj_anneau(self) -> None:
        s = self.site
        for cle in ("R", "Bf", "LA"):
            sp = self.sp[cle]
            if abs(sp.value() - getattr(s, cle)) > 1e-9:
                sp.blockSignals(True)
                sp.setValue(getattr(s, cle))
                sp.blockSignals(False)
        self.lbl_rg.setText(f"{_fr(s.Rg)} m" + ("  (mini-giratoire)" if s.R == 0 else ""))
        if s.rayon_axe_bdtopo:
            r = s.rayon_axe_bdtopo
            self.lbl_existant.setText(
                f"Existant (BD TOPO) : axe de l'anneau r ≈ {_fr(r, 1)} m, soit Rg ≈ {_fr(r + s.LA / 2, 1)} m "
                f"pour LA = {_fr(s.LA, 1)} m — à vérifier sur la photo.")
        else:
            self.lbl_existant.setText("Saisissez la géométrie projetée : le dessin suit sur la carte.")
        self.bt_caler.setEnabled(bool(s.rayon_axe_bdtopo))

    def _maj_table(self) -> None:
        self._remplissage = True
        ordre = self.site.ordre_girabase()
        self.table.setRowCount(len(ordre))
        ligne_sel = None
        for k, (b, angle) in enumerate(ordre):
            i = self.site.branches.index(b)
            if i == self.selection:
                ligne_sel = k
            valeurs = [str(k + 1), b.nom, b.numero, b.nom_voie, _fr(b.azimut, 1), b.orientation, _fr(angle, 1),
                       _fr(b.le4), _fr(b.li), _fr(b.ls)]
            for col, val in enumerate(valeurs):
                it = QTableWidgetItem(val)
                it.setData(Qt.UserRole, i)
                if col not in EDITABLES:
                    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                if col in (0, 4, 5, 6, 7, 8, 9):
                    it.setTextAlignment(Qt.AlignCenter)
                if col == 1:
                    it.setToolTip(f"Source : {b.source}")
                elif col == 3 and b.nom_voie:
                    it.setToolTip(b.nom_voie)
                if k == 0 and col == 0:
                    it.setToolTip("Branche n° 1 (angle 0)")
                self.table.setItem(k, col, it)
        if ligne_sel is not None:
            self.table.selectRow(ligne_sel)
        else:
            self.table.clearSelection()
        lignes = max(3, min(NB_BRANCHES_MAX, len(ordre)))
        self.table.setFixedHeight(self.table.horizontalHeader().sizeHint().height()
                                  + self.table.verticalHeader().defaultSectionSize() * lignes
                                  + 2 * self.table.frameWidth() + 2)
        self._remplissage = False

    # ================================================================== fond de carte
    def _changer_fond(self, _i: int) -> None:
        self.carte.set_fond(self.cb_fond.currentData())

    def _changer_opacite(self, v: int) -> None:
        self.lbl_opacite.setText(f"{v} %")
        self.carte.set_opacite(v / 100)

    def _changer_cadastre(self, actif: bool) -> None:
        self.carte.set_cadastre(actif)

    def choisir_mode(self, mode: str) -> None:
        for bt in self.modes.buttons():
            bt.setChecked(bt.property("mode") == mode)
        self.carte.set_mode(mode)
        self.carte.setFocus(Qt.OtherFocusReason)      # les touches G, C, A, Échap restent disponibles
        self.statusBar().clearMessage()
        self._maj_consigne()

    def _curseur(self, lat: float, lon: float) -> None:
        texte = format_dms(lat, lon)
        leg = systeme_legal(lat, lon)
        if leg:
            court = "L93" if leg.epsg == 2154 else leg.nom.split(" / ")[-1]
            texte += f"   {court} X {_fr(leg.x, 1)}  Y {_fr(leg.y, 1)}"
        if self.site.centre_defini:
            e, n = vers_local(self.site.lat, self.site.lon, lat, lon)
            az = azimut(self.site.lat, self.site.lon, lat, lon)
            texte += f"   ·   à {_fr(math.hypot(e, n), 1)} m du centre, azimut {az:.0f}° {A.cardinal8(az)}"
        self.lbl_curseur.setText(texte)

    def centrer_giratoire(self) -> None:
        if self.site.centre_defini:
            self.carte.ajuster(self.site.lat, self.site.lon, self.site.Rg + 75)

    # ================================================================== recherche
    def rechercher(self) -> None:
        texte = self.saisie.text().strip()
        if not texte:
            return
        coord = analyser_saisie(texte)
        if coord:                                # coordonnées du carrefour : analyse directe
            lat, lon, systeme = coord
            self.carte.centrer(lat, lon, 18)
            self.analyser_carrefour(lat, lon)
            return
        self.statut(f"Recherche de « {texte} »…", 0)
        self.client.obtenir_json(url_recherche(texte, 10, *self.carte.centre_geo()), self._resultats)

    def _resultats(self, donnees: Optional[dict], erreur: str) -> None:
        if donnees is None:
            self._erreur_reseau("recherche d'adresse", erreur)
            return
        lat0, lon0 = self.carte.centre_geo()
        lieux = sorted(lire_recherche(donnees), key=lambda l: math.hypot(*vers_local(lat0, lon0, l.lat, l.lon)))
        if not lieux:
            self.statut("Aucun résultat. Essayez « commune, lieu-dit » ou des coordonnées.")
            return
        self.statusBar().clearMessage()
        if len(lieux) == 1:
            self._aller(lieux[0])
            return
        menu = QMenu(self)
        for lieu in lieux:
            a = menu.addAction(lieu.libelle + (f"  ({lieu.commune})" if lieu.commune and lieu.commune not in
                                               lieu.libelle else ""))
            a.triggered.connect(lambda _=False, l=lieu: self._aller(l))
        menu.popup(self.saisie.mapToGlobal(QPoint(0, self.saisie.height())))

    def _aller(self, lieu: Lieu) -> None:
        self.carte.centrer(lieu.lat, lieu.lon, ZOOM_LIEU.get(lieu.type, 17))
        self.statut(f"{lieu.libelle} — pointez le carrefour (G) ou faites un clic droit dessus.")

    # ================================================================== réseau IGN
    def _erreur_reseau(self, quoi: str, erreur: str) -> None:
        self.lbl_reseau.setText("⚠ Services IGN injoignables")
        self.lbl_reseau.setToolTip(erreur)
        self.statut(f"Échec de la {quoi} : {erreur}. Vérifiez la connexion Internet ou le proxy du réseau.", 12000)

    def _reseau_ok(self) -> None:
        self.lbl_reseau.setText("")

    def _chercher_commune(self) -> None:
        if not self.site.centre_defini:
            return
        self._jetons["commune"] += 1
        jeton = self._jetons["commune"]

        def recu(donnees, erreur):
            if jeton != self._jetons["commune"]:
                return
            if donnees is None:
                self._erreur_reseau("recherche de la commune", erreur)
                return
            self._reseau_ok()
            self.site.commune = lire_commune(donnees) or Commune()
            self._maj_coordonnees()
            self._maj_resumes()

        self.client.obtenir_json(url_commune(self.site.lat, self.site.lon), recu)

    def charger_routes(self, lat: float, lon: float, suite=None, forcer: bool = False) -> None:
        """Tronçons BD TOPO autour du point ; « suite » est appelée quand ils sont disponibles."""
        if not forcer and self.troncons_ou is not None:
            e, n = vers_local(lat, lon, *self.troncons_ou)
            if math.hypot(e, n) < 40:
                if suite:
                    suite()
                return
        self._jetons["routes"] += 1
        jeton = self._jetons["routes"]
        if suite:
            self._attente_routes.append(suite)
        self.statut("Chargement des routes de la BD TOPO…", 0)

        def recu(donnees, erreur):
            if jeton != self._jetons["routes"]:
                return
            suites, self._attente_routes = self._attente_routes, []
            if donnees is None:
                self._erreur_reseau("lecture des routes (BD TOPO)", erreur)
                return
            self._reseau_ok()
            self.statusBar().clearMessage()
            self.troncons = lire_routes(donnees)
            self.troncons_ou = (lat, lon)
            self._dessiner()
            for f in suites:
                f()

        self.client.obtenir_json(url_routes(lat, lon, RAYON_ROUTES), recu)

    # ================================================================== centre
    def placer_centre(self, lat: float, lon: float) -> None:
        self.site.lat, self.site.lon = lat, lon
        self._modif()
        self._tout_rafraichir()
        self._chercher_commune()
        self.charger_routes(lat, lon, self._suggerer_existant)
        if self.carte.mode == "centre":
            self.choisir_mode("axe")

    def _suggerer_existant(self) -> None:
        s = self.site
        if not s.centre_defini or s.rayon_axe_bdtopo:
            return
        an = A.detecter_anneau(self.troncons, s.lat, s.lon, 40)
        if an:
            e, n = vers_local(s.lat, s.lon, an.lat, an.lon)
            self.statut(f"Giratoire existant à {_fr(math.hypot(e, n), 1)} m (rayon d'axe {_fr(an.rayon_axe, 1)} m) : "
                        "« Analyser le carrefour » (Ctrl+D) cale le centre, l'anneau et les branches.", 15000)

    def _centre_deplace(self, lat: float, lon: float, fini: bool) -> None:
        self.site.lat, self.site.lon = lat, lon
        if fini:
            self._modif()
            self._tout_rafraichir()
            self._chercher_commune()
            self.charger_routes(lat, lon)
        else:
            self._dessiner()
            self._maj_coordonnees()

    def _cc_choisie(self, _i: int) -> None:
        self.cc_auto = False
        self._maj_coordonnees()

    def copier_coordonnees(self) -> None:
        s = self.site
        if not s.centre_defini:
            return
        lignes = [s.nom or s.nom_propose()]
        if s.commune.nom:
            lignes.append(f"Commune : {s.commune.nom} ({s.commune.insee})")
        lignes += self._lignes_coordonnees(s.lat, s.lon, self.cb_cc.currentData())
        QGuiApplication.clipboard().setText("\n".join(lignes))
        self.statut("Coordonnées copiées dans le presse-papiers.")

    @staticmethod
    def _lignes_coordonnees(lat: float, lon: float, zone: Optional[int] = None) -> list[str]:
        lignes = [f"WGS84 : {format_dms(lat, lon)} — {lat:.7f}, {lon:.7f}"]
        leg = systeme_legal(lat, lon)
        if leg:
            lignes.append(f"{leg.nom} : X = {leg.x:.2f} m ; Y = {leg.y:.2f} m")
        if en_metropole(lat, lon):
            z = zone or zone_cc(lat)
            xc, yc = CC[z].depuis_geo(lat, lon)
            lignes.append(f"RGF93 CC{z} : X = {xc:.2f} m ; Y = {yc:.2f} m")
        return lignes

    def _executer_menu(self, menu: QMenu, pos: QPoint) -> None:
        menu.exec(pos)

    def _menu_carte(self, lat: float, lon: float, pos: QPoint) -> None:
        menu = QMenu(self)
        menu.addAction("◎ Analyser le carrefour ici", lambda: self.analyser_carrefour(lat, lon))
        menu.addAction("Placer le centre ici", lambda: self.placer_centre(lat, lon))
        if self.site.centre_defini:
            menu.addAction("Tracer un axe vers ce point", lambda: self.tracer_axe(lat, lon))
        menu.addSeparator()
        menu.addAction("Copier les coordonnées de ce point", lambda: (
            QGuiApplication.clipboard().setText("\n".join(self._lignes_coordonnees(lat, lon))),
            self.statut("Coordonnées du point copiées.")))
        menu.addAction("Centrer la carte ici", lambda: self.carte.centrer(lat, lon))
        menu.addSeparator()
        menu.addAction("Ouvrir ce point dans Google Maps", lambda: self._ouvrir_web("gmaps", lat, lon))
        menu.addAction("Ouvrir ce point dans Street View", lambda: self._ouvrir_web("streetview", lat, lon))
        menu.addAction("Ouvrir ce point dans le Géoportail", lambda: self._ouvrir_web("geoportail", lat, lon))
        self._executer_menu(menu, pos)

    def _ouvrir_web(self, service: str, lat: Optional[float] = None, lon: Optional[float] = None) -> None:
        s = self.site
        if lat is None:
            lat, lon = (s.lat, s.lon) if s.centre_defini else self.carte.centre_geo()
        urls = {"gmaps": f"https://www.google.com/maps/search/?api=1&query={lat:.7f},{lon:.7f}",
                "streetview": f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lat:.7f},{lon:.7f}",
                "geoportail": (f"https://www.geoportail.gouv.fr/carte?c={lon:.7f},{lat:.7f}&z=19"
                               "&l0=ORTHOIMAGERY.ORTHOPHOTOS::GEOPORTAIL:OGC:WMTS(1)&permalink=yes")}
        QDesktopServices.openUrl(QUrl(urls[service]))

    # ================================================================== détection BD TOPO
    def detecter_giratoire(self) -> None:
        """Analyse autour du centre actuel ou, à défaut, du milieu de la carte."""
        lat, lon = (self.site.lat, self.site.lon) if self.site.centre_defini else self.carte.centre_geo()
        self.analyser_carrefour(lat, lon, confirmer=False)

    def analyser_carrefour(self, lat: float, lon: float, confirmer: bool = True) -> None:
        """Outil « Pointer le carrefour » : centre, anneau, branches et angles lus dans la BD TOPO."""
        if self.carte.niveau < SEUIL_PHOTO - 2.25:
            self.carte.centrer(lat, lon, SEUIL_PHOTO + 1.5)
            self.statut("Carte rapprochée : pointez maintenant le carrefour avec précision.")
            return
        s = self.site
        if confirmer and s.branches:
            proche = s.centre_defini and math.hypot(*vers_local(s.lat, s.lon, lat, lon)) <= 150
            if proche:
                if QMessageBox.question(self, TITRE, "Remplacer le giratoire en cours par l'analyse de ce "
                                        "carrefour ?") != QMessageBox.Yes:
                    return
            elif not self._confirmer_abandon():
                return
        self.statut("Analyse du carrefour (BD TOPO de l'IGN)…", 0)
        self.charger_routes(lat, lon, lambda: self._detecter_giratoire(lat, lon))

    def _detecter_giratoire(self, lat: float, lon: float) -> None:
        """Giratoire existant (anneau BD TOPO) ou carrefour plan (nœud du réseau) le plus proche du point."""
        s, nature = site_depuis_troncons(
            self.troncons, lat, lon, site=SiteCarto(fond=self.cb_fond.currentData(),
                                                    opacite=self.sl_opacite.value() / 100,
                                                    cadastre=self.ck_cadastre.isChecked()))
        nature = {"giratoire": "Giratoire existant", "carrefour": "Carrefour plan", "aucun": ""}[nature]
        self.site = s
        self.chemin, self.selection, self.b1_manuel, self.cc_auto = None, None, False, True
        self.modifie = True
        self._titre()
        self.carte.ajuster(s.lat, s.lon, s.Rg + 75)
        self.choisir_mode("deplacer")
        self._tout_rafraichir()
        self._chercher_commune()
        if nature and s.branches:
            self.statut(f"{nature} : {len(s.branches)} branches — "
                        + ", ".join(f"{b.nom} {a:.0f}°" for b, a in s.ordre_girabase())
                        + f". Anneau : Rg = {_fr(s.Rg)} m, modifiable au clavier.", 20000)
        else:
            self.choisir_mode("axe")
            self.statut("Pas de carrefour dans la BD TOPO à cet endroit : centre placé au point cliqué. "
                        "Tracez les axes des branches en cliquant sur chaque route.", 20000)

    def detecter_branches(self) -> None:
        if not self.site.centre_defini:
            self.statut("Placez d'abord le centre du giratoire.")
            return
        self.charger_routes(self.site.lat, self.site.lon, lambda: self._remplir_branches(demander=True))

    def _remplir_branches(self, demander: bool) -> None:
        s = self.site
        trouvees = A.detecter_branches(self.troncons, s.lat, s.lon, s.rayon_axe_bdtopo)
        if not trouvees:
            self.statut("Aucune route raccordée trouvée dans la BD TOPO : tracez les axes à la main (A).")
            return
        if s.branches and demander:
            rep = QMessageBox.question(
                self, TITRE, f"{len(trouvees)} branches trouvées dans la BD TOPO :\n"
                + "\n".join(f"  • {b.nom} ({b.azimut:.0f}°)" for b in trouvees)
                + "\n\nRemplacer les branches actuelles ?")
            if rep != QMessageBox.Yes:
                return
        s.branches = []
        s.sources = mention_sources(self.troncons)
        for b in trouvees[:NB_BRANCHES_MAX]:
            s.ajouter_branche(b.azimut, b.numero, b.nom_voie, "BD TOPO")
        s.distinguer_noms()
        s.choisir_branche1_nord()
        self.b1_manuel = False
        self.selection = None
        self._modif()
        self._tout_rafraichir()
        self.statut(f"{len(s.branches)} branches détectées : "
                    + ", ".join(b.nom for b, _ in s.ordre_girabase()) + ".")

    def caler_anneau(self) -> None:
        s = self.site
        if not s.rayon_axe_bdtopo:
            return
        rg = s.rayon_axe_bdtopo + s.LA / 2
        s.R = max(0.0, round((rg - s.LA - s.Bf) * 2) / 2)
        self._modif()
        self._tout_rafraichir()
        self.statut(f"R = {_fr(s.R)} m (Rg = {_fr(s.Rg)} m) — à contrôler sur la photographie aérienne.")

    # ================================================================== anneau
    def _anneau_modifie(self, cle: str, v: float) -> None:
        setattr(self.site, cle, v)
        self._modif()
        self._maj_anneau()
        self._dessiner()

    def _nom_modifie(self, texte: str) -> None:
        self.site.nom = texte.strip()
        self._modif()

    # ================================================================== branches
    @staticmethod
    def _nom_auto(b) -> bool:
        return (b.nom == A.nom_branche(b.numero, b.nom_voie, b.azimut)
                or re.fullmatch(r"Branche \d+ (Nord|Est|Sud|Ouest)", b.nom) is not None)

    @staticmethod
    def _nom_calcule(b) -> str:
        if b.numero or b.nom_voie:
            return A.nom_branche(b.numero, b.nom_voie, b.azimut)
        m = re.match(r"(Branche \d+)", b.nom)
        return f"{m.group(1) if m else 'Branche'} {A.cardinal4(b.azimut)}"

    def tracer_axe(self, lat: float, lon: float) -> None:
        s = self.site
        if not s.centre_defini:
            self.statut("Placez d'abord le centre du giratoire (C).")
            return
        e, n = vers_local(s.lat, s.lon, lat, lon)
        if math.hypot(e, n) < 2:
            return
        if len(s.branches) >= NB_BRANCHES_MAX:
            self.statut(f"Girabase traite au plus {NB_BRANCHES_MAX} branches.")
            return
        az = azimut(s.lat, s.lon, lat, lon)
        proche = next((i for i, b in enumerate(s.branches) if abs((b.azimut - az + 180) % 360 - 180) < 4), None)
        if proche is not None:                   # clic sur un axe déjà tracé : simple sélection
            self._selectionner_branche(proche)
            return
        t = A.route_proche(self.troncons, lat, lon, 25) if self.troncons else None
        b = s.ajouter_branche(az, t.numero if t else "", t.nom if t else "", "tracé")
        if t is not None and not s.sources:
            s.sources = mention_sources(self.troncons)
        if not self.b1_manuel:
            s.choisir_branche1_nord()
        self.selection = s.branches.index(b)
        self._modif()
        self._tout_rafraichir()
        self.statut(f"Axe « {b.nom} » : azimut {az:.1f}° ({b.orientation}). Cliquez la route suivante, "
                    "ou Échap pour terminer.", 0)

    def _branche_deplacee(self, i: int, az: float, fini: bool) -> None:
        if not 0 <= i < len(self.site.branches):
            return
        b = self.site.branches[i]
        auto = self._nom_auto(b)
        b.azimut = az % 360
        if auto:
            b.nom = self._nom_calcule(b)
        self.selection = i
        if fini:
            if not self.b1_manuel:
                self.site.choisir_branche1_nord()
            self._modif()
            self._tout_rafraichir()
        else:
            self._dessiner()
            self.statut(f"{b.nom} : azimut {b.azimut:.1f}° ({b.orientation})", 0)

    def _selectionner_branche(self, i: int) -> None:
        self.selection = i
        self._maj_table()
        self._dessiner()

    def _selection_table(self) -> None:
        if self._remplissage:
            return
        lignes = self.table.selectionModel().selectedRows()
        self.selection = self.table.item(lignes[0].row(), 0).data(Qt.UserRole) if lignes else None
        self._dessiner()

    def _menu_branche(self, i: int, pos: QPoint) -> None:
        self._selectionner_branche(i)
        menu = QMenu(self)
        menu.addAction("Définir comme branche n° 1", self.definir_branche1)
        menu.addAction("Renommer…", self.renommer_branche)
        menu.addSeparator()
        menu.addAction("Supprimer la branche", self.supprimer_branche)
        self._executer_menu(menu, pos)

    def renommer_branche(self) -> None:
        if self.selection is None:
            return
        b = self.site.branches[self.selection]
        nom, ok = QInputDialog.getText(self, TITRE, "Nom de la branche :", text=b.nom)
        if ok and nom.strip():
            b.nom = nom.strip()
            self._modif()
            self._tout_rafraichir()

    def definir_branche1(self) -> None:
        if self.selection is None:
            self.statut("Sélectionnez d'abord une branche (tableau ou poignée sur la carte).")
            return
        self.site.branche1 = self.selection
        self.b1_manuel = True
        self._modif()
        self._tout_rafraichir()

    def supprimer_branche(self) -> None:
        if self.selection is None or not 0 <= self.selection < len(self.site.branches):
            return
        self.site.supprimer_branche(self.selection)
        self.selection = None
        self._modif()
        self._tout_rafraichir()

    def effacer_giratoire(self) -> None:
        """Efface le centre et toutes les branches ; la géométrie de l'anneau saisie au clavier est conservée."""
        s = self.site
        if not (s.centre_defini or s.branches):
            return
        quoi = "le centre" + (f" et les {len(s.branches)} branches" if len(s.branches) > 1 else
                              " et la branche" if s.branches else "")
        if QMessageBox.question(self, TITRE, f"Effacer {quoi} du giratoire ?\n\nLa géométrie de l'anneau "
                                f"(R, Bf, LA) est conservée.") != QMessageBox.Yes:
            return
        self.site = SiteCarto(R=s.R, Bf=s.Bf, LA=s.LA, fond=s.fond, opacite=s.opacite, cadastre=s.cadastre)
        self.selection, self.b1_manuel, self.cc_auto = None, False, True
        self._modif()
        self.choisir_mode("carrefour")
        self._tout_rafraichir()
        self.statut("Giratoire effacé : pointez un carrefour, ou placez le centre (C) puis tracez les axes (A).")

    def effacer_branches(self) -> None:
        if self.site.branches and QMessageBox.question(self, TITRE, "Supprimer toutes les branches ?") \
                == QMessageBox.Yes:
            self.site.branches = []
            self.site.branche1 = 0
            self.selection = None
            self.b1_manuel = False
            self._modif()
            self._tout_rafraichir()

    def _cellule_modifiee(self, it: QTableWidgetItem) -> None:
        if self._remplissage:
            return
        i = it.data(Qt.UserRole)
        if i is None or not 0 <= i < len(self.site.branches):
            return
        b = self.site.branches[i]
        col, texte = it.column(), it.text().strip()
        auto = self._nom_auto(b)
        if col == 1 and texte:
            b.nom = texte
        elif col in (2, 3):
            if col == 2:
                b.numero = texte.upper().replace(" ", "")
            else:
                b.nom_voie = texte
            if auto:
                b.nom = self._nom_calcule(b)
        elif col == 4:
            v = _nombre(texte)
            if v is not None:
                b.azimut = v % 360
                if auto:
                    b.nom = self._nom_calcule(b)
        elif col in (7, 8, 9):
            v = _nombre(texte)
            if v is not None and 0 <= v <= 12:
                setattr(b, {7: "le4", 8: "li", 9: "ls"}[col], v)
        self.selection = i
        self._modif()
        QTimer.singleShot(0, self._tout_rafraichir)

    # ================================================================== fichiers et exports
    def _nom_fichier(self, ext: str) -> str:
        base = re.sub(r'[\\/:*?"<>|]+', "-", self.site.nom or self.site.nom_propose()).strip(" -")
        return str(Path(self._dossier()) / f"{base or 'giratoire'}{ext}")

    def _verifier_centre(self) -> bool:
        if not self.site.centre_defini:
            QMessageBox.warning(self, TITRE, "Le centre du giratoire n'est pas défini.")
            return False
        return True

    def exporter_kml(self) -> None:
        if not self._verifier_centre():
            return
        chemin, _ = QFileDialog.getSaveFileName(self, "Exporter en KML", self._nom_fichier(".kml"),
                                                "Google Earth / QGIS (*.kml)")
        if not chemin:
            return
        self._preparer_enregistrement()
        try:
            exporter_kml(self.site, chemin)
        except OSError as exc:
            QMessageBox.critical(self, TITRE, f"Écriture impossible :\n{exc}")
            return
        self._retenir_dossier(chemin)
        self.statut(f"KML exporté : {chemin}")

    def creer_gbs(self) -> None:
        s = self.site
        if not self._verifier_centre():
            return
        if not NB_BRANCHES_MIN <= len(s.branches) <= NB_BRANCHES_MAX:
            QMessageBox.warning(self, TITRE, f"Girabase calcule les giratoires de {NB_BRANCHES_MIN} à "
                                f"{NB_BRANCHES_MAX} branches ({len(s.branches)} définie(s)).")
            return
        self._preparer_enregistrement()
        libelles = [m.libelle for m in Milieu]
        choix, ok = QInputDialog.getItem(self, "Créer le projet Girabase", "Environnement du giratoire :",
                                         libelles, 0, False)
        if not ok:
            return
        chemin, _ = QFileDialog.getSaveFileName(self, "Créer le projet Girabase", self._nom_fichier(".gbs"),
                                                "Projet Girabase (*.gbs)")
        if not chemin:
            return
        g = s.vers_giratoire()
        g.milieu = list(Milieu)[libelles.index(choix)]
        try:
            gbs.ecrire(g, chemin)
        except OSError as exc:
            QMessageBox.critical(self, TITRE, f"Écriture impossible :\n{exc}")
            return
        self._retenir_dossier(chemin)
        self.giratoire_cree.emit(g)
        angles = ", ".join(f"{b.nom} {b.angle}°" for b in g.branches)
        texte = (f"Projet créé : {Path(chemin).name}\n\n{g.n} branches : {angles}\n"
                 f"Anneau : R = {_fr(g.R)} m, Bf = {_fr(g.Bf)} m, LA = {_fr(g.LA)} m\n\n"
                 "Ouvrez-le dans Girabase pour saisir les largeurs d'entrée et les trafics.")
        exe = Path(sys.executable).with_name("Girabase.exe")
        if getattr(sys, "frozen", False) and exe.exists():
            if QMessageBox.question(self, TITRE, texte + "\n\nOuvrir maintenant dans Girabase ?") == QMessageBox.Yes:
                QProcess.startDetached(str(exe), [chemin])
        else:
            QMessageBox.information(self, TITRE, texte)

    # ================================================================== lien avec Girabase
    def envoyer_dans_girabase(self) -> None:
        s = self.site
        if not self._verifier_centre():
            return
        if not NB_BRANCHES_MIN <= len(s.branches) <= NB_BRANCHES_MAX:
            QMessageBox.warning(self, TITRE, f"Girabase calcule les giratoires de {NB_BRANCHES_MIN} à "
                                f"{NB_BRANCHES_MAX} branches ({len(s.branches)} définie(s)).")
            return
        self._preparer_enregistrement()
        if not s.nom:
            s.nom = s.nom_propose()
        import copy
        self.envoi_demande.emit(copy.deepcopy(s))
        self.modifie = False
        self._titre()

    def charger_site(self, site: SiteCarto) -> None:
        """Affiche un site fourni par Girabase (projet ouvert)."""
        import copy
        self.site = copy.deepcopy(site)
        self.chemin = None
        self.selection, self.b1_manuel, self.cc_auto, self.modifie = None, bool(site.branches), True, False
        self.troncons, self.troncons_ou = [], None
        self._tout_rafraichir()
        self._titre()
        if site.centre_defini:
            self.carte.ajuster(site.lat, site.lon, site.Rg + 75)
            self.charger_routes(site.lat, site.lon)

    def repartir_de_zero(self, demander: bool = True, voir_france: bool = True) -> bool:
        if demander and self.modifie and QMessageBox.question(
                self, TITRE, "Abandonner le giratoire en cours sur la carte ?") != QMessageBox.Yes:
            return False
        s = self.site
        self.site = SiteCarto(fond=s.fond, opacite=s.opacite, cadastre=s.cadastre)
        self.chemin, self.selection, self.b1_manuel, self.cc_auto, self.modifie = None, None, False, True, False
        self._tout_rafraichir()
        self._titre()
        if voir_france:
            self.carte.voir_france()
        return True

    def nouveau(self) -> None:
        if not self._confirmer_abandon():
            return
        self.site = SiteCarto(fond=self.site.fond, opacite=self.site.opacite)
        self.chemin, self.selection, self.b1_manuel, self.cc_auto = None, None, False, True
        self.modifie = False
        self._tout_rafraichir()
        self._titre()

    def ouvrir_dialogue(self) -> None:
        if not self._confirmer_abandon():
            return
        chemin, _ = QFileDialog.getOpenFileName(self, "Ouvrir un site", self._dossier(),
                                                f"Site Girabase (*{EXT_SITE});;Tous les fichiers (*)")
        if chemin:
            self.ouvrir(chemin)

    def ouvrir(self, chemin: str) -> None:
        try:
            site = SiteCarto.ouvrir(chemin)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            QMessageBox.critical(self, TITRE, f"Fichier illisible :\n{exc}")
            return
        self.site = site
        self.chemin = Path(chemin)
        self.selection, self.b1_manuel, self.cc_auto, self.modifie = None, True, True, False
        self.troncons, self.troncons_ou = [], None
        self._retenir_dossier(chemin)
        self.cb_fond.setCurrentIndex(max(0, self.cb_fond.findData(site.fond)))
        self.sl_opacite.setValue(int(round(site.opacite * 100)))
        self.ck_cadastre.setChecked(site.cadastre)
        self._tout_rafraichir()
        self._titre()
        if site.centre_defini:
            if site.branches:
                self.carte.ajuster(site.lat, site.lon, site.Rg + 75)
            else:
                self.carte.centrer(site.lat, site.lon, site.zoom)
            self.charger_routes(site.lat, site.lon)

    def _preparer_enregistrement(self) -> None:
        s = self.site
        s.fond = self.cb_fond.currentData()
        s.opacite = self.sl_opacite.value() / 100
        s.cadastre = self.ck_cadastre.isChecked()
        s.zoom = round(self.carte.niveau, 2)
        if s.centre_defini and not s.sources:       # giratoire dessiné à la main : date de consultation figée
            s.sources = mention_fond(s.fond)

    def enregistrer(self) -> bool:
        if self.chemin is None:
            return self.enregistrer_sous()
        self._preparer_enregistrement()
        try:
            self.site.enregistrer(self.chemin)
        except OSError as exc:
            QMessageBox.critical(self, TITRE, f"Écriture impossible :\n{exc}")
            return False
        self.modifie = False
        self._titre()
        self.statut(f"Site enregistré : {self.chemin}")
        return True

    def enregistrer_sous(self) -> bool:
        chemin, _ = QFileDialog.getSaveFileName(self, "Enregistrer le site", self._nom_fichier(EXT_SITE),
                                                f"Site Girabase (*{EXT_SITE})")
        if not chemin:
            return False
        if not chemin.lower().endswith(EXT_SITE):
            chemin += EXT_SITE
        self.chemin = Path(chemin)
        self._retenir_dossier(chemin)
        return self.enregistrer()

    def _confirmer_abandon(self) -> bool:
        if not self.modifie or not self.site.centre_defini:
            return True
        if self.liee:
            rep = QMessageBox.question(self, TITRE, "Le giratoire n'a pas été envoyé dans Girabase. L'envoyer "
                                       "maintenant ?", QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
            if rep == QMessageBox.Yes:
                self.envoyer_dans_girabase()
                return not self.modifie
            return rep == QMessageBox.No
        rep = QMessageBox.question(self, TITRE, "Enregistrer le site avant de continuer ?",
                                   QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        if rep == QMessageBox.Save:
            return self.enregistrer()
        return rep == QMessageBox.Discard

    def sources_et_licences(self) -> None:
        from .sources import dialogue_sources
        dialogue_sources(self)

    def aide(self) -> None:
        QMessageBox.information(self, TITRE, (
            "1. Choisissez l'emplacement : partez de la carte de France et zoomez à la molette (ou double-clic en "
            "mode Déplacer) vers le carrefour, ou tapez une commune, une adresse ou des coordonnées (Google Maps, "
            "Géoportail, Lambert-93, CC ; outre-mer « UTM 40S X Y » ou « EPSG:2975 X Y »).\n"
            "2. Aux grandes échelles, la photographie aérienne de l'IGN remplace le plan, avec la couche "
            "« Routes » (menu Couches). Opacité de la photo réglable (50 % par défaut).\n"
            "3. Outils de la carte (en haut du panneau de droite) : ◎ Pointer le carrefour (G) lit dans la BD TOPO "
            "le centre, "
            "l'anneau existant et les branches avec leur route, leur orientation (Nord, Est, Sud, Ouest) et leurs "
            "angles Girabase ; ⊕ Placer le centre (C) et ↗ Tracer un axe (A) pour dessiner à la main ; "
            "✕ Effacer le giratoire pour recommencer. Dans tous les modes, glisser déplace la carte. Les touches "
            "G, C, A et Échap agissent quand la carte a le focus (cliquez dessus).\n"
            "4. Saisissez l'anneau projeté au clavier (R, Bf, LA) ; ajustez le centre et les axes en faisant "
            "glisser les poignées.\n"
            "5. Exportez en KML (Google Earth, QGIS, Géoportail) et créez le projet Girabase (.gbs).\n\n"
            "Les encarts du panneau se replient d'un clic sur leur titre (▸ / ▾) : repliés, ils affichent un "
            "résumé de deux lignes. « Tout replier » fait tenir tout le panneau à l'écran.\n"
            "Coordonnées : WGS84, RGF93 Lambert-93 et CC42 à CC50 en métropole ; système légal UTM outre-mer.\n"
            "Sources : IGN Géoplateforme (photographies aériennes, Plan IGN, Routes, BD TOPO, Admin Express, "
            "Parcellaire Express — Licence Ouverte Etalab 2.0), © contributeurs OpenStreetMap (ODbL).\n"
            "La conception est schématique : à vérifier sur plan topographique."))

    def _appliquer_theme(self) -> None:
        """Couleurs du panneau adaptées au thème de Windows (clair ou sombre), sans texte illisible."""
        sombre = theme_sombre()
        if sombre != self._sombre:
            self._sombre = sombre
            self.setStyleSheet(feuille_de_style(sombre))

    def _schema_couleurs_change(self, _schema) -> None:
        QTimer.singleShot(0, self._appliquer_theme)      # la palette de l'application est mise à jour juste après

    def changeEvent(self, ev):
        if ev.type() in (QEvent.ApplicationPaletteChange, QEvent.PaletteChange, QEvent.ThemeChange):
            self._appliquer_theme()                  # bascule clair / sombre de Windows en cours de session
        super().changeEvent(ev)

    def closeEvent(self, ev):
        if not self._confirmer_abandon():
            ev.ignore()
            return
        self._memoriser()
        super().closeEvent(ev)
