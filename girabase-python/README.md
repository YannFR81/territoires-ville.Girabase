# Girabase — portage Python (version 1.2)

*L’intelligence artificielle au service de l’action publique efficiente.*

Calcul de capacité des carrefours giratoires : réserve de capacité, temps d'attente, longueurs de file,
conseils de conception et de fonctionnement, courbes de capacité, diagramme de flux, note de calcul PDF et
export du schéma vers AutoCAD / COVADIS. **Nouveau en 1.2 :** localisation du giratoire sur la carte de l'IGN,
partout en France, et serveur MCP pour les assistants d'IA.

Ce programme reprend **à l'identique** le moteur du logiciel **GIRABASE 4** (CERTU / CETE de l'Ouest),
dont le CEREMA a publié le code source Visual Basic 6 sous licence GNU GPL v3 :
<https://github.com/CEREMA/territoires-ville.Girabase>. Le logiciel d'origine n'est plus vendu ni maintenu
depuis 2021 et ne fonctionne plus sans manipulation (protection, contrôles ActiveX propriétaires). Les 24
résultats du cas de référence du guide Girabase 4 sont reproduits à l'identique.

**Documentation :** [guide d'utilisation](docs/guide-utilisateur.md) (aussi dans le logiciel, touche F1) ·
[sources des données et licences](docs/sources-et-licences.md) · [nouveautés](NOUVEAUTES.md).

**Téléchargements** : [dernière version publiée](https://github.com/YannFR81/territoires-ville.Girabase/releases/latest)
(onglet *Releases* du dépôt).

| Fichier | Rôle |
|---|---|
| `Girabase.exe` | logiciel complet, fichier unique, Windows 10/11 64 bits, sans installation |
| `Girabase-Windows.zip` | même logiciel en version dossier (démarrage plus rapide, à préférer si l'antivirus bloque le fichier unique) |
| `girabase-mcp.exe` | serveur MCP pour les assistants d'IA (Claude Desktop, LM Studio, Jan…) |
| `girabase.mcpb` | extension Claude Desktop prête à installer (double-clic) |
| `Guide-utilisateur-Girabase.pdf` | guide d'utilisation imprimable |

## Ce que fait le programme

| Fonction | Détail |
|---|---|
| Saisie | site et environnement (rase campagne, périurbain, centre-ville), anneau, 3 à 8 branches (rampe > 3 %, tourne-à-droite direct, entrée évasée, îlot, sortie), angles en degrés ou grades |
| Trafics | périodes multiples, matrices O/D en uvp/h ou par catégorie VL / PL / 2R, piétons, **copier-coller depuis Excel**, inversion HPM ↔ HPS, multiplication (globale, par entrée, par sortie), import depuis un autre projet |
| Résultats | trafic entrant, trafic gênant, capacité, réserve en uvp/h et en %, files moyenne et maximale, attente moyenne et totale, « saturer la branche » |
| Conseils | tous les contrôles, recommandations et conseils de Girabase 4 (conception, trafics, fonctionnement) |
| Schéma | schéma de principe à l'échelle, diagramme de flux, réserve de capacité par entrée |
| Exports | note de calcul **PDF** (en-tête et pied de page paramétrables), impression, schéma **DXF R12** (1 unité = 1 m, calques GIRA_*), tableau des résultats copiable vers Excel/Word |
| Fichiers | format **.gbs** de Girabase 4 en lecture et en écriture : les anciens projets s'ouvrent directement et un projet enregistré ici s'ouvre dans le logiciel d'origine |
| Carte IGN | localisation partout en France : photo aérienne et routes de l'IGN, **un clic sur le carrefour** donne centre, anneau existant, branches (route, nom de voie, orientation N/E/S/O, angle Girabase), commune, WGS84 / Lambert-93 / CC (UTM outre-mer) ; export **KML** ; envoi direct dans le calcul |
| IA (MCP) | `girabase-mcp.exe` : calcul de capacité, lecture/écriture .gbs, analyse de carrefour IGN, conversions de coordonnées et KML à la disposition des assistants d'IA locaux |

## Exécutable Windows (Windows 10 / 11, 64 bits)

**`Girabase.exe`** est un fichier unique, sans installation ni Python : le copier où l'on veut (bureau,
lecteur réseau, clé USB) et double-cliquer. Le premier lancement prend quelques secondes (décompression).

- L'exécutable n'est pas signé : à la première ouverture, Windows SmartScreen peut afficher « Windows a
  protégé votre ordinateur » → *Informations complémentaires* → *Exécuter quand même*.
- Si l'antivirus du poste bloque l'exe unique, utiliser la **version dossier** (`Girabase-Windows.zip`) :
  décompresser et lancer `Girabase\Girabase.exe` (copier tout le dossier, pas seulement le `.exe`).
- Ouvrir les `.gbs` par double-clic : clic droit sur un `.gbs` › Ouvrir avec › Choisir une autre application
  › `Girabase.exe` › Toujours utiliser.
- **Auto-contrôle** : `Girabase.exe --autotest C:\temp\essai` recalcule le cas de référence du guide Girabase,
  contrôle la localisation (données BD TOPO embarquées), produit une note PDF, un DXF et un KML dans le dossier
  indiqué et écrit `autotest_girabase.txt` (« CONFORME »).

### Recompiler l'exécutable

Après une modification du code : installer Python 3.12 « pour l'utilisateur » depuis
<https://www.python.org/downloads/windows/> (cocher *Add python.exe to PATH*), puis double-cliquer sur
**`construire_exe.bat`** (environnement local, versions figées dans `requirements.txt` et
`requirements-dev.txt`, tests, puis
compilation dans `dist\`). Sur GitHub, le workflow `.github/workflows/girabase-python.yml` (à la racine du
dépôt) relance les tests et recompile les exécutables à chaque modification du dossier `girabase-python/` ;
les fichiers produits se téléchargent dans l'onglet *Actions*. Pour lancer sans compiler :
`python -m pip install -r requirements.txt` puis `python lancer_girabase.py`.

## Utilisation

Les onglets suivent l'ordre de saisie de Girabase : **1. Site → 2. Géométrie → 3. Trafics → 4. Résultats**.
Le calcul est relancé automatiquement à chaque modification. Le panneau « Contrôles et recommandations »
signale en rouge les données qui bloquent le calcul et en orange les recommandations. Le dossier
`exemples/` contient le cas de référence du guide Girabase et deux projets fictifs.

Points d'attention repris de l'aide de Girabase :

- branches numérotées **dans le sens de giration** (sens inverse des aiguilles d'une montre) ;
- la matrice comprend **tous** les mouvements, demi-tours et mouvements par tourne-à-droite direct compris ;
- une période n'est calculée que si toutes ses cases utiles sont renseignées (menu Opérations ›
  « Remplacer les cases vides par 0 ») ;
- en rase campagne, travailler de préférence sur la 30<sup>e</sup> heure.

## Fidélité au logiciel d'origine

Le moteur (`girabase/calcul.py`) est une transcription ligne à ligne de `GIRATOIRE.cls`, `BRANCHE.cls` et
`TRAFIC.cls` : coefficients par environnement, cas du mini-giratoire (coefficients de rase campagne),
largeur d'entrée utile LEU, coefficients de gêne KI, KE, KS et KAE, trafic gênant, perte de capacité piétons,
trois régimes du temps d'attente, longueurs de stockage, saturation d'une branche. Les grandeurs typées
`Single` en VB6 sont arrondies en simple précision et les affectations à des `Integer` suivent l'arrondi
bancaire de VB, ce qui reproduit les mêmes trafics gênants entiers. Les conseils (`conseils.py`) reprennent
les règles et les messages de `Données.frm` et `Résultats.frm`.

**Cas de référence du logiciel d'origine.** Le guide utilisateur CERTU/CEREMA « Girabase Version 4.0 »
(révision du 03/06/2015) montre, en captures d'écran, un giratoire complet (Marcellin / Mendès France,
Lyon, périurbain) avec ses résultats calculés par GIRABASE 4. Ce cas est fourni dans
`exemples/exemple_guide_certu.gbs` : les **24 valeurs** du tableau de résultats (réserve en uvp/h et en %,
files moyenne et maximale, attentes moyenne et totale, 4 branches) et les conseils de fonctionnement sont
reproduits **à l'identique** (`tests/test_reference_guide.py`).

Les autres tests (`tests/`, plus de 130 cas) vérifient les formules sur des calculs faits à la main, contre
une seconde implémentation indépendante, et les parcours de l'interface. Pour aller plus loin, rouvrir
quelques `.gbs` d'études passées et comparer avec leurs sorties Girabase 4.

Choix et écarts connus, tous mineurs :

- conversion VL/PL/2R → uvp avec troncature des demi-uvp des deux-roues, comme le code (l'aide parlait
  d'arrondi supérieur) ;
- une case piétons laissée vide compte 0 (le code d'origine utilisait −1, ce qui majorait la capacité de
  moins de 0,1 %) ;
- les mouvements supérieurs à 2 500 uvp/h (par exemple après multiplication) déclenchent un avertissement
  de domaine de validité au lieu d'un blocage ;
- le contrôle de chevauchement des branches est recodé sur le même principe géométrique ;
- le schéma est un schéma de principe (longueur des îlots fixée pour la lisibilité), pas une épure de giration.

## Localisation sur la carte IGN

Dans l'onglet **Site**, le bouton **Localiser sur la carte IGN** (Ctrl+L), ou **Fichier → Nouveau giratoire depuis
la carte IGN**, ouvre la carte de France :

1. on se rapproche du carrefour à la molette, ou l'on tape une commune, une adresse ou des coordonnées
   (Google Maps, Lambert-93, CC ; outre-mer, UTM avec la zone : `UTM 40S 342177 7639537`) ;
2. aux grandes échelles, la photographie aérienne et la couche Routes de l'IGN s'affichent ;
3. **Pointer le carrefour**, puis un clic sur le carrefour : la BD TOPO de l'IGN donne le centre, l'anneau
   existant et les branches avec leur nom de route, leur orientation et leurs angles ;
4. l'anneau projeté se saisit au clavier et les axes s'ajustent à la souris ;
5. **Envoyer dans Girabase** crée le projet ou met à jour la géométrie du projet ouvert, trafics conservés.

Le détail est dans le [guide d'utilisation](docs/guide-utilisateur.md#4-localiser-le-giratoire-sur-la-carte-ign).
Les données de l'IGN sont sous Licence Ouverte Etalab 2.0. Girabase affiche les mentions de source et les
reprend dans les projets et les exports ; voir [sources et licences](docs/sources-et-licences.md).

## Serveur MCP pour les assistants d'IA

`girabase-mcp.exe` (ou `python -m girabase.mcp`) est un serveur
[Model Context Protocol](https://modelcontextprotocol.io) en stdio, sans dépendance. Il expose sept outils :

- `calculer_capacite` ;
- `lire_projet_gbs` et `ecrire_projet_gbs` ;
- `analyser_carrefour` ;
- `convertir_coordonnees` ;
- `rechercher_lieu` ;
- `exporter_kml`.

Pour Claude Desktop, double-cliquez `girabase.mcpb`, ou déclarez-le dans la configuration :

```json
{ "mcpServers": { "girabase": { "command": "C:\\Outils\\Girabase\\girabase-mcp.exe" } } }
```

Les autres clients (LM Studio, Jan, AnythingLLM…) utilisent le même bloc `mcpServers`. Le format JSON
d'échange d'un giratoire est décrit dans `girabase/echange.py`. Voir le
[guide, chapitre 6](docs/guide-utilisateur.md#6-utiliser-girabase-avec-un-assistant-dia-mcp).

## Export DXF

Format **DXF R12**, écrit directement par le programme : il s'ouvre ou s'insère dans toutes les versions
d'AutoCAD et de COVADIS. Centre du giratoire en (0, 0), branche 1 sur l'axe des X, 1 unité = 1 m.
Calques : `GIRA_ILOT_CENTRAL`, `GIRA_BANDE_FRANCH`, `GIRA_ANNEAU`, `GIRA_BORDS_BRANCHES`,
`GIRA_ILOTS_SEPARATEURS`, `GIRA_AXES`, `GIRA_TEXTES` et `GIRA_FLUX` (si le diagramme de flux est coché).
Insérer le DXF dans le plan, puis DEPLACER et ROTATION pour le caler sur les axes réels.

## Structure

Dans le fork du dépôt du CEREMA, ce projet occupe le dossier `girabase-python/` ; les fichiers VB6 d'origine,
à la racine, sont inchangés.

```
girabase/
  constantes.py   coefficients, bornes de validité, messages de Girabase
  modele.py       giratoire, branches, périodes de trafic
  calcul.py       moteur de capacité (portage de GIRATOIRE/BRANCHE/TRAFIC.cls)
  conseils.py     validité, recommandations, conseils sur les résultats
  gbs.py          lecture / écriture des fichiers .gbs
  geometrie.py    géométrie du schéma (partagée écran / DXF)
  dxf_export.py   export AutoCAD
  formats.py      mise en forme des résultats comme Girabase
  echange.py      format JSON d'échange (giratoire, résultats)
  gui/            interface PySide6 (onglets, schéma, courbes, note de calcul, guide)
  carto/          localisation : projections (Lambert-93, CC, UTM), services IGN, analyse BD TOPO,
                  conception automatique, site géoréférencé, export KML ; carto/gui/ : fenêtre de la carte
  mcp/            serveur MCP (stdio, JSON-RPC 2.0) et ses outils
docs/             guide d'utilisation, sources et licences, captures
tests/            moteur, format .gbs, conseils, DXF, projections, carte, interface, serveur MCP
outils/           assemblage de l'extension girabase.mcpb et du guide PDF
```

Le moteur n'a aucune dépendance graphique : il peut être utilisé seul dans un script, par exemple pour
traiter une série de variantes :

```python
from girabase import gbs
from girabase.calcul import calculer
for res in calculer(gbs.lire("mon_giratoire.gbs")):
    for b in res.branches:
        print(res.periode.nom, b.nom, round(b.RC_pct or 0), "%")
```

## Projets voisins

- [CEREMA/territoires-ville.Girabase](https://github.com/CEREMA/territoires-ville.Girabase) : code source
  d'origine (VB6), base de ce fork.
- [nic01asFr/Girabase](https://github.com/nic01asFr/Girabase) : autre fork, orienté web (API FastAPI, widget
  Grist) avec un moteur Python simplifié.

## Licence

GNU GPL v3 (fichier `LICENSE`), comme le code source d'origine du CEREMA. L'exécutable inclut Qt for Python
(PySide6, LGPL v3). Usage interne libre ; en cas de
diffusion à d'autres services ou collectivités, le code source doit accompagner l'exécutable et rester sous
GPL. Ce portage n'est ni édité ni validé par le CEREMA.

Girabase Python est un travail personnel, mis à la disposition de toutes les collectivités territoriales
et de leurs bureaux d'études.
