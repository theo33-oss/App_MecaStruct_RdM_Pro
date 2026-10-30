"""Outils de comparaison avec les résultats MATLAB exportés (golden files).

Utilisation dans un test :
    from tests.golden_tools import load_cases, get_case, assert_matches
    case = get_case("golden_geometry.json", "rect_100x200_analytical")
    P = geometry.analytical(case["entrees"])
    assert_matches(P, case["sortie"], rel=1e-9)
"""

from __future__ import annotations

import json
import math
from dataclasses import is_dataclass
from pathlib import Path
from typing import Any

import numpy as np

GOLDEN_DIR = Path(__file__).parent / "golden"

# Clés ignorées par défaut : textes libres ou méthode choisie (symbolique / numérique)
DEFAULT_IGNORE = frozenset(
    {
        "report",
        "latex",
        "methodUsed",
        "method",
        "kSource",
        "description",
        "notes",
        "note",
        "Note",
        "planeText",
        "label",
        "title",
    }
)


def load_cases(filename: str) -> list[dict]:
    """Charge la liste des cas d'un fichier golden (NaN / Infinity acceptés)."""
    path = GOLDEN_DIR / filename
    if not path.exists():
        import pytest

        pytest.skip(f"Fichier golden absent : {path} (lancer l'étape E00 dans MATLAB)")
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def get_case(filename: str, case_id: str) -> dict:
    """Renvoie le cas `case_id` du fichier golden `filename`."""
    for c in load_cases(filename):
        if c["id"] == case_id:
            return c
    raise KeyError(f"Cas {case_id!r} absent de {filename}")


def case_ids(filename: str, prefix: str = "", suffix: str = "") -> list[str]:
    """Liste des identifiants de cas (filtrés par préfixe / suffixe), pour pytest.mark.parametrize."""
    path = GOLDEN_DIR / filename
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        cases = json.load(f)
    return [c["id"] for c in cases if c["id"].startswith(prefix) and c["id"].endswith(suffix)]


def _to_plain(actual: Any) -> Any:
    """Convertit DataFrame, dataclass, objets numpy en types Python simples comparables."""
    try:
        import pandas as pd

        if isinstance(actual, pd.DataFrame):
            return actual.to_dict("records")
        if isinstance(actual, pd.Series):
            return actual.to_list()
    except ImportError:  # pragma: no cover
        pass
    if is_dataclass(actual) and not isinstance(actual, type):
        if hasattr(actual, "breaks") and hasattr(actual, "coefs"):
            return actual  # polynôme par morceaux : traité à part
        return {k: getattr(actual, k) for k in actual.__dataclass_fields__}
    if isinstance(actual, np.generic):
        return actual.item()
    return actual


def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float, np.integer, np.floating)) and not isinstance(x, bool)


def _close(a: float, e: float, rel: float, abs_: float) -> bool:
    if math.isnan(e):
        return math.isnan(a)
    if math.isinf(e):
        return a == e
    return math.isclose(a, e, rel_tol=rel, abs_tol=abs_)


