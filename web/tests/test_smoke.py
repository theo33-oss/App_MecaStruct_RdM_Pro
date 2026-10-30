"""Tests de fumée : le paquet s'importe, les données exportées de MATLAB sont présentes et lisibles."""

import json
from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parents[1]


def test_package_importable():
    import mecastruct  # noqa: F401
    import mecastruct.core  # noqa: F401


@pytest.mark.parametrize(
    "name",
    [
        "materials.json",
        "profiles.json",
        "bearing_pressures.json",
        "section_presets.json",
        "formula_sheets.json",
        "kt_charts.json",
        "mohr_table.json",
        "units.json",
    ],
)
def test_data_files_readable(name):
    path = WEB / "data" / name
    if not path.exists():
        pytest.skip(f"{path} absent : lancer l'étape E00 (export MATLAB)")
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    assert data, f"{name} est vide"


def test_golden_files_readable():
    golden = WEB / "tests" / "golden"
    files = sorted(golden.glob("golden_*.json"))
    if not files:
        pytest.skip("Aucun fichier golden : lancer l'étape E00 (export MATLAB)")
    for p in files:
        with p.open(encoding="utf-8") as f:
            cases = json.load(f)
        assert isinstance(cases, list) and cases, p.name
        assert {"id", "fonction", "entrees", "sortie", "erreur"} <= cases[0].keys(), p.name
