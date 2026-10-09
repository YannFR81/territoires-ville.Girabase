"""Aide intégrée : méthode de calcul et lecture des résultats."""

TEXTE_METHODE = """
<h2>Méthode de calcul</h2>
<p>La capacité d'une entrée dépend surtout du <b>trafic gênant</b> au droit de cette entrée, composé :</p>
<ul>
<li>du <b>trafic tournant</b> qui passe devant l'entrée, pondéré selon qu'il circule à l'intérieur ou à
l'extérieur de l'anneau (coefficients KI et KE, fonction du rayon utile et de la largeur d'anneau) ; un véhicule
qui sort à l'une des deux branches suivantes est supposé rouler à l'extérieur, d'autant plus que la sortie est
proche (coefficient KAE) ;</li>
<li>d'une partie du <b>trafic sortant</b> à la même branche (l'automobiliste en attente ne sait pas toujours si
le véhicule va sortir) ; cette gêne diminue quand l'îlot séparateur s'élargit (coefficient KS).</li>
</ul>
<p>Capacité : <b>Cvh = 3600 / Tf · exp(−Qg / 3600 · (Tg − Tf / 2)) · (LE / 3,5)<sup>Te</sup></b>, avec Tg
(créneau critique), Tf (créneau complémentaire, majoré de 35 % si rampe &gt; 3 %) et Te selon l'environnement.
La largeur d'entrée retenue est plafonnée par la largeur utile LEU, fonction de l'anneau.
La traversée des piétons réduit ensuite la capacité. Les mini-giratoires (R = 0) utilisent les coefficients
de rase campagne.</p>
<p>Le temps moyen d'attente et les longueurs de file (moyenne et maximale, en véhicules) découlent du taux
de charge de l'entrée.</p>
<p><b>Entrées à plusieurs voies</b> : le nombre de véhicules stockés est donné pour l'ensemble de l'entrée ;
le diviser par le nombre de voies pour obtenir la longueur de file, en tenant compte d'une répartition
inégale (la voie de gauche est souvent moins chargée). Le temps d'attente, lui, tient déjà compte du nombre
de voies puisqu'il dépend de la capacité globale de l'entrée.</p>
<h2>Saisie</h2>
<ul>
<li>Branches numérotées dans le <b>sens de giration</b>, angles mesurés entre axes depuis la branche 1.</li>
<li>Largeur d'entrée mesurée 4 m avant le cédez-le-passage ; si l'entrée est évasée, Girabase retient la
moyenne des largeurs à 4 m et à 15 m.</li>
<li>Largeur de sortie mesurée 4 m après l'anneau ; îlot mesuré à la base du triangle de construction.</li>
<li>Bande franchissable : à associer à l'îlot central si sa pente dépasse 6 %, si ses bordures dépassent 3 cm
ou si le rayon extérieur dépasse 15 m.</li>
<li>La matrice doit comprendre <b>tous</b> les mouvements, demi-tours et mouvements par voie directe de
tourne-à-droite compris. Équivalences : 1 VL = 1 uvp, 1 PL = 2 uvp, 1 deux-roues = 0,5 uvp.</li>
<li>Cocher « tourne-à-droite » retire seulement du calcul le mouvement vers la branche suivante : les largeurs
saisies restent celles situées entre l'anneau et la voie directe.</li>
<li>En rase campagne, préférer la 30<sup>e</sup> heure à une pointe exceptionnelle de week-end.</li>
</ul>
<h2>Lecture de la réserve de capacité</h2>
<ul>
<li><b>25 à 80 %</b> sur toutes les entrées : bon fonctionnement en heure de pointe.</li>
<li><b>Plus de 80 %</b> partout : le giratoire n'est probablement pas justifié ; plus de 50 % sur une entrée :
vérifier qu'elle n'est pas surdimensionnée (2 voies réductibles à 1, au bénéfice de la sécurité).</li>
<li><b>5 à 25 %</b> : files assez longues possibles aux hyper-pointes ou aux pointes saisonnières.</li>
<li><b>Moins de 5 %</b>, ou réserve négative : fortes perturbations. Pistes : élargir l'entrée (si le trafic
entrant dépasse la moitié du trafic gênant), élargir l'îlot séparateur (si le trafic sortant représente 25 à 75 %
du trafic gênant), élargir l'anneau, voie directe de tourne-à-droite, dénivellation, plan de circulation.</li>
</ul>
<p>« Saturer la branche » recalcule le giratoire avec un trafic entrant limité à la capacité d'une entrée
saturée : les autres entrées ne subissent alors que le trafic qui entre réellement.</p>
<h2>Échanges avec AutoCAD / COVADIS</h2>
<p>L'export DXF trace un schéma de principe à l'échelle (1 unité = 1 m), centre du giratoire en (0,0), branche 1
sur l'axe des X, un calque par élément (GIRA_*). Il se déplace et s'oriente sur le plan avec DEPLACER et
ROTATION ; il ne remplace pas une épure de giration.</p>
<p>Les fichiers <b>.gbs</b> sont ceux de GIRABASE 4 : un projet enregistré ici s'ouvre dans le logiciel d'origine
et réciproquement.</p>
"""