def assert_matches(
    actual: Any,
    expected: Any,
    rel: float = 1e-9,
    abs_: float = 1e-12,
    ignore: set[str] | frozenset[str] = frozenset(),
    path: str = "sortie",
    strict_keys: bool = True,
) -> None:
    """Vérifie que `actual` (résultat Python) correspond à `expected` (sortie MATLAB du JSON).

    - dict attendu : chaque clé attendue (hors `ignore` et DEFAULT_IGNORE) doit exister dans `actual`
      si strict_keys, et correspondre récursivement ;
    - nombres : |a - e| <= max(rel*|e|, abs_) ; NaN = NaN ; Inf = Inf ;
    - listes : même longueur, comparaison élément par élément (tableaux numpy acceptés) ;
    - un scalaire MATLAB peut correspondre à un tableau Python d'un élément, et inversement ;
    - une structure MATLAB d'un seul élément (dict) peut correspondre à une liste Python d'un élément ;
    - chaînes commençant par '<' (ex. '<fonction>') : ignorées ;
    - polynôme par morceaux attendu {breaks, coefs, s, valeurs} : on compare les valeurs aux points s.
    """
    ign = DEFAULT_IGNORE | set(ignore)
    actual = _to_plain(actual)

    # polynôme par morceaux
    if isinstance(expected, dict) and {"breaks", "s", "valeurs"} <= expected.keys():
        from mecastruct.core import pp as ppmod  # import tardif : module créé à l'étape E05

        s = np.asarray(expected["s"], dtype=float)
        got = np.asarray(ppmod.ppEval(actual, s), dtype=float)
        _assert_array(got, expected["valeurs"], rel, abs_, path + ".valeurs")
        _assert_array(np.asarray(actual.breaks, dtype=float), expected["breaks"], rel, abs_, path + ".breaks")
        return

    if isinstance(expected, dict):
        if isinstance(actual, (list, tuple)) and len(actual) == 1:
            actual = _to_plain(actual[0])
        assert isinstance(actual, dict), f"{path} : dict attendu, obtenu {type(actual).__name__}"
        for key, exp_val in expected.items():
            if key in ign:
                continue
            if key not in actual:
                if strict_keys:
                    raise AssertionError(f"{path} : clé manquante {key!r} (clés présentes : {sorted(actual)})")
                continue
            assert_matches(actual[key], exp_val, rel, abs_, ignore, f"{path}.{key}", strict_keys)
        return

    if isinstance(expected, list):
        if isinstance(actual, dict) and len(expected) == 1:
            actual = [actual]
        if len(expected) == 0:
            if actual is None:
                return
            n = actual.size if isinstance(actual, np.ndarray) else len(actual)
            assert n == 0, f"{path} : vide attendu, obtenu {n} élément(s)"
            return
        if all(_is_number(x) or isinstance(x, bool) or isinstance(x, list) for x in expected) and not any(
            isinstance(x, dict) for x in expected
        ):
            try:
                exp_arr = np.asarray(expected, dtype=float)
            except (TypeError, ValueError):
                exp_arr = None
            if exp_arr is not None:
                _assert_array(np.asarray(actual, dtype=float), expected, rel, abs_, path)
                return
        act_list = list(actual)
        assert len(act_list) == len(expected), f"{path} : {len(expected)} éléments attendus, {len(act_list)} obtenus"
        for i, (a, e) in enumerate(zip(act_list, expected)):
            assert_matches(a, e, rel, abs_, ignore, f"{path}[{i}]", strict_keys)
        return

    if isinstance(expected, bool):
        a = actual
        if isinstance(a, np.ndarray):
            a = a.reshape(-1)[0] if a.size == 1 else a
        assert bool(a) == expected, f"{path} : {expected} attendu, obtenu {actual!r}"
        return

    if _is_number(expected):
        a = actual
        if isinstance(a, (list, tuple, np.ndarray)):
            arr = np.asarray(a, dtype=float).reshape(-1)
            assert arr.size == 1, f"{path} : scalaire attendu, obtenu un tableau de taille {arr.size}"
            a = arr[0]
        assert _is_number(a) or isinstance(a, bool), f"{path} : nombre attendu, obtenu {a!r}"
        assert _close(float(a), float(expected), rel, abs_), f"{path} : {expected!r} attendu, obtenu {a!r}"
        return

    if isinstance(expected, str):
        if expected.startswith("<"):
            return
        assert str(actual) == expected, f"{path} : {expected!r} attendu, obtenu {actual!r}"
        return

    if expected is None:
        return

    raise AssertionError(f"{path} : type attendu non géré {type(expected).__name__}")


def _assert_array(actual: np.ndarray, expected: Any, rel: float, abs_: float, path: str) -> None:
    exp = np.asarray(expected, dtype=float)
    act = np.asarray(actual, dtype=float)
    if exp.size == act.size and exp.shape != act.shape:
        act = act.reshape(exp.shape)  # vecteur ligne / colonne
    assert act.shape == exp.shape, f"{path} : forme {exp.shape} attendue, obtenue {act.shape}"
    nan_e = np.isnan(exp)
    assert np.array_equal(nan_e, np.isnan(act)), f"{path} : positions des NaN différentes"
    ok = np.isclose(act, exp, rtol=rel, atol=abs_, equal_nan=True)
    if not ok.all():
        idx = np.argwhere(~ok)[0]
        i = tuple(idx)
        raise AssertionError(f"{path}{list(i)} : {exp[i]!r} attendu, obtenu {act[i]!r} (rel={rel})")
