"""Mode « Ossature 3D » de la page Poutres : saisie en tableaux, vue 3D, résultats du moteur frame3d.

Saisie en mm, N, N·m et N/m ; conversion en SI (m) avant l'appel à frame3d.solveFrame3D. Clés de widgets « p3d. ».
"""

import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from mecastruct.core import frame3d
from mecastruct.core.errors import MecaStructError
from mecastruct.ui import widgets

APPUIS = ["libre", "encastrement", "rotule", "appui_z", "perso"]
LIAISONS = ["rigide", "articulee"]
SECTIONS = ["catalogue", "rond", "tube", "rectangle", "perso"]
COMPOSANTES = [("N", "N"), ("Vy", "N"), ("Vz", "N"), ("T", "N·m"), ("My", "N·m"), ("Mz", "N·m")]
# exemples de saisie de la colonne « Dimensions », par type de section (mm, mm², mm⁴, mm³)
EXEMPLES_DIM = {
    "catalogue": "IPE 200",
    "rond": "d=40",
    "tube": "D=100; t=5",
    "rectangle": "b=30; h=60",
    "perso": "A=2848; Iy=1.943e7; Iz=1.424e6; J=7e4; Wy=1.943e5; Wz=2.847e4; Wt=8e3",
}
TABLES = ("noeuds", "pieces", "charges_nodales", "charges_reparties")
C_STRUCTURE, C_DEFORMEE, C_APPUI, C_CHARGE = "#1E1B2E", "#6E56CF", "#009E73", "#E69F00"


def _nombre(label: str, **kw) -> st.column_config.NumberColumn:
    return st.column_config.NumberColumn(label, format="%.6g", default=0.0, **kw)


def _id(label: str) -> st.column_config.NumberColumn:
    return st.column_config.NumberColumn(label, format="%d", step=1, required=True)


def _colonnes(dm) -> dict[str, dict]:
    """column_config des quatre tableaux de saisie."""
    return {
        "noeuds": {
            "id": _id("id"),
            "x": _nombre("x (mm)"),
            "y": _nombre("y (mm)"),
            "z": _nombre("z (mm)"),
            "appui": st.column_config.SelectboxColumn("Appui", options=APPUIS, default="libre", required=True),
            "ddl": st.column_config.TextColumn(
                "DDL perso", default="", help="Appui « perso » : 6 chiffres 0/1 pour ux uy uz θx θy θz (1 = bloqué)."
            ),
        },
        "pieces": {
            "id": _id("id"),
            "debut": _id("Nœud début"),
            "fin": _id("Nœud fin"),
            "materiau": st.column_config.SelectboxColumn(
                "Matériau", options=dm.listMaterials(), default="S235", required=True
            ),
            "section": st.column_config.SelectboxColumn("Section", options=SECTIONS, default="rond", required=True),
            "dimensions": st.column_config.TextColumn(
                "Dimensions (mm)",
                default="d=40",
                help="Exemples : " + " ; ".join(f"{k} : « {v} »" for k, v in EXEMPLES_DIM.items()),
            ),
            "beta": _nombre("β (°)"),
            "liaison_debut": st.column_config.SelectboxColumn(
                "Liaison début", options=LIAISONS, default="rigide", required=True
            ),
            "liaison_fin": st.column_config.SelectboxColumn(
                "Liaison fin", options=LIAISONS, default="rigide", required=True
            ),
        },
        "charges_nodales": {
            "noeud": _id("Nœud"),
            **{c: _nombre(f"{c} (N)") for c in ("Fx", "Fy", "Fz")},
            **{c: _nombre(f"{c} (N·m)") for c in ("Mx", "My", "Mz")},
        },
        "charges_reparties": {"piece": _id("Pièce"), **{c: _nombre(f"{c} (N/m)") for c in ("qx", "qy", "qz")}},
    }


# ------------------------------------------------------------------ exemples → tableaux


def _perso(e: dict) -> str:
    """Section d'un exemple en saisie « perso » (mm², mm⁴, mm³)."""
    echelles = {"A": 1e6, "Iy": 1e12, "Iz": 1e12, "J": 1e12, "Wy": 1e9, "Wz": 1e9, "Wt": 1e9}
    return "; ".join(f"{k}={e[k] * f:.6g}" for k, f in echelles.items() if e.get(k) is not None)


