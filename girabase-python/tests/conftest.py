import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from girabase.constantes import Milieu  # noqa: E402
from girabase.modele import Branche, Giratoire  # noqa: E402

MATRICE_4 = [[0, 300, 500, 150],
             [250, 0, 200, 100],
             [600, 180, 0, 120],
             [100, 90, 140, 0]]


@pytest.fixture
def gir4() -> Giratoire:
    """Giratoire de rase campagne, 4 branches à 90°, entrées à une voie, sans piétons."""
    g = Giratoire(nom="Test", milieu=Milieu.RASE_CAMPAGNE, R=15, Bf=1.5, LA=8)
    for k, a in enumerate([0, 90, 180, 270]):
        g.branches.append(Branche(nom=f"B{k + 1}", angle=a, le4=4, li=3, ls=4.5))
    p = g.nouvelle_periode("HPM")
    p.uvp = [r[:] for r in MATRICE_4]
    p.pietons = [0] * 4
    return g
