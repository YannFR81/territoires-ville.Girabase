# Sources des données et licences

*Vérifié le 9 octobre 2026.*

## Le logiciel

| Élément | Licence |
|---|---|
| Girabase — portage Python (ce dépôt) | GNU GPL v3, comme le code source d'origine publié par le CEREMA |
| Code d'origine GIRABASE 4 (VB6) | GNU GPL v3 — [CEREMA/territoires-ville.Girabase](https://github.com/CEREMA/territoires-ville.Girabase) |
| Qt for Python (PySide6), inclus dans l'exécutable | LGPL v3 |
| Python | PSF License |

## Données cartographiques utilisées par la localisation

Les images et les objets sont lus à la demande pour la zone affichée, sur les services publics de la
**Géoplateforme de l'IGN** (`data.geopf.fr`) et, en option, sur les tuiles d'**OpenStreetMap**, puis gardés
dans un cache local (300 Mo au plus). Seule exception : deux petits extraits de la BD TOPO® (deux carrefours
réels, 15 tronçons) sont embarqués pour l'auto-contrôle hors ligne, et quatre autres servent aux tests du
dépôt. Leur source, leur date d'extraction et leur licence sont indiquées dans
[`girabase/carto/donnees/LISEZMOI.md`](../girabase/carto/donnees/LISEZMOI.md) et
[`tests/donnees/LISEZMOI.md`](../tests/donnees/LISEZMOI.md).

| Usage dans Girabase | Données / service | Producteur | Licence |
|---|---|---|---|
| Fond : photographie aérienne | Orthophotographies (BD ORTHO®) — WMTS `ORTHOIMAGERY.ORTHOPHOTOS` | IGN | Licence Ouverte Etalab 2.0 |
| Fond : plan | Plan IGN — WMTS `GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2` | IGN | Licence Ouverte Etalab 2.0 |
| Couche « Routes » | Réseau routier (BD TOPO®) — WMTS `TRANSPORTNETWORKS.ROADS` | IGN | Licence Ouverte Etalab 2.0 |
| Couche cadastre | Parcellaire Express (PCI) — WMTS `CADASTRALPARCELS.PARCELLAIRE_EXPRESS` | IGN d'après DGFiP | Licence Ouverte Etalab 2.0 |
| Analyse du carrefour | BD TOPO® tronçons de route — WFS `BDTOPO_V3:troncon_de_route` | IGN | Licence Ouverte Etalab 2.0 |
| Commune, code INSEE | ADMIN EXPRESS COG — WFS `ADMINEXPRESS-COG.LATEST:commune` | IGN | Licence Ouverte Etalab 2.0 |
| Recherche d'adresses | Géocodage de la Géoplateforme (BAN, BD TOPO®) | IGN, BAN | Licence Ouverte Etalab 2.0 |
| Fond OpenStreetMap (option) | `tile.openstreetmap.org` | Contributeurs OpenStreetMap | ODbL (données), CC BY-SA 2.0 (tuiles) |

## Obligations et mise en conformité

**Licence Ouverte Etalab 2.0.** Réutilisation libre, y compris commerciale, à condition de mentionner la
paternité : la source (au minimum le producteur) et la date de dernière mise à jour
([texte de la licence](https://www.etalab.gouv.fr/licence-ouverte-open-licence/)).

- La carte affiche toujours, dans son coin inférieur droit, la mention du fond et des couches visibles :
  « © IGN – Géoplateforme, orthophotographies » ou « …, Plan IGN », « © IGN – Routes »,
  « © IGN – Parcellaire Express », ou « © contributeurs OpenStreetMap » avec le fond OSM. Un clic sur la
  mention ouvre la fenêtre des sources et licences, avec les liens vers les licences.
- Après une analyse de carrefour, Girabase rédige la mention
  « Sources : IGN — BD TOPO®, tronçons mis à jour jusqu'au …, ADMIN EXPRESS (Géoplateforme, consultée le …),
  Licence Ouverte / Open Licence Etalab 2.0 ». Pour un giratoire dessiné entièrement à la main, la mention
  porte sur le fond utilisé (« Sources : IGN – Géoplateforme, … consultée le …, Licence Ouverte … », et
  « © contributeurs OpenStreetMap » avec le fond OSM). Cette mention est reprise :
  - dans la localisation du projet `.gbs`, donc dans la note de calcul ;
  - dans le fichier de site `.gsite` ;
  - dans l'export KML.

**Conditions générales d'utilisation de la Géoplateforme** ([CGU](https://cartes.gouv.fr/cgu/),
[limites d'usage](https://cartes.gouv.fr/aide/fr/guides-utilisateur/utiliser-les-services-de-la-geoplateforme/limites-d-usage/)).
Elles demandent un usage raisonnable, sans entraver le fonctionnement des API. Les limites par adresse IP sont
les suivantes :

- WFS : 30 requêtes/s ;
- géocodage : 50 requêtes/s ;
- WMTS (tuiles) : non limité.

En cas de dépassement, le service répond HTTP 429 avec un délai `Retry-After`. Girabase reste très en deçà :
deux requêtes WFS par analyse de carrefour, une par recherche. Il attend le délai indiqué avant de réessayer et
met les tuiles en cache. Le serveur MCP limite ses propres appels à 5 requêtes/s.

**OpenStreetMap** ([droits d'auteur](https://www.openstreetmap.org/copyright),
[politique des tuiles](https://operations.osmfoundation.org/policies/tiles/)).

- La mention « © contributeurs OpenStreetMap » est visible sur la carte, avec un lien vers
  `openstreetmap.org/copyright` dans la fenêtre des sources.
- L'application s'identifie par un User-Agent stable : `Girabase-Python/<version> (+URL du dépôt)`.
- Le cache local respecte les en-têtes HTTP.
- Il n'y a ni téléchargement en masse, ni préchargement hors de la zone affichée, ni usage hors ligne.

Le Plan IGN est le fond proposé par défaut. OpenStreetMap n'est qu'une option.

**Google Maps / Street View.** Ces services ne servent pas de fond de carte : leurs conditions l'interdisent
en dehors de leurs propres API. Girabase se contente d'ouvrir le lieu dans le navigateur.

## Responsabilité

Le centre, l'anneau et les branches proposés à partir de la BD TOPO® sont des **propositions schématiques** à
vérifier sur un plan topographique. Ni l'IGN ni le CEREMA ne sont responsables de leur usage. Ce portage
n'est ni édité ni validé par le CEREMA.