def _tables_exemple(nom: str, dm) -> dict[str, pd.DataFrame]:
    """Les quatre tableaux de saisie remplis avec l'exemple `nom` de frame3d.exemples()."""
    d = frame3d.exemples()[nom]
    mat = dm.getMaterial("S235")["Name"]  # matériau des exemples de frame3d
    noeuds = [
        {
            "id": n["id"],
            **{c: n[c] * 1e3 for c in "xyz"},
            "appui": n.get("appui", "libre"),
            "ddl": "",
        }
        for n in d["noeuds"]
    ]
    pieces = [
        {
            "id": e["id"],
            "debut": e["ni"],
            "fin": e["nj"],
            "materiau": mat,
            "section": "perso",
            "dimensions": _perso(e),
            "beta": e.get("beta_deg", 0.0),
            "liaison_debut": e.get("liaison_i", "rigide"),
            "liaison_fin": e.get("liaison_j", "rigide"),
        }
        for e in d["elements"]
    ]
    nod = [
        {"noeud": c["noeud"], **{f: c.get(f, 0.0) for f in ("Fx", "Fy", "Fz", "Mx", "My", "Mz")}}
        for c in d.get("charges_nodales", [])
    ]
    rep = [
        {"piece": c["element"], **{f: c.get(f, 0.0) for f in ("qx", "qy", "qz")}}
        for c in d.get("charges_reparties", [])
    ]
    cols = _colonnes(dm)
    t = {"noeuds": noeuds, "pieces": pieces, "charges_nodales": nod, "charges_reparties": rep}
    return {k: pd.DataFrame(v, columns=list(cols[k])) for k, v in t.items()}


def _charge_exemple() -> None:
    """Callback du choix d'exemple : remplace les tableaux, la case poids propre, et efface le résultat."""
    nom = st.session_state["p3d.exemple"]
    for k, df in _tables_exemple(nom, st.session_state["dm"]).items():
        st.session_state[f"p3d.src.{k}"] = df
        st.session_state.pop(f"p3d.{k}", None)  # l'éditeur repart du nouveau tableau
    st.session_state["p3d.pp"] = bool(frame3d.exemples()[nom].get("poids_propre", False))
    st.session_state.pop("p3d.res", None)


# ------------------------------------------------------------------ tableaux → données du moteur


def _lignes(df: pd.DataFrame, cle: str) -> list[dict]:
    """Lignes du tableau sans les lignes vides (identifiant `cle` absent)."""
    return [r for r in df.to_dict("records") if r.get(cle) is not None and not pd.isna(r.get(cle))]


def _f(v) -> float:
    """Case numérique : vide → 0."""
    return 0.0 if v is None or pd.isna(v) else float(v)


def _dims(txt, quoi: str) -> dict[str, float]:
    """« d=40; t=5 » → {d: 40, t: 5} (virgule décimale acceptée). Erreur : ValueError en français."""
    out = {}
    for morceau in str(txt or "").split(";"):
        if not morceau.strip():
            continue
        k, sep, v = morceau.partition("=")
        if not sep:
            raise ValueError(f"{quoi} : « {morceau.strip()} » doit être de la forme nom=valeur.")
        try:
            out[k.strip()] = float(v.strip().replace(",", "."))
        except ValueError:
            raise ValueError(f"{quoi} : valeur « {v.strip()} » invalide pour {k.strip()}.") from None
    return out


def _proprietes(p: dict, dm) -> dict:
    """Propriétés SI (A, Iy, Iz, J, Wy, Wz, Wt) d'une pièce à partir de son type de section et de ses dimensions."""
    quoi, sec = f"Pièce {int(p['id'])}", p.get("section")
    if sec == "catalogue":
        fam, _, taille = str(p.get("dimensions") or "").strip().partition(" ")
        try:
            return frame3d._profil(dm, fam, taille.strip())
        except MecaStructError as err:
            raise ValueError(f"{quoi} : {err.message} (exemple : « IPE 200 »).") from None
    d = _dims(p.get("dimensions"), quoi)

    def mm(k: str) -> float:
        if k not in d:
            raise ValueError(f"{quoi} : dimension « {k} » manquante (exemple : « {EXEMPLES_DIM[sec]} »).")
        return d[k] / 1e3

    if sec == "rond":
        return frame3d.sectionRond(mm("d"))
    if sec == "tube":
        return frame3d.sectionTube(mm("D"), mm("t"))
    if sec == "rectangle":
        return frame3d.sectionRectangle(mm("b"), mm("h"))
    if sec == "perso":
        for k in ("A", "Iy", "Iz", "J"):
            mm(k)
        puissance = {"A": 2, "Iy": 4, "Iz": 4, "J": 4, "Wy": 3, "Wz": 3, "Wt": 3}
        return {k: v / 1e3 ** puissance[k] for k, v in d.items() if k in puissance}
    raise ValueError(f"{quoi} : type de section « {sec} » inconnu.")


