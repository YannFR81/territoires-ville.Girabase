# Girabase — fork avec portage Python (version 1.2)

> **Ce fork ajoute [Girabase Python](girabase-python/)**, un portage fidèle de GIRABASE 4 qui fonctionne sur
> Windows 10 et 11 sans installation ni numéro de licence. Il apporte :
> - le même calcul de capacité, validé sur le cas de référence du guide ;
> - la lecture et l'écriture des fichiers `.gbs` ;
> - une note de calcul PDF et un export DXF pour AutoCAD / COVADIS ;
> - la localisation du giratoire sur la carte de l'IGN (photographie aérienne, routes, analyse du carrefour
>   dans la BD TOPO, export KML) ;
> - un serveur MCP pour les assistants d'IA.
>
> - **Télécharger** : [dernière version](https://github.com/YannFR81/territoires-ville.Girabase/releases/latest)
>   (`Girabase.exe`, guide PDF, serveur MCP).
> - **Documentation** : [présentation](girabase-python/README.md) ·
>   [guide d'utilisation](girabase-python/docs/guide-utilisateur.md) ·
>   [sources des données et licences](girabase-python/docs/sources-et-licences.md).
>
> Les fichiers VB6 du CEREMA, ci-dessous et à la racine du dépôt, sont **inchangés**. Le portage est distribué
> sous la même licence GNU GPL v3. Il n'est ni édité ni validé par le CEREMA.

---

*Présentation d'origine du dépôt du CEREMA :*

# territoires-ville.Girabase
<h2>Le logiciel GIRABASE permet de tester les projets de carrefours giratoires du point de vue capacité et d'adapter les caractéristiques géométriques aux prévisions de trafic. Logiciel développé au CERTU sous Visual Basic 6.0. Initialement vendu au CERTU sous licence propriétaire et désormais diffusé en logiciel libre sous licence GPL. Ce logiciel n'est plus maintenu.</h2>

A la 1ere ouverture d'un executable, une interface vous demandant un numéro de licence va s'ouvrir :

   * Indiquez dans le champ Licence au moins un caractère alphanumérique de votre choix puis cliquer sur Enregistrer Une message box vous indiquant que votre licence a été enregistré avec succès apparaitera alors.
   * Dans cette message Box cliquer sur Ok : le logiciel s'ouvrira et 2 fichiers apparaiteront à la racine de votre exécutable (relic.ctu et reser.ctu).
   * Tant que ces 2 fichiers seront présent à la racine de votre exe la fenêtre vous demandant un numéro de licence n'apparaitera pas.
-------------------------------------------------------------------------------------------------------------------------------------
Les guides utilisateurs (.pdf et .odt) et l'aide en ligne (.chm) ont été crées à l'époque où ce logiciel était propriétaire : dans la configuration actuelle ne pas tenir compte des parties sur le contrat de licence qui de fait n'ont plus lieu d'être.

