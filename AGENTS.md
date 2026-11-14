# Girabase — portage Python (fork YannFR81)

Instructions pour les agents d'IA travaillant sur ce dépôt.
Lu par Gemini / Antigravity (`AGENTS.md`) et par Claude (via `CLAUDE.md`).

Amont : CEREMA/territoires-ville.Girabase (code VB6 de Girabase 4, GPL v3).

## Le projet

Portage Python de **Girabase 4** (CERTU / CETE de l'Ouest) : capacité des carrefours giratoires
(réserve de capacité, files, attentes, conseils de conception, note de calcul PDF, export DXF, serveur MCP).

- **Branche de travail : `main`**, dossier `girabase-python/` (version 1.2 ; voir `girabase-python/README.md` et `NOUVEAUTES.md`).
- Les fichiers VB6 à la racine sont le code d'origine : ne pas les modifier.
- CI : `.github/workflows/girabase-python.yml`. Tests : `pytest` dans `girabase-python/`.
- Exécutables Windows publiés dans les *Releases* du fork (`Girabase.exe`, `girabase-mcp.exe`, `girabase.mcpb`).

## Règle absolue
Les **24 résultats du cas de référence du guide Girabase 4** doivent rester reproduits à l'identique.
Toute modification du moteur qui les change est un bug, sauf décision explicite de YannFR81.

## Règles communes à tous les agents (Claude, Gemini / Antigravity, autres)

- **Propriétaire du fork :** YannFR81, projeteur routier (conception routière, AutoCAD / COVADIS).
  C'est lui qui tranche les choix métier et de terminologie.
- **Crédit :** uniquement sous le pseudo **YannFR81**, jamais de nom réel (commits, README, feuilles de route, PR).
- **Langue :** français pour la documentation, les messages de commit et les échanges ; apostrophe typographique ’ dans les textes d'interface.
- **Relations avec le dépôt d'origine (amont) :** proposer d'abord par une *issue* ; n'ouvrir une PR qu'après
  réponse des mainteneurs. Ne jamais pousser ni ouvrir de PR vers l'amont sans accord explicite de YannFR81.
- **Fichiers propres au fork :** `AGENTS.md`, `CLAUDE.md`, `NOTES_REVUE.md` (et `CONTEXTE_YANNFR81.md` le cas échéant)
  ne doivent **jamais** figurer dans une branche proposée à l'amont. Créer les branches destinées à l'amont
  à partir de la branche de l'amont (`upstream/<branche>`), ou retirer ces fichiers avant la PR.
- **Pas de force-push** sur une branche dont une PR est ouverte.

## Travail en binôme

1. Un agent écrit, **l'autre relit** : aucun agent ne valide seul son propre travail.
2. Calculs normatifs ou moteur de calcul : écrire ou compléter d'abord les **tests sur cas de référence**
   (guides, abaques, exemples publiés), puis modifier le code. Un résultat de référence qui change = arrêt et signalement.
3. À la fin de chaque session, ajouter une entrée en tête de `NOTES_REVUE.md`
   (date, agent, branche, fait / vérifié / en suspens / question pour YannFR81).
4. Avant de commencer, lire `NOTES_REVUE.md` pour reprendre là où l'autre agent s'est arrêté.