def _appui(n: dict) -> str | list[bool]:
    """Appui d'un nœud pour le moteur ; « perso » : 6 chiffres 0/1 de la colonne DDL perso."""
    if n.get("appui") != "perso":
        return n.get("appui") or "libre"
    ddl = str(n.get("ddl") or "").replace(" ", "")
    if len(ddl) != 6 or set(ddl) - {"0", "1"}:
        raise ValueError(f"Nœud {int(n['id'])} : appui perso, la colonne DDL perso doit contenir 6 chiffres 0/1.")
    return [c == "1" for c in ddl]


def _donnees(tables: dict[str, pd.DataFrame], poids_propre: bool, dm) -> dict:
    """Données de frame3d.solveFrame3D (SI) à partir des tableaux de saisie."""
    noeuds = [
        {"id": int(n["id"]), **{c: _f(n[c]) / 1e3 for c in "xyz"}, "appui": _appui(n)}
        for n in _lignes(tables["noeuds"], "id")
    ]
    elements = []
    for p in _lignes(tables["pieces"], "id"):
        mat = dm.getMaterial(p.get("materiau") or "S235")
        if not all(math.isfinite(mat[k]) for k in ("E", "G")):
            raise ValueError(f"Pièce {int(p['id'])} : E ou G inconnu pour le matériau « {mat['Name']} ».")
        elements.append(
            {
                "id": int(p["id"]),
                "ni": None if pd.isna(p.get("debut")) else int(p["debut"]),
                "nj": None if pd.isna(p.get("fin")) else int(p["fin"]),
                "E": mat["E"],
                "G": mat["G"],
                "rho": mat["rho"] if math.isfinite(mat["rho"]) else 0.0,
                **_proprietes(p, dm),
                "beta_deg": _f(p.get("beta")),
                "liaison_i": p.get("liaison_debut") or "rigide",
                "liaison_j": p.get("liaison_fin") or "rigide",
            }
        )
    nod = [
        {"noeud": int(c["noeud"]), **{f: _f(c.get(f)) for f in ("Fx", "Fy", "Fz", "Mx", "My", "Mz")}}
        for c in _lignes(tables["charges_nodales"], "noeud")
    ]
    rep = [
        {"element": int(c["piece"]), **{f: _f(c.get(f)) for f in ("qx", "qy", "qz")}}
        for c in _lignes(tables["charges_reparties"], "piece")
    ]
    return {
        "noeuds": noeuds,
        "elements": elements,
        "charges_nodales": nod,
        "charges_reparties": rep,
        "poids_propre": poids_propre,
    }


# ------------------------------------------------------------------ vue 3D


def _amplification_auto(res: dict, data: dict) -> int:
    """Amplification telle que le déplacement maximal vaille 10 % de la plus grande dimension (entre 1 et 1000)."""
    xyz = np.array([[n[c] for c in "xyz"] for n in data["noeuds"]])
    dim = float(np.max(np.ptp(xyz, axis=0))) if len(xyz) else 0.0
    umax = res["deplacement_max"]["valeur"]
    return int(min(1000, max(1, round(0.1 * dim / umax)))) if umax > 0 and dim > 0 else 1


