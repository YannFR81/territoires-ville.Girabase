# Nouveautés de Girabase Python

## 1.2.1 — 9 octobre 2026

- Girabase Python s'adresse à toutes les collectivités territoriales. Les textes ont été rendus génériques.
- Guide PDF : correction des caractères remplacés par des pavés noirs dans le fichier compilé sous Windows.
- La note de calcul porte par défaut l'en-tête « Girabase — capacité des carrefours giratoires » et la devise
  « L’intelligence artificielle au service de l’action publique efficiente. ». L'organisme, le service et le pied de page restent modifiables
  dans *Fichier → Paramètres de la note de calcul*.

## 1.2.0 — 9 octobre 2026

- **Localisation du giratoire sur la carte de l'IGN**, partout en France :
  - photographie aérienne et couche Routes aux grandes échelles ;
  - un clic sur le carrefour lit dans la BD TOPO le centre, l'anneau existant et les branches (route, nom de
    voie, orientation, angle Girabase) ;
  - commune, coordonnées WGS84, Lambert-93 et CC (UTM outre-mer) ;
  - export KML et envoi direct dans le calcul.
- **Serveur MCP** pour les assistants d'IA locaux : `girabase-mcp.exe` et l'extension Claude Desktop
  `girabase.mcpb`. Il donne accès au calcul de capacité, aux fichiers `.gbs`, à l'analyse de carrefour, aux
  coordonnées et à l'export KML.
- **Guide d'utilisation** intégré (F1) et en PDF.
- Fenêtre **Sources des données et licences** : mentions de source exigées par la Licence Ouverte Etalab 2.0,
  reprises dans les projets et les exports.
- Interface lisible en thème clair comme en thème sombre de Windows.
- L'en-tête de la note de calcul se règle dans *Fichier → Paramètres de la note de calcul* : il n'est plus
  pré-rempli.

## 1.1.0

- Portage complet de GIRABASE 4 :
  - même moteur de calcul ;
  - mêmes contrôles et conseils ;
  - fichiers `.gbs` lus et écrits.
- Le cas de référence du guide Girabase 4 est reproduit à l'identique.
- Note de calcul PDF, export DXF R12 pour AutoCAD / COVADIS.
- Valeurs par défaut et conseils complétés d'après le guide utilisateur PDF de Girabase 4.
- Exécutable Windows 10 / 11 en fichier unique, et version dossier.
