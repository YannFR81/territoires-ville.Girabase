"""Constantes du modèle Girabase 4 (CERTU / CETE de l'Ouest).

Valeurs reprises de GirabaseMain.bas (version française, GIRAWAL non défini).
"""
from enum import IntEnum


class Milieu(IntEnum):
    RASE_CAMPAGNE = 0
    PERIURBAIN = 1
    CENTRE_VILLE = 2

    @property
    def libelle(self) -> str:
        return LIBELLES_MILIEU[self]


LIBELLES_MILIEU = {
    Milieu.RASE_CAMPAGNE: "Rase campagne",
    Milieu.PERIURBAIN: "Périurbain",
    Milieu.CENTRE_VILLE: "Centre-ville",
}


class UniteAngle(IntEnum):
    DEGRE = 0
    GRADE = 1

    @property
    def demi_tour(self) -> int:
        """Équivalent de pi dans l'unité (eqvPI)."""
        return 180 if self is UniteAngle.DEGRE else 200

    @property
    def libelle(self) -> str:
        return "degrés" if self is UniteAngle.DEGRE else "grades"


# Coefficients du calcul de capacité (NOTE DE CALCUL §1.3)
#   Te  : exposant de la largeur d'entrée
#   Tg  : créneau critique (s)
#   Tf1 : créneau complémentaire (s)
TE = {Milieu.RASE_CAMPAGNE: 0.7, Milieu.PERIURBAIN: 0.8, Milieu.CENTRE_VILLE: 0.85}
TG = {Milieu.RASE_CAMPAGNE: 4.75, Milieu.PERIURBAIN: 4.55, Milieu.CENTRE_VILLE: 4.4}
TF1 = {Milieu.RASE_CAMPAGNE: 2.25, Milieu.PERIURBAIN: 2.05, Milieu.CENTRE_VILLE: 1.8}
COEF_LEU = 1.2
COEF_RAMPE = 1.35          # Tf majoré si rampe > 3 %

# Équivalences véhicules (1 VL = 1 uvp, 1 PL = 2 uvp, 1 2R = 0,5 uvp)
COEF_VL = 1
COEF_PL = 2
COEF_2R = 0.5

# Bornes de validité (aide en ligne §1.1.2 et Données.frm)
NB_BRANCHES_MIN = 3
NB_BRANCHES_MAX = 8
R_MAX = 100.0
BF_MAX = 3.0
LA_MIN = 4.5
LA_MAX_RC = 12.0
LA_MAX_URBAIN = 18.0
LE4_MAX = 12.0
LS_MAX = 10.0
Q_MAX = 2500          # uvp/h par mouvement
QP_MAX = 2500         # piétons/h
RG_MINI_MIN = 7.5
RG_MINI_MAX = 12.0
RG_MIN = 12.0
QP_DEFAUT = 10        # trafic piéton proposé à la création d'une période
LI_DEFAUT = 3.0
LONGUEUR_BRANCHE_DESSIN = 18.0  # m, longueur des branches sur le schéma