def _vue_3d(res: dict, data: dict, ampli: float) -> go.Figure:
    """Structure initiale, déformée amplifiée, nœuds numérotés, appuis et charges nodales (mm)."""
    ids = [n["id"] for n in data["noeuds"]]
    P = {n["id"]: np.array([n[c] for c in "xyz"]) * 1e3 for n in data["noeuds"]}
    D = {i: P[i] + ampli * np.array(res["deplacements"][i][:3]) * 1e3 for i in ids}
    fig = go.Figure()
    # shortcut: déformée tracée en segments droits entre nœuds déplacés ; découper les pièces pour une courbe plus fine
    for pos, nom, style in ((P, "Structure", {"color": C_STRUCTURE, "width": 5}), (D, f"Déformée (×{ampli:g})", None)):
        x, y, z = [], [], []
        for e in data["elements"]:
            for k, v in enumerate(np.c_[pos[e["ni"]], pos[e["nj"]], [np.nan] * 3]):
                (x, y, z)[k].extend(v)
        line = style or {"color": C_DEFORMEE, "width": 4, "dash": "dash"}
        fig.add_trace(go.Scatter3d(x=x, y=y, z=z, mode="lines", name=nom, line=line, hoverinfo="skip"))
    xyz = np.array([P[i] for i in ids])
    fig.add_trace(
        go.Scatter3d(
            x=xyz[:, 0],
            y=xyz[:, 1],
            z=xyz[:, 2],
            mode="markers+text",
            text=[str(i) for i in ids],
            textposition="top center",
            marker={"size": 3, "color": C_STRUCTURE},
            name="Nœuds",
        )
    )
    appuis = [i for i in ids if i in res["reactions"]]
    if appuis:
        a = np.array([P[i] for i in appuis])
        fig.add_trace(
            go.Scatter3d(
                x=a[:, 0],
                y=a[:, 1],
                z=a[:, 2],
                mode="markers",
                marker={"size": 8, "symbol": "square", "color": C_APPUI},
                name="Appuis",
            )
        )
    charges = [c for c in data["charges_nodales"] if any(c[f] for f in ("Fx", "Fy", "Fz"))]
    if charges:
        dim = float(np.max(np.ptp(xyz, axis=0))) or 1000.0
        pos = np.array([P[c["noeud"]] for c in charges])
        f = np.array([[c["Fx"], c["Fy"], c["Fz"]] for c in charges])
        f = f / np.linalg.norm(f, axis=1)[:, None]
        fig.add_trace(
            go.Cone(
                x=pos[:, 0],
                y=pos[:, 1],
                z=pos[:, 2],
                u=f[:, 0],
                v=f[:, 1],
                w=f[:, 2],
                anchor="tip",
                sizemode="absolute",
                sizeref=0.08 * dim,
                colorscale=[[0, C_CHARGE], [1, C_CHARGE]],
                showscale=False,
                name="Charges nodales",
                hovertext=[f"F = ({c['Fx']:g} ; {c['Fy']:g} ; {c['Fz']:g}) N" for c in charges],
            )
        )
    fig.update_layout(
        height=400 if widgets.is_compact() else 550,
        margin={"l": 0, "r": 0, "t": 10, "b": 0},
        scene={
            "aspectmode": "data",
            "xaxis": {"title": {"text": "X (mm)"}},
            "yaxis": {"title": {"text": "Y (mm)"}},
            "zaxis": {"title": {"text": "Z (mm)"}},
        },
        legend={"orientation": "h", "y": 1.02, "x": 0},
    )
    return fig


# ------------------------------------------------------------------ résultats


def _table_deplacements(res: dict) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"Nœud": i, **{f"u{c} (mm)": v * 1e3 for c, v in zip("xyz", u[:3], strict=True)}}
            | {f"θ{c} (mrad)": v * 1e3 for c, v in zip("xyz", u[3:], strict=True)}
            for i, u in res["deplacements"].items()
        ]
    )


def _table_reactions(res: dict) -> pd.DataFrame:
    noms = ["Rx (N)", "Ry (N)", "Rz (N)", "Mx (N·m)", "My (N·m)", "Mz (N·m)"]
    return pd.DataFrame([{"Nœud": i, **dict(zip(noms, r, strict=True))} for i, r in res["reactions"].items()])


def _table_contraintes(res: dict) -> pd.DataFrame:
    def mpa(v):
        return None if v is None else v / 1e6

    return pd.DataFrame(
        [
            {"Pièce": i, "σmax (MPa)": mpa(c["sigma_max"]), "τ torsion (MPa)": mpa(c["tau_torsion"])}
            for i, c in res["contraintes"].items()
        ]
    )


def _csv(res: dict) -> bytes:
    """Tableaux de résultats à la suite, séparés par une ligne de titre (UTF-8 avec BOM pour Excel)."""
    parties = [
        ("Déplacements", _table_deplacements(res)),
        ("Réactions", _table_reactions(res)),
        ("Contraintes", _table_contraintes(res)),
    ]
    return "\n".join(f"# {titre}\n{df.to_csv(index=False)}" for titre, df in parties).encode("utf-8-sig")


def _synthese(res: dict) -> None:
    sig = [c["sigma_max"] for c in res["contraintes"].values() if c["sigma_max"] is not None]
    dm = res["deplacement_max"]
    widgets.synthese(
        [
            {"label": "Déplacement max", "value": f"{dm['valeur'] * 1e3:.4g} mm", "help": f"Nœud {dm['noeud']}"},
            {"label": "σmax", "value": f"{max(sig) / 1e6:.4g} MPa" if sig else "non calculée"},
        ]
    )
    eq = res["equilibre"]
    if eq["ok"]:
        widgets.status("Équilibre global vérifié (réactions + charges = 0).", True)
    else:
        widgets.status(
            f"Écart d'équilibre : ΣF = {np.round(eq['forces'], 6).tolist()} N, "
            f"ΣM = {np.round(eq['moments'], 6).tolist()} N·m.",
            False,
        )


