"""Fenêtre principale de Girabase."""
from __future__ import annotations

import html
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSettings, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout,
                               QInputDialog, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton, QSplitter,
                               QTabWidget, QTextBrowser, QVBoxLayout, QWidget)

from .. import __version__, gbs
from ..calcul import ResultatPeriode, calculer, flux, periode_inversee, periode_multipliee, periode_saturee
from ..conseils import avertissements_domaine, erreurs, recommandations_saisie
from ..carto.gui.theme import couleur_texte
from ..constantes import Milieu, UniteAngle
from ..modele import Giratoire, giratoire_defaut
from .dialogues import TEXTE_A_PROPOS, DialogueImport, DialogueMultiplier
from .onglet_geometrie import OngletGeometrie
from .onglet_resultats import OngletResultats
from .onglet_site import OngletSite
from .onglet_trafics import OngletTrafics
from .rapport import EnteteRapport, exporter_pdf, imprimer
from .schema import VueSchema

FILTRE = "Projets Girabase (*.gbs);;Tous les fichiers (*)"
MAX_RECENTS = 8


class FenetrePrincipale(QMainWindow):
    def __init__(self, chemin: Optional[str] = None):
        super().__init__()
        self.reglages = QSettings("Girabase-Py", "Girabase")
        self.g: Giratoire = giratoire_defaut(4)
        self.g.milieu = None
        self.chemin: Optional[Path] = None
        self.modifie_flag = False
        self.resultats: list[ResultatPeriode] = []
        self.erreurs = []
        self.site_carto = None              # site cartographique associé (fichier .gsite à côté du .gbs)
        self._jeton_projet = 0              # change à chaque nouveau projet ou ouverture
        self._carte_jeton = None            # projet affiché dans la fenêtre de la carte
        self.fen_carte = None               # fenêtre de localisation sur la carte IGN
        self.setAcceptDrops(True)
        self.resize(1440, 900)

        self.onglets = QTabWidget()
        self.site = OngletSite()
        self.geometrie = OngletGeometrie()
        self.trafics = OngletTrafics()
        self.resultats_tab = OngletResultats()
        self.onglets.addTab(self.site, "1. Site")
        self.onglets.addTab(self.geometrie, "2. Géométrie")
        self.onglets.addTab(self.trafics, "3. Trafics")
        self.onglets.addTab(self.resultats_tab, "4. Résultats")

        gauche = QWidget()
        vg = QVBoxLayout(gauche)
        vg.setContentsMargins(0, 0, 0, 0)
        vg.addWidget(self.onglets, 1)
        self.controles = QTextBrowser()
        self.controles.setMaximumHeight(96)
        self.controles.setOpenLinks(False)
        vg.addWidget(QLabel("Contrôles et recommandations"))
        vg.addWidget(self.controles)

        droite = QWidget()
        vd = QVBoxLayout(droite)
        vd.setContentsMargins(0, 0, 0, 0)
        barre = QHBoxLayout()
        self.cb_flux = QCheckBox("Diagramme de flux")
        self.cb_rc = QCheckBox("Réserves de capacité")
        self.cb_rc.setChecked(True)
        bt_ajuster = QPushButton("Ajuster")
        bt_ajuster.setToolTip("Recadrer le schéma (ou double-clic). Molette : zoom.")
        barre.addWidget(QLabel("<b>Schéma de principe</b>"))
        barre.addStretch()
        barre.addWidget(self.cb_flux)
        barre.addWidget(self.cb_rc)
        barre.addWidget(bt_ajuster)
        vd.addLayout(barre)
        self.vue = VueSchema()
        vd.addWidget(self.vue, 1)
        self.legende = QLabel()
        self.legende.setObjectName("aide")
        self.legende.setWordWrap(True)
        vd.addWidget(self.legende)

        split = QSplitter(Qt.Horizontal)
        split.addWidget(gauche)
        split.addWidget(droite)
        split.setSizes([860, 560])
        self.setCentralWidget(split)

        self.minuteur = QTimer(self)
        self.minuteur.setSingleShot(True)
        self.minuteur.setInterval(150)
        self.minuteur.timeout.connect(self.recalculer)

        self._menus()
        self.site.modifie.connect(self._sur_modif)
        self.site.basculer_angles.connect(self._basculer_angles)
        self.site.localiser.connect(self.localiser_sur_carte)
        self.geometrie.modifie.connect(self._sur_modif)
        self.trafics.modifie.connect(self._sur_modif)
        self.trafics.action.connect(self._action_trafic)
        self.trafics.periode_changee.connect(self._periode_trafic)
        self.resultats_tab.saturer.connect(self._saturer)
        self.resultats_tab.supprimer_saturee.connect(self._supprimer_saturee)
        self.resultats_tab.periode_changee.connect(lambda _: self._maj_schema())
        self.cb_flux.toggled.connect(lambda _: self._maj_schema())
        self.cb_rc.toggled.connect(lambda _: self._maj_schema())
        bt_ajuster.clicked.connect(self.vue.ajuster)

        if chemin:
            self.ouvrir(chemin)
        else:
            self._charger_tout()
        self.statusBar().showMessage("Prêt. Ouvrez un projet .gbs existant ou décrivez un nouveau giratoire.", 6000)

    # ------------------------------------------------------------------ menus
    def _menus(self) -> None:
        mb = self.menuBar()
        m = mb.addMenu("&Fichier")
        self._act(m, "&Nouveau giratoire", self.nouveau, QKeySequence.New)
        self._act(m, "Nouveau giratoire depuis la &carte IGN…", self.nouveau_depuis_carte, "Ctrl+Shift+N")
        self._act(m, "&Ouvrir…", self.ouvrir_dialogue, QKeySequence.Open)
        self.menu_recents = m.addMenu("Projets &récents")
        self._maj_recents()
        m.addSeparator()
        self._act(m, "&Enregistrer", self.enregistrer, QKeySequence.Save)
        self._act(m, "Enregistrer &sous…", self.enregistrer_sous, QKeySequence.SaveAs)
        m.addSeparator()
        self._act(m, "Exporter la note de calcul (&PDF)…", self.exporter_pdf, "Ctrl+E")
        self._act(m, "&Imprimer la note de calcul…", self.imprimer, QKeySequence.Print)
        self._act(m, "Exporter le schéma pour AutoCAD (&DXF)…", self.exporter_dxf, "Ctrl+D")
        self._act(m, "Paramètres de la note de calcul…", self.parametres_rapport)
        m.addSeparator()
        self._act(m, "&Quitter", self.close, QKeySequence.Quit)

        t = mb.addMenu("&Trafics")
        for code, lib in (("nouvelle", "Nouvelle période"), ("dupliquer", "Dupliquer la période"),
                          ("renommer", "Renommer la période"), ("supprimer", "Supprimer la période"), (None, None),
                          ("inverser", "Inverser les trafics"), ("multiplier", "Multiplier les trafics…"),
                          ("importer", "Importer les trafics d'un autre projet…"),
                          ("completer", "Remplacer les cases vides par 0")):
            if code is None:
                t.addSeparator()
            else:
                self._act(t, lib, lambda c=code: self._action_trafic(c))

        o = mb.addMenu("&Outils")
        self._act(o, "Localiser sur la carte IGN…", self.localiser_sur_carte, "Ctrl+L")
        o.addSeparator()
        self._act(o, "Recalculer", self.recalculer, "F5")
        self._act(o, "Convertir les angles (degrés ↔ grades)", self._basculer_angles)
        self._act(o, "Copier le tableau des résultats", self.resultats_tab.copier)

        a = mb.addMenu("&Aide")
        self._act(a, "Guide d'utilisation", self.guide, QKeySequence.HelpContents)
        self._act(a, "Méthode de calcul et lecture des résultats", self.aide_methode)
        self._act(a, "Sources des données cartographiques et licences", self.sources_et_licences)
        self._act(a, "Code source d'origine (CEREMA)",
                  lambda: QDesktopServices.openUrl(QUrl("https://github.com/CEREMA/territoires-ville.Girabase")))
        self._act(a, "À propos", self.a_propos)

    def _act(self, menu, texte, slot, raccourci=None) -> QAction:
        act = QAction(texte, self)
        if raccourci is not None:
            act.setShortcut(QKeySequence(raccourci))
        act.triggered.connect(slot)
        menu.addAction(act)
        return act

    def _maj_recents(self) -> None:
        self.menu_recents.clear()
        recents = [r for r in (self.reglages.value("recents", []) or []) if r and Path(r).exists()]
        for r in recents[:MAX_RECENTS]:
            self.menu_recents.addAction(Path(r).name, lambda c=r: self.ouvrir(c)).setToolTip(r)
        self.menu_recents.setEnabled(bool(recents))

    def _ajouter_recent(self, chemin: Path) -> None:
        recents = [r for r in (self.reglages.value("recents", []) or []) if r != str(chemin)]
        self.reglages.setValue("recents", [str(chemin)] + recents[:MAX_RECENTS - 1])
        self._maj_recents()

    # ------------------------------------------------------------------ état
    def _titre(self) -> None:
        nom = self.chemin.name if self.chemin else "Nouveau giratoire"
        self.setWindowTitle(f"{nom}{' *' if self.modifie_flag else ''} — Girabase {__version__}")

    def _charger_tout(self) -> None:
        self.site.charger(self.g)
        self.geometrie.charger(self.g)
        self.trafics.charger(self.g, 0)
        self.recalculer()
        self._titre()

    def _sur_modif(self, structure: bool = False) -> None:
        self.modifie_flag = True
        self._titre()
        # supprime les périodes saturées obsolètes
        self.g.periodes = [p for p in self.g.periodes if p.branche_saturee is None]
        if structure:
            emetteur = self.sender()
            if emetteur is not self.site:
                self.site.charger(self.g)
            if emetteur is not self.geometrie:
                self.geometrie.charger(self.g)
            self.trafics.charger(self.g)
        self.minuteur.start()

    def recalculer(self) -> None:
        g = self.g
        self.erreurs = erreurs(g)
        self.resultats = []
        if not self.erreurs:
            try:
                self.resultats = calculer(g)
            except (ValueError, ZeroDivisionError, OverflowError) as exc:
                from ..conseils import Remarque
                self.erreurs = [Remarque(f"Calcul impossible : {exc}")]
        self.resultats_tab.charger(g, self.resultats, self.erreurs)
        self._maj_controles()
        self._maj_schema()
        self._maj_statut()

    def _maj_controles(self) -> None:
        g = self.g
        lignes = []
        for e in self.erreurs:
            lignes.append(f'<p style="color:{couleur_texte("erreur")};margin:1px">⛔ {html.escape(e.texte)}</p>')
        recs = recommandations_saisie(g, None)
        for pr in g.periodes_reelles():
            recs += avertissements_domaine(g, pr)
        for r in recs:
            lignes.append(f'<p style="color:{couleur_texte("alerte")};margin:1px">⚠ {html.escape(r.texte)}</p>')
        if not lignes:
            lignes.append(f'<p style="color:{couleur_texte("ok")};margin:1px">✔ Données valides, aucune '
                          'recommandation.</p>')
        self.controles.setHtml("".join(lignes))
        idx = self.onglets.indexOf(self.resultats_tab)
        self.onglets.setTabText(idx, "4. Résultats" + (" ⛔" if self.erreurs else ""))

    def _maj_schema(self) -> None:
        res = self.resultats_tab.resultat_courant()
        fl = None
        if self.cb_flux.isChecked():
            p = res.periode if res is not None else self.trafics.periode()
            if p is not None:
                fl = flux(self.g, p)
        self.vue.afficher(self.g, res if (self.cb_rc.isChecked() and res is not None) else None, fl)
        txt = f"Rg = {self.g.Rg:.2f} m".replace(".", ",")
        if res is not None:
            txt += f" — période « {res.periode.nom} »"
        txt += ". Couleurs de réserve : lie-de-vin < 0 %, orange < 15 %, vert 15–80 %, bleu > 80 %."
        self.legende.setText(txt)

    def _maj_statut(self) -> None:
        if self.erreurs:
            self.statusBar().showMessage(f"{len(self.erreurs)} donnée(s) à corriger avant le calcul.")
            return
        pires = []
        for res in self.resultats:
            if not res.complete:
                continue
            ent = [b for b in res.branches if not b.entree_nulle and b.RC_pct is not None]
            if ent:
                b = min(ent, key=lambda x: x.RC_pct)
                pires.append(f"{res.periode.nom} : RC mini {b.RC_pct:.0f} % ({b.nom})")
        self.statusBar().showMessage("   |   ".join(pires) if pires else "Saisissez les trafics pour obtenir les résultats.")

    # ------------------------------------------------------------------ fichiers
    def _confirmer_abandon(self) -> bool:
        if not self.modifie_flag:
            return True
        r = QMessageBox.question(getattr(self, "_parent_questions", None) or self, "Projet modifié",
                                 "Enregistrer les modifications du projet en cours ?",
                                 QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        if r == QMessageBox.Save:
            return self.enregistrer()
        return r == QMessageBox.Discard

    def nouveau(self) -> None:
        if not self._confirmer_abandon():
            return
        self.g = giratoire_defaut(4)
        self.g.milieu = None
        self.chemin = None
        self.site_carto = None
        self._jeton_projet += 1
        self.modifie_flag = False
        self.onglets.setCurrentIndex(0)
        self._charger_tout()

    def ouvrir_dialogue(self) -> None:
        if not self._confirmer_abandon():
            return
        rep = self.reglages.value("dossier", str(Path.home()))
        chemin, _ = QFileDialog.getOpenFileName(self, "Ouvrir un projet Girabase", rep, FILTRE)
        if chemin:
            self.ouvrir(chemin)

    def ouvrir(self, chemin: str) -> None:
        try:
            g = gbs.lire(chemin)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Ouverture impossible", f"Le fichier n'a pas pu être lu :\n{exc}")
            return
        self.g = g
        self.chemin = Path(chemin)
        self.site_carto = self._lire_site_associe(self.chemin)
        self._jeton_projet += 1
        self.modifie_flag = False
        self.reglages.setValue("dossier", str(self.chemin.parent))
        self._ajouter_recent(self.chemin)
        self._charger_tout()
        self.onglets.setCurrentWidget(self.resultats_tab if not self.erreurs else self.geometrie)

    def enregistrer(self) -> bool:
        if self.chemin is None:
            return self.enregistrer_sous()
        try:
            gbs.ecrire(self.g, self.chemin)
            if self.site_carto is not None:          # localisation sur la carte, à côté du projet
                self.site_carto.nom = self.g.nom
                self.site_carto.enregistrer(self.chemin.with_suffix(".gsite"))
        except OSError as exc:
            QMessageBox.warning(self, "Enregistrement impossible", str(exc))
            return False
        self.modifie_flag = False
        self.site.charger(self.g)
        self._titre()
        self.statusBar().showMessage(f"Enregistré : {self.chemin}", 5000)
        return True

    def enregistrer_sous(self) -> bool:
        rep = self.reglages.value("dossier", str(Path.home()))
        nom = (self.g.nom or "giratoire").replace("/", "-")
        chemin, _ = QFileDialog.getSaveFileName(self, "Enregistrer le projet", str(Path(rep) / f"{nom}.gbs"), FILTRE)
        if not chemin:
            return False
        if not chemin.lower().endswith(".gbs"):
            chemin += ".gbs"
        self.chemin = Path(chemin)
        self.reglages.setValue("dossier", str(self.chemin.parent))
        ok = self.enregistrer()
        if ok:
            self._ajouter_recent(self.chemin)
        return ok

    def _base_export(self, ext: str) -> str:
        rep = self.reglages.value("dossier", str(Path.home()))
        base = self.chemin.stem if self.chemin else (self.g.nom or "giratoire")
        return str(Path(rep) / f"{base}{ext}")

    def _verifier_calcul(self) -> bool:
        self.recalculer()
        if self.erreurs:
            QMessageBox.warning(self, "Données à corriger",
                                "Le calcul n'est pas possible tant que des données sont invalides :\n\n"
                                + "\n".join("• " + e.texte for e in self.erreurs[:8]))
            return False
        return True

    def entete(self) -> EnteteRapport:
        e = EnteteRapport()
        for cle in ("organisme", "service", "auteur", "pied"):
            v = self.reglages.value(f"rapport/{cle}")
            if v is not None:
                setattr(e, cle, v)
        return e

    def exporter_pdf(self) -> None:
        if not self._verifier_calcul():
            return
        chemin, _ = QFileDialog.getSaveFileName(self, "Exporter la note de calcul", self._base_export(".pdf"),
                                                "PDF (*.pdf)")
        if not chemin:
            return
        if not chemin.lower().endswith(".pdf"):
            chemin += ".pdf"
        nb = exporter_pdf(self.g, self.resultats, chemin, self.entete())
        self.statusBar().showMessage(f"Note de calcul exportée ({nb} pages) : {chemin}", 8000)
        QDesktopServices.openUrl(QUrl.fromLocalFile(chemin))

    def imprimer(self) -> None:
        if not self._verifier_calcul():
            return
        from PySide6.QtPrintSupport import QPrintDialog, QPrinter
        printer = QPrinter(QPrinter.HighResolution)
        dlg = QPrintDialog(printer, self)
        if dlg.exec() == QDialog.Accepted:
            imprimer(self.g, self.resultats, printer, self.entete())

    def exporter_dxf(self) -> None:
        if self.g.n < 3:
            return
        from ..dxf_export import exporter_dxf
        chemin, _ = QFileDialog.getSaveFileName(self, "Exporter le schéma DXF", self._base_export(".dxf"),
                                                "DXF AutoCAD (*.dxf)")
        if not chemin:
            return
        if not chemin.lower().endswith(".dxf"):
            chemin += ".dxf"
        fl = None
        if self.cb_flux.isChecked():
            res = self.resultats_tab.resultat_courant()
            p = res.periode if res is not None else self.trafics.periode()
            fl = flux(self.g, p) if p is not None else None
        try:
            exporter_dxf(self.g, chemin, fl)
        except OSError as exc:
            QMessageBox.warning(self, "Export impossible", str(exc))
            return
        self.statusBar().showMessage(f"Schéma DXF exporté (1 unité = 1 m, centre en 0,0, branche 1 sur l'axe X) : "
                                     f"{chemin}", 10000)

    def parametres_rapport(self) -> None:
        e = self.entete()
        dlg = QDialog(self)
        dlg.setWindowTitle("Paramètres de la note de calcul")
        f = QFormLayout(dlg)
        champs = {}
        for cle, lib in (("organisme", "Organisme"), ("service", "Service"), ("auteur", "Établi par"),
                         ("pied", "Pied de page")):
            le = QLineEdit(getattr(e, cle))
            le.setMinimumWidth(360)
            f.addRow(lib, le)
            champs[cle] = le
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        f.addRow(bb)
        if dlg.exec() == QDialog.Accepted:
            for cle, le in champs.items():
                self.reglages.setValue(f"rapport/{cle}", le.text())

    # ------------------------------------------------------------------ trafics
    def _periode_trafic(self, _index: int) -> None:
        p = self.trafics.periode()
        if p is not None:
            self.resultats_tab.selectionner_periode(p.nom)

    def _nom_periode(self, titre: str, defaut: str) -> Optional[str]:
        nom, ok = QInputDialog.getText(self, titre, "Nom de la période :", text=defaut)
        nom = nom.strip()
        if not ok or not nom:
            return None
        if any(p.nom == nom for p in self.g.periodes):
            QMessageBox.warning(self, titre, "Nom de période déjà utilisé.")
            return None
        return nom

    def _ajouter_periode(self, p) -> None:
        reelles = self.g.periodes_reelles()
        self.g.periodes = reelles + [p]
        self.trafics.charger(self.g, len(reelles))
        self._sur_modif(False)
        self.resultats_tab.selectionner_periode(p.nom)

    def _action_trafic(self, code: str) -> None:
        g = self.g
        src = self.trafics.periode()
        if code == "nouvelle":
            nom = self._nom_periode("Nouvelle période", g.nom_periode_libre())
            if nom:
                p = g.nouvelle_periode(nom)
                g.periodes.remove(p)
                self._ajouter_periode(p)
                self.onglets.setCurrentWidget(self.trafics)
            return
        if src is None:
            QMessageBox.information(self, "Trafics", "Créez d'abord une période de trafic.")
            return
        if code == "dupliquer":
            nom = self._nom_periode("Dupliquer la période", f"Copie de {src.nom}")
            if nom:
                self._ajouter_periode(src.copie(nom))
        elif code == "renommer":
            nom = self._nom_periode("Renommer la période", src.nom)
            if nom:
                src.nom = nom
                self.trafics.charger(g)
                self._sur_modif(False)
        elif code == "supprimer":
            if QMessageBox.question(self, "Supprimer", f"Supprimer la période « {src.nom} » ?") == QMessageBox.Yes:
                g.periodes.remove(src)
                self.trafics.charger(g)
                self._sur_modif(False)
        elif code in ("inverser", "multiplier"):
            if not src.est_complete(g.branches):
                QMessageBox.warning(self, "Période incomplète", "Période de trafic incomplète : renseignez toutes "
                                                               "les cases avant cette opération.")
                return
            if code == "inverser":
                nom = self._nom_periode("Inverser les trafics", f"Inversion de {src.nom}")
                if nom:
                    self._ajouter_periode(periode_inversee(g, src, nom))
            else:
                dlg = DialogueMultiplier(g, src, self)
                if dlg.exec() == QDialog.Accepted:
                    params = dlg.parametres()
                    nom = params.pop("nom") or f"Multiplication de {src.nom}"
                    if any(p.nom == nom for p in g.periodes):
                        QMessageBox.warning(self, "Multiplier", "Nom de période déjà utilisé.")
                        return
                    self._ajouter_periode(periode_multipliee(g, src, nom=nom, **params))
        elif code == "importer":
            self._importer()
        elif code == "completer":
            src.completer_par_zero(g.branches)
            self.trafics.charger(g)
            self._sur_modif(False)

    def _importer(self) -> None:
        g = self.g
        rep = self.reglages.value("dossier", str(Path.home()))
        chemin, _ = QFileDialog.getOpenFileName(self, "Projet contenant les trafics à importer", rep, FILTRE)
        if not chemin:
            return
        try:
            autre = gbs.lire(chemin)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Import impossible", str(exc))
            return
        if not autre.periodes_reelles():
            QMessageBox.warning(self, "Import impossible", "Pas de période de trafic dans le projet lu.")
            return
        if autre.n != g.n:
            QMessageBox.warning(self, "Import impossible",
                                "Nombre de branches du projet importé différent du giratoire courant.")
            return
        for a, b in zip(autre.branches, g.branches):
            if a.entree_nulle != b.entree_nulle or a.sortie_nulle != b.sortie_nulle:
                QMessageBox.warning(self, "Import impossible",
                                    "Incompatibilité entre les deux projets (branche unidirectionnelle).")
                return
        dlg = DialogueImport(autre, self)
        if dlg.exec() != QDialog.Accepted:
            return
        for i in dlg.choix():
            p = autre.periodes_reelles()[i]
            nom = p.nom
            while any(q.nom == nom for q in g.periodes):
                nom += " (import)"
            self._ajouter_periode(p.copie(nom))

    def _saturer(self, index: int, k: int) -> None:
        g = self.g
        res = self.resultats[index]
        src = res.periode
        nom = f"{src.nom} SBr{g.branches[k].nom}"
        existante = next((p for p in g.periodes if p.nom == nom), None)
        if existante is None:
            try:
                existante = periode_saturee(g, src, k)
            except ValueError as exc:
                QMessageBox.warning(self, "Saturer la branche", str(exc))
                return
            g.periodes.append(existante)
        self.recalculer()
        self.resultats_tab.selectionner_periode(nom)

    def _supprimer_saturee(self, index: int) -> None:
        p = self.resultats[index].periode
        if p in self.g.periodes:
            self.g.periodes.remove(p)
        self.recalculer()

    def _basculer_angles(self) -> None:
        self.g.changer_unite_angle()
        self._sur_modif(True)
        self.site.charger(self.g)
        self.geometrie.charger(self.g)

    # ------------------------------------------------------------------ aide
    def aide_methode(self) -> None:
        from .aide import TEXTE_METHODE
        dlg = QDialog(self)
        dlg.setWindowTitle("Méthode de calcul et lecture des résultats")
        dlg.resize(760, 640)
        v = QVBoxLayout(dlg)
        tb = QTextBrowser()
        tb.setOpenExternalLinks(True)
        tb.setHtml(TEXTE_METHODE)
        v.addWidget(tb)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(dlg.reject)
        v.addWidget(bb)
        dlg.exec()

    def guide(self) -> None:
        from .guide import afficher_guide
        afficher_guide(self)

    def sources_et_licences(self) -> None:
        from ..carto.gui.sources import dialogue_sources
        dialogue_sources(self)

    # ------------------------------------------------------------------ localisation sur la carte IGN
    @staticmethod
    def _lire_site_associe(chemin: Path):
        from ..carto.site import SiteCarto
        gsite = chemin.with_suffix(".gsite")
        if gsite.exists():
            try:
                return SiteCarto.ouvrir(gsite)
            except (OSError, ValueError, TypeError, KeyError):
                return None
        return None

    def _site_pour_carte(self):
        """Site à afficher : celui du projet, sinon les coordonnées écrites dans la localisation."""
        from ..carto.site import site_depuis_texte
        if self.site_carto is not None:
            return self.site_carto
        site = site_depuis_texte(self.g.localisation)
        if site is not None:
            site.R, site.Bf, site.LA, site.nom = self.g.R, self.g.Bf, self.g.LA, self.g.nom
        return site

    def _fenetre_carte(self):
        from ..carto.gui.fenetre import FenetreLocalisation
        if self.fen_carte is None:
            self.fen_carte = FenetreLocalisation(liee=True)
            self.fen_carte.envoi_demande.connect(self._recevoir_site)
        return self.fen_carte

    def localiser_sur_carte(self) -> None:
        fen = self._fenetre_carte()
        if self._carte_jeton != self._jeton_projet and self._carte_a_jour(fen):
            self._carte_jeton = self._jeton_projet
        fen.show()
        fen.raise_()
        fen.activateWindow()

    def _carte_a_jour(self, fen) -> bool:
        """Affiche sur la carte le site du projet ouvert (ou une carte vierge s'il n'en a pas).

        Un giratoire dessiné sur la carte et pas encore envoyé n'est abandonné qu'avec l'accord de l'utilisateur.
        """
        if fen.modifie and fen.site.centre_defini and QMessageBox.question(
                self, "Localiser sur la carte IGN",
                "Le giratoire dessiné sur la carte n'a pas été envoyé dans Girabase.\n"
                f"L'abandonner pour afficher le projet « {self.g.nom} » ?") != QMessageBox.Yes:
            return False
        site = self._site_pour_carte()
        if site is not None:
            fen.charger_site(site)
        elif fen.site.centre_defini or fen.site.branches:
            fen.repartir_de_zero(demander=False, voir_france=False)
        return True

    def nouveau_depuis_carte(self) -> None:
        fen = self._fenetre_carte()
        if fen.site.centre_defini and not fen.repartir_de_zero():
            return
        self._carte_jeton = self._jeton_projet       # carte vierge volontaire : ne pas la recharger
        fen.show()
        fen.raise_()
        fen.activateWindow()

    def _recevoir_site(self, site) -> None:
        """Giratoire conçu sur la carte : nouveau projet, ou mise à jour de la géométrie du projet ouvert."""
        # Les questions s'affichent devant la carte, d'où vient la demande
        self._parent_questions = self.fen_carte if self.fen_carte is not None and self.fen_carte.isVisible() \
            else self
        try:
            self._recevoir_site_suite(site)
        finally:
            self._parent_questions = self

    def _recevoir_site_suite(self, site) -> None:
        n = len(site.branches)
        projet_en_cours = self.chemin is not None or self.modifie_flag or any(p.total() for p in self.g.periodes)
        mode = self._demander_mode(n) if projet_en_cours else "nouveau"
        if mode is None:
            return
        mettre_a_jour = mode == "maj"
        if not mettre_a_jour and projet_en_cours and not self._confirmer_abandon():
            return
        if mettre_a_jour:
            self._maj_geometrie_depuis_site(site)
        else:
            milieu = self._choisir_milieu()
            if milieu is None:
                return
            g = site.vers_giratoire()
            g.milieu = milieu
            self.g, self.chemin = g, None
            self.site_carto = site
            self._jeton_projet += 1
            self._carte_jeton = self._jeton_projet     # la carte montre déjà ce giratoire
            self.modifie_flag = True
            self._charger_tout()
            self.onglets.setCurrentWidget(self.trafics)
        self.statusBar().showMessage("Giratoire repris de la carte : " + ", ".join(
            f"{b.nom} {b.angle}" for b in self.g.branches) + f" ({self.g.unite_angle.libelle}).", 10000)
        self.raise_()
        self.activateWindow()

    def _demander_mode(self, n: int):
        """« maj » (géométrie du projet ouvert, trafics conservés), « nouveau » ou None (annulé)."""
        boite = QMessageBox(getattr(self, "_parent_questions", self))
        boite.setWindowTitle("Giratoire conçu sur la carte")
        boite.setText(f"Le giratoire comporte {n} branches.")
        boite.setInformativeText(
            "Mettre à jour la géométrie du projet ouvert (noms, angles, anneau, localisation ; les trafics et les "
            "largeurs sont conservés), ou créer un nouveau projet ?" if n == self.g.n else
            f"Le projet ouvert compte {self.g.n} branches : un nouveau projet va être créé.")
        bt_maj = boite.addButton("Mettre à jour le projet ouvert", QMessageBox.AcceptRole) if n == self.g.n else None
        bt_nouveau = boite.addButton("Nouveau projet", QMessageBox.AcceptRole)
        boite.addButton(QMessageBox.Cancel)
        boite.exec()
        if bt_maj is not None and boite.clickedButton() is bt_maj:
            return "maj"
        return "nouveau" if boite.clickedButton() is bt_nouveau else None

    def _maj_geometrie_depuis_site(self, site) -> None:
        g = self.g
        nouveau = site.vers_giratoire()
        for b, nb in zip(g.branches, nouveau.branches):
            b.nom = nb.nom
            b.angle = nb.angle if g.unite_angle is UniteAngle.DEGRE else int(round(nb.angle * 400 / 360)) % 400
        g.R, g.Bf, g.LA = site.R, site.Bf, site.LA
        g.localisation = nouveau.localisation
        if not g.nom.strip() or g.nom == "Nouveau giratoire":
            g.nom = nouveau.nom
        self.site_carto = site
        self.modifie_flag = True
        self.site.charger(g)
        self.geometrie.charger(g)
        self.trafics.charger(g)
        self.recalculer()
        self._titre()

    def _choisir_milieu(self):
        libelles = [m.libelle for m in Milieu]
        actuel = libelles.index(self.g.milieu.libelle) if self.g.milieu is not None else 0
        choix, ok = QInputDialog.getItem(getattr(self, "_parent_questions", self), "Nouveau projet depuis la carte",
                                         "Environnement du giratoire :", libelles, actuel, False)
        return list(Milieu)[libelles.index(choix)] if ok else None

    def a_propos(self) -> None:
        QMessageBox.about(self, "À propos de Girabase", TEXTE_A_PROPOS + f"<p>Version {__version__}</p>")

    # ------------------------------------------------------------------ événements
    def closeEvent(self, ev):
        if not self._confirmer_abandon():
            ev.ignore()
            return
        if self.fen_carte is not None and self.fen_carte.isVisible():
            self.fen_carte.close()
            if self.fen_carte.isVisible():           # fermeture refusée dans la fenêtre de la carte
                ev.ignore()
                return
        ev.accept()

    def dragEnterEvent(self, ev):
        if ev.mimeData().hasUrls():
            ev.acceptProposedAction()

    def dropEvent(self, ev):
        urls = ev.mimeData().urls()
        if urls and self._confirmer_abandon():
            self.ouvrir(urls[0].toLocalFile())