# ---------------------------------------------------------------------------
# Messages (strDonnées.bas, strRésultats.bas)
# ---------------------------------------------------------------------------
M = {
    # Recommandations de conception
    "TropDeBranchesEnRC": "Un giratoire à plus de 6 branches n'est pas recommandé en rase campagne.",
    "RTropGrand": "Un rayon d'îlot infranchissable supérieur à 25 m est très rarement justifié.",
    "RTropGrand2": "Il peut être réduit au bénéfice de la sécurité.",
    "LATropGrand": "Un anneau aussi large est inutile.",
    "LEPetit": "Si possible, une largeur d'entrée d'au moins 3 m est préférable.",
    "LETropLargeEnRC": "Une entrée à 3 voies n'est pas recommandée en rase campagne.",
    "LETropLargePourPietons": "Les piétons auront des difficultés à traverser l'entrée.",
    "LSPetit": "Si possible, une largeur de sortie d'au moins 3,5 m est préférable.",
    "LSTropLarge": "Une sortie aussi large est rarement utile.",
    "RTropGrandPourMiniG": "Pour un mini-giratoire, le rayon est pris égal à 0. "
                           "Dans les autres cas, le rayon est obligatoirement supérieur à 3,5 m.",
    "RNulEnRC": "Les mini-giratoires ne sont pas autorisés en rase campagne.",
    "RNulEnPU": "Un mini-giratoire ne peut pas être réalisé en entrée d'agglomération "
                "ou sur un itinéraire de contournement.",
    "LENul": "Aucune entrée possible - Branche de sortie uniquement.",
    "LETropPetit": "L'entrée est trop étroite.",
    "LE2Roues": "Entrée spéciale 2 roues sinon l'entrée est trop étroite.",
    "LSNul": "Aucune sortie possible - Branche d'entrée uniquement.",
    "LSTropPetit": "La sortie est trop étroite.",
    "LS2Roues": "Sortie spéciale 2 roues sinon la sortie est trop étroite.",
    "QPTropGrand": "Le trafic piéton est très important. Vérifiez vos données.",
    "QTropGrand": "Le trafic est très important. Vérifiez vos données.",
    "RgVoirGiration": "Vérifiez la giration des bus et poids-lourds.",
    "RgVoirGirationEnRC": "Cette taille de giratoire n'est acceptable que sur le réseau secondaire "
                          "en rase campagne. Vérifiez la giration des bus et poids-lourds.",
    "RgTropPetitPourMiniG": "Le rayon extérieur est trop faible pour un mini-giratoire.",
    "RgTropGrandPourMiniG": "Un mini-giratoire n'est pas approprié. L'emprise disponible permet "
                            "l'aménagement d'un giratoire semi-franchissable.",
    "RgTropPetit": "Avec une entrée à 2 voies, un rayon extérieur d'au moins 20 m est souhaitable "
                   "en rase campagne.",
    "EvasementEnRC": "En rase campagne, l'évasement devrait être complet 35 m avant l'entrée.",
    "EvasementTropPetit": "La longueur d'évasement est courte.",
    "LATropEtroit": "L'anneau est trop étroit.",
    "LATropEtroitPourEntrer": "L'anneau est trop étroit pour une circulation optimale de la voie d'entrée ",
    "LITropPetit": "La largeur d'îlot séparateur est insuffisante pour les piétons.",
    "LITropGrand": "Le trafic sortant n'a pas d'influence sur la capacité. "
                   "Vous pouvez éventuellement réduire la largeur de l'îlot séparateur.",
    "Bf": "Pour un giratoire semi-franchissable, la largeur de bande franchissable doit être "
          "comprise entre 1,5 m et 2 m.",
    "AngleTropPetitPourMiniG": "Configuration dangereuse : risque de contournement permanent par la "
                               "gauche pour le tourne à gauche.",
    "AnglePourMiniG": "Configuration dangereuse : risque de contournement par la gauche pour le "
                      "tourne à gauche.",
    "QTropPetitPourTAD": "Le trafic ne justifie pas la présence de cette voie directe de tourne-à-droite.",
    "RapportLE": "Le rapport LE à 4m / LE à 15m doit être compris entre 1 et 2,5.",
    "BfTropPetitPourMiniG": "Le dôme central franchissable d'un mini-giratoire doit avoir un rayon "
                            "compris entre 1,5 m et 2,5 m.",
    "LTropGrand": "La somme des largeurs d'entrée à 4m, d'îlot et de sortie doit être inférieure "
                  "au diamètre extérieur de l'anneau.",
    "QEGrandPourMiniG": "Attention ! Trafic important, il existe un risque de dysfonctionnement.",
    "QETropGrandPourMiniG": "Le trafic est trop important pour un mini-giratoire.",
    "QETropGrand": "Trafic très important pour un giratoire.",
    # Résultats / conseils de fonctionnement
    "BrancheSortie": "Branche de sortie uniquement",
    "BrancheEntree": "Branche d'entrée uniquement",
    "MatriceSaturation": "Branche avec un trafic en entrée limité à sa capacité",
    "TraficsIncomplets": "Les trafics de la période en cours sont incomplets ; "
                         "les conseils relatifs à cette période ne peuvent être édités.",
    "QEnul": "Comme il n'y a jamais de trafic, la largeur d'entrée de la branche devrait être nulle.",
    "QSnul": "Comme il n'y a jamais de trafic, la largeur de sortie la branche devrait être nulle.",
    "IlotEtroit": "Un îlot plus large serait préférable pour les piétons.",
    "IlotASeparer": "Penser à séparer l'entrée de la sortie par une bande en relief, une zone pavée ou autre.",
    "LS2voiesN": "Une sortie à deux voies est nécessaire. ",
    "LS2voiesP": "Une sortie à deux voies peut être envisagée. ",
    "TraverseePietons": "Attention aux traversées piétonnes.",
    "RCnegative": "ENTRÉE SATURÉE ; vous pouvez : ",
    "RCfaible": "Attention, la réserve de capacité est faible ; vous pouvez : ",
    "RC1": " - envisager une voie directe de tourne-à-droite",
    "RC2": " - élargir l'entrée à 2 voies",
    "RC2p": ", mais attention au traitement des traversées piétonnes",
    "RC3": " - élargir l'entrée à 3 voies",
    "RC3p": " si le trafic piéton est très faible",
    "RC4": " - élargir l'anneau et, si nécessaire, l'entrée",
    "RC5": " - élargir l'îlot séparateur",
    "RC6": " - agrandir le giratoire",
    "RC11": "Un des mouvements est assez important pour envisager de déniveler le carrefour.",
    "RC12": "Une entrée à une voie suffit probablement.",
    "RC13": "Une entrée à une voie suffit probablement et serait plus favorable aux piétons",
    "RC14": "Une entrée à 2 voies suffit probablement.",
    "TMA1": "Le temps d'attente sur la branche est important.",
    "TMA2": "Le temps moyen d'attente sur la branche est très important.",
    "LK1": "La file d'attente sur la branche est importante. Attention aux pertes de visibilité "
           "en approche dues au profil en long ou au tracé.",
    "LK2": "La file d'attente sur la branche est très importante. Attention aux pertes de visibilité "
           "en approche dues au profil en long ou au tracé.",
    "LK3": "La file d'attente sur la branche est importante, penser au carrefour en amont.",
    "LK4": "La file d'attente sur la branche est très importante, penser au carrefour en amont.",
    "LK5": "La file d'attente sur la branche peut être importante. Attention aux pertes de visibilité "
           "en approche dues au profil en long ou au tracé.",
    "LK6": "La file d'attente sur la branche peut être importante, penser au carrefour en amont.",
}

# Aides à la saisie (IDi_*)
AIDE_BF = ("Le rayon extérieur doit être inférieur à 15 m, la bande franchissable doit être de "
           "pente inférieure à 6 % et être délimitée par des bordures de moins de 3 cm sans ligne "
           "continue. Sinon, la bande franchissable est à associer à l'îlot central infranchissable.")
AIDE_LE4 = ("Largeur conseillée entre marquages ou à défaut entre bordures : 3,5 à 4 m pour une voie, "
            "6 à 7 m pour 2 voies, 9 à 10 m pour 3 voies.")
AIDE_LS = ("Largeur conseillée entre marquages ou à défaut entre bordures : 4 à 5 m pour une voie, "
           "6 à 7 m pour 2 voies.")
AIDE_QP = "Trafic piéton bidirectionnel traversant la branche (piétons/h)."