def _efforts(res: dict) -> None:
    piece = st.selectbox("Pièce", list(res["efforts"]), key="p3d.piece")
    ef = res["efforts"][piece]
    s = np.array(ef["s"]) * 1e3
    cols = st.columns(1 if widgets.is_compact() else 2)
    for k, (c, unite) in enumerate(COMPOSANTES):
        fig = go.Figure(go.Scatter(x=s, y=ef[c], mode="lines", fill="tozeroy", line={"color": C_DEFORMEE}))
        fig.update_layout(
            title={"text": f"{c} ({unite})"},
            height=260,
            margin={"l": 50, "r": 10, "t": 40, "b": 40},
            xaxis_title="s (mm)",
            showlegend=False,
        )
        with cols[k % len(cols)]:
            widgets.plot(fig, key=f"p3d.g.{c}")


def _equations(res: dict) -> None:
    widgets.formulas(res["latex"])
    widgets.report(res["rapport"])


def _resultats(res: dict, data: dict) -> None:
    if "p3d.ampli" not in st.session_state:
        st.session_state["p3d.ampli"] = _amplification_auto(res, data)
    ampli = st.slider("Amplification", 1, 1000, key="p3d.ampli")
    widgets.plot(_vue_3d(res, data, ampli), key="p3d.vue")
    widgets.tabs(
        [
            ("Synthèse", lambda: _synthese(res)),
            ("Déplacements", lambda: st.dataframe(_table_deplacements(res), hide_index=True)),
            ("Réactions", lambda: st.dataframe(_table_reactions(res), hide_index=True)),
            ("Efforts internes", lambda: _efforts(res)),
            ("Contraintes", lambda: st.dataframe(_table_contraintes(res), hide_index=True)),
            ("Équations", lambda: _equations(res)),
        ]
    )
    st.download_button(
        "Exporter les résultats (CSV)",
        data=_csv(res),
        file_name="ossature_3d.csv",
        mime="text/csv",
        key="p3d.csv",
    )


# ------------------------------------------------------------------ page


def page_ossature_3d() -> None:
    """Mode « Ossature 3D » : tableaux de saisie, bouton Calculer, vue 3D et onglets de résultats."""
    dm = st.session_state["dm"]
    noms = list(frame3d.exemples())
    if "p3d.src.noeuds" not in st.session_state:
        st.session_state["p3d.exemple"] = st.session_state.get("p3d.exemple", noms[0])
        _charge_exemple()
    gauche, droite = widgets.zones("p3d")
    with gauche:
        st.selectbox("Exemple", noms, key="p3d.exemple", on_change=_charge_exemple)
        cols = _colonnes(dm)
        tables = {}
        for k, titre in zip(
            TABLES,
            ("Nœuds", "Pièces", "Charges nodales (repère global)", "Charges réparties (repère global)"),
            strict=True,
        ):
            st.markdown(f"**{titre}**")
            tables[k] = st.data_editor(
                st.session_state[f"p3d.src.{k}"],
                num_rows="dynamic",
                column_config=cols[k],
                key=f"p3d.{k}",
                hide_index=True,
            )
        pp = st.checkbox("Poids propre", key="p3d.pp", help="ρ·g·A selon -Z, g = 9,81 m/s².")
        if widgets.calc_button("p3d"):
            st.session_state.pop("p3d.res", None)
            try:
                data = _donnees(tables, pp, dm)
                res = frame3d.solveFrame3D(data)
                res.pop("K", None)  # 11 Mo pour 200 nœuds, inutile à la page : pas gardé en session
            except (ValueError, frame3d.FrameMechanismError) as err:
                st.error(str(err))
            else:
                st.session_state["p3d.res"] = {"res": res, "data": data}
                st.session_state["p3d.ampli"] = _amplification_auto(res, data)
        st.caption(
            "Poutres d'Euler-Bernoulli (déformation d'effort tranchant négligée). Repère local : x de début vers fin, "
            "z vertical pour une pièce horizontale (Iy = axe fort). β tourne la section autour de son axe."
        )
    with droite:
        if "p3d.res" in st.session_state:
            _resultats(st.session_state["p3d.res"]["res"], st.session_state["p3d.res"]["data"])
        else:
            st.info("Choisissez un exemple ou remplissez les tableaux, puis cliquez sur « Calculer ».")
