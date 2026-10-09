"""Export DXF R12 : relu avec ezdxf (dépendance de test uniquement)."""
import pytest

from girabase.calcul import flux
from girabase.dxf_export import exporter_dxf

ezdxf = pytest.importorskip("ezdxf")
from ezdxf import recover  # noqa: E402


def test_export_dxf(gir4, tmp_path):
    gir4.nom = "Giratoire de l'Écluse"
    chemin = tmp_path / "schema.dxf"
    exporter_dxf(gir4, chemin, flux(gir4, gir4.periodes[0]))
    doc, auditeur = recover.readfile(chemin)
    assert not auditeur.has_errors
    assert doc.dxfversion == "AC1009"
    msp = doc.modelspace()
    rayons = sorted(round(e.dxf.radius, 3) for e in msp if e.dxftype() == "CIRCLE")
    assert rayons == [15.0, 16.5, 24.5]
    calques = {e.dxf.layer for e in msp}
    assert {"GIRA_ANNEAU", "GIRA_BORDS_BRANCHES", "GIRA_AXES", "GIRA_TEXTES", "GIRA_FLUX"} <= calques
    textes = {e.dxf.text for e in msp if e.dxftype() == "TEXT"}
    assert {"B1", "B2", "B3", "B4"} <= textes
    assert any("Écluse" in t for t in textes)
    polys = [e for e in msp if e.dxftype() == "POLYLINE"]
    assert polys and all(len(list(p.vertices)) >= 2 for p in polys)
    assert {"DASHED", "CENTER"} <= {lt.dxf.name for lt in doc.linetypes}
