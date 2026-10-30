"""Petits outils partagés par les moteurs : données JSON, listes et tableaux, formatage des nombres."""

import copy
import functools
import json
import math
from pathlib import Path
from typing import Any

import numpy as np


def data_path(name: str) -> Path:
    """Chemin de `web/data/<name>`.

    Entrée : `name` (nom du fichier, ex. « units.json »).
    Sortie : Path absolu.
    """
    return Path(__file__).resolve().parents[2] / "data" / name


@functools.cache
def _read_json_cached(name: str) -> Any:
    with data_path(name).open(encoding="utf-8") as f:
        return json.load(f)


def load_json(name: str) -> Any:
    """Contenu JSON de `web/data/<name>`, en copie profonde pour ne pas modifier le cache.

    Entrée : `name` (nom du fichier dans web/data).
    Sortie : données Python (dict, list…).
    """
    return copy.deepcopy(_read_json_cached(name))


def as_list(x) -> list:
    """Force une valeur en liste : None → [], un dict seul → [dict], liste ou tuple → liste.

    Entrée : `x` (None, dict, list ou tuple, JSON MATLAB).
    Sortie : list.
    """
    if x is None:
        return []
    if isinstance(x, dict):
        return [x]
    return list(x)


def as_array(x) -> np.ndarray:
    """Force une valeur en tableau 1-D de réels ; None → tableau vide, un nombre seul → tableau d'un élément.

    Entrée : `x` (nombre, liste, tableau ou None).
    Sortie : np.ndarray de float.
    """
    if x is None:
        return np.zeros(0)
    return np.atleast_1d(np.asarray(x, dtype=float))


def fmt_fr(x: float, spec: str = ".4g") -> str:
    """Formate un nombre avec une virgule décimale ; NaN, Inf et -Inf écrits comme MATLAB.

    Entrées : `x` (réel, sans unité), `spec` (format Python, ex. ".4g").
    Sortie : texte, ex. "1,5".
    """
    if math.isnan(x):
        return "NaN"
    if math.isinf(x):
        return "Inf" if x > 0 else "-Inf"
    return format(x, spec).replace(".", ",")


def is_num(x) -> bool:
    """Vrai pour un nombre (int, float, numpy), NaN compris ; faux pour un booléen, None ou un texte.

    Entrée : `x` (valeur quelconque).
    Sortie : bool.
    """
    return isinstance(x, (int, float, np.integer, np.floating)) and not isinstance(x, bool)
