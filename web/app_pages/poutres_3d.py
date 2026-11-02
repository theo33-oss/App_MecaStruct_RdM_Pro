"""Mode « Ossature 3D » de la page Poutres : saisie en tableaux, vue 3D, résultats du moteur frame3d.

Saisie en mm, N, N·m et N/m ; conversion en SI (m) avant l'appel à frame3d.solveFrame3D. Clés de widgets « p3d. ».
"""

import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app_pages.exemples_3d import EXPLICATIONS, exemples
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
# repère global dessiné à l'origine : X rouge, Y vert, Z bleu (convention des logiciels de CAO)
C_AXES = {"X": "#D55E00", "Y": "#009E73", "Z": "#0072B2"}


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
    """Les quatre tableaux de saisie remplis avec l'exemple `nom` (voir exemples_3d.exemples)."""
    d = exemples(dm)[nom]
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
    st.session_state["p3d.pp"] = bool(exemples(st.session_state["dm"])[nom].get("poids_propre", False))
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
                "Re": mat["Re"],  # pour comparer σ à la limite élastique ; ignorée par le solveur
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
    dim = float(np.max(np.ptp(xyz, axis=0))) or 1000.0
    charges = [c for c in data["charges_nodales"] if any(c[f] for f in ("Fx", "Fy", "Fz"))]
    if charges:
        pos = np.array([P[c["noeud"]] for c in charges])
        f = np.array([[c["Fx"], c["Fy"], c["Fz"]] for c in charges])
        f = 0.12 * dim * f / np.linalg.norm(f, axis=1)[:, None]  # flèche de 12 % de la structure, en mm
        fig.add_trace(
            go.Cone(
                x=pos[:, 0],
                y=pos[:, 1],
                z=pos[:, 2],
                u=f[:, 0],
                v=f[:, 1],
                w=f[:, 2],
                anchor="tip",
                sizemode="raw",  # « absolute » gonflait les cônes à des millions de mm et écrasait la structure
                colorscale=[[0, C_CHARGE], [1, C_CHARGE]],
                showscale=False,
                name="Charges nodales",
                hovertext=[f"F = ({c['Fx']:g} ; {c['Fy']:g} ; {c['Fz']:g}) N" for c in charges],
            )
        )
    # cube de même échelle sur les trois axes : « aspectmode=data » écrase un axe vide (console plane, treillis plan)
    long_axe = 0.15 * dim
    for k, (nom, couleur) in enumerate(C_AXES.items()):
        bout = np.zeros(3)
        bout[k] = long_axe
        fig.add_trace(
            go.Scatter3d(
                x=[0, bout[0]],
                y=[0, bout[1]],
                z=[0, bout[2]],
                mode="lines+text",
                line={"color": couleur, "width": 6},
                text=["", nom],
                textfont={"color": couleur, "size": 14},
                textposition="middle right",
                name="Repère (0, 0, 0)",
                legendgroup="repere",
                showlegend=k == 0,
                hoverinfo="skip",
            )
        )
    tout = np.vstack([xyz, *D.values(), np.zeros(3), np.eye(3) * long_axe])  # le repère reste dans le cadre
    centre, demi = (tout.min(axis=0) + tout.max(axis=0)) / 2, 0.65 * max(float(np.max(np.ptp(tout, axis=0))), dim)
    fig.update_layout(
        height=400 if widgets.is_compact() else 550,
        margin={"l": 0, "r": 0, "t": 10, "b": 0},
        scene={
            "aspectmode": "cube",
            **{
                f"{a}axis": {"title": {"text": f"{a.upper()} (mm)"}, "range": [c - demi, c + demi]}
                for a, c in zip("xyz", centre, strict=True)
            },
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


def _terme(v: float) -> str:
    """Valeur en kN ou kN·m d'un terme de somme LaTeX, entre parenthèses si négative."""
    x = 0.0 if abs(v) < 1e-9 else v / 1e3  # résidu d'arrondi : écrit 0
    return f"({x:.5g})" if x < 0 else f"{x:.5g}"


def _verification(res: dict, data: dict) -> None:
    """Vérification à la main : bilan des actions avec valeurs, puis contraintes comparées à Re."""
    v = frame3d.verificationAMain(data, res)
    b = v["bilan"]
    st.markdown(
        "**Équilibre global, refait à partir de vos données** : charges nodales + charges réparties (poids propre "
        "compris) + réactions du solveur = 0. Moments pris par rapport à l'origine (0, 0, 0)."
    )
    termes = (("charges nodales", "nodales"), ("charges réparties", r"r\'eparties"), ("réactions", r"r\'eactions"))
    for grandeur, cle, unite in (("F", "F", r"\mathrm{kN}"), ("M", "M", r"\mathrm{kN\cdot m}")):
        for i, axe in enumerate("xyz"):
            somme = " + ".join(
                r"\underbrace{" + _terme(b[nom][cle][i]) + r"}_{\text{" + leg + "}}" for nom, leg in termes
            )
            st.latex(rf"\sum {grandeur}_{axe}=" + somme + "=" + _terme(b["somme"][cle][i]) + rf"\ {unite}")
    st.caption(
        "Les sommes doivent être nulles (écart admis : 1e-6 de l'échelle des actions). "
        + ("Équilibre vérifié." if res["equilibre"]["ok"] else "ÉQUILIBRE NON VÉRIFIÉ : voir l'onglet Synthèse.")
    )
    st.markdown(
        "**Contraintes** : σ = |N|/A + |My|/Wy + |Mz|/Wz, maximum sur les 21 points de chaque pièce, comparée à la "
        "limite élastique Re du matériau (sans coefficient de sécurité). Les efforts viennent du solveur "
        "(onglet Efforts internes)."
    )
    re = {e["id"]: e.get("Re") for e in data["elements"]}
    lignes = []
    for c in v["contraintes"]:
        r = re.get(c["id"])
        ok = c["sigma"] is not None and r is not None and math.isfinite(r)
        lignes.append(
            {
                "Pièce": c["id"],
                "N max (kN)": c["N"] / 1e3,
                "My max (kN·m)": c["My"] / 1e3,
                "Mz max (kN·m)": c["Mz"] / 1e3,
                "A (mm²)": c["A"] * 1e6,
                "Wy (cm³)": None if c["Wy"] is None else c["Wy"] * 1e6,
                "Wz (cm³)": None if c["Wz"] is None else c["Wz"] * 1e6,
                "σ refait (MPa)": None if c["sigma"] is None else c["sigma"] / 1e6,
                "σ solveur (MPa)": None if c["solveur"] is None else c["solveur"] / 1e6,
                "Re (MPa)": r / 1e6 if ok else None,
                "σ/Re": c["sigma"] / r if ok else None,
            }
        )
    st.dataframe(pd.DataFrame(lignes), hide_index=True)
    if any(c["sigma"] is None for c in v["contraintes"]):
        st.caption("σ non calculée pour une pièce sans module de flexion Wy ou Wz : saisissez-les (section « perso »).")


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
            ("Vérification à la main", lambda: _verification(res, data)),
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


def _empreinte(tables: dict[str, pd.DataFrame], poids_propre: bool) -> str:
    """Empreinte de la saisie (4 tableaux + poids propre) : dit si un résultat date de la saisie actuelle."""
    return "|".join(tables[k].to_json() for k in TABLES) + str(poids_propre)


def _materiaux(pieces: pd.DataFrame, dm) -> None:
    """Caractéristiques des matériaux choisis dans le tableau des pièces (base de données du site)."""
    noms = sorted({str(m) for m in pieces.get("materiau", []) if isinstance(m, str) and m})
    lignes = []
    for nom in noms:
        m = dm.getMaterial(nom)
        lignes.append(
            {
                "Matériau": m["Name"],
                "E (GPa)": m["E"] / 1e9,
                "G (GPa)": m["G"] / 1e9,
                "ν": m["nu"],
                "ρ (kg/m³)": m["rho"],
                "Re (MPa)": m["Re"] / 1e6,
                "Rm (MPa)": m["Rm"] / 1e6,
            }
        )
    with st.expander(f"Matériaux utilisés ({len(lignes)})", icon=":material/science:"):
        st.dataframe(pd.DataFrame(lignes), hide_index=True)
        st.caption("Valeurs de la base de données du site (page Base de données). Changez le matériau dans « Pièces ».")


# ------------------------------------------------------------------ page


def page_ossature_3d() -> None:
    """Mode « Ossature 3D » : tableaux de saisie, bouton Calculer, vue 3D et onglets de résultats."""
    dm = st.session_state["dm"]
    noms = list(exemples(dm))
    if "p3d.src.noeuds" not in st.session_state:
        st.session_state["p3d.exemple"] = st.session_state.get("p3d.exemple", noms[0])
        _charge_exemple()
    gauche, droite = widgets.zones("p3d")
    with gauche:
        st.selectbox(
            "Exemple",
            noms,
            key="p3d.exemple",
            on_change=_charge_exemple,
            help="\n\n".join(f"**{n}** : {t}" for n, t in EXPLICATIONS.items()),
        )
        st.caption(EXPLICATIONS.get(st.session_state["p3d.exemple"], ""))
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
            if k == "pieces":
                _materiaux(tables[k], dm)
        pp = st.checkbox("Poids propre", key="p3d.pp", help="ρ·g·A selon -Z, g = 9,81 m/s².")
        if widgets.calc_button("p3d.calc"):
            st.session_state.pop("p3d.res", None)
            try:
                data = _donnees(tables, pp, dm)
                res = frame3d.solveFrame3D(data)
                res.pop("K", None)  # 11 Mo pour 200 nœuds, inutile à la page : pas gardé en session
            except (ValueError, frame3d.FrameMechanismError) as err:
                st.error(str(err))
            else:
                st.session_state["p3d.res"] = {"res": res, "data": data, "empreinte": _empreinte(tables, pp)}
                st.session_state["p3d.ampli"] = _amplification_auto(res, data)
        st.caption(
            "Poutres d'Euler-Bernoulli (déformation d'effort tranchant négligée). Repère local : x de début vers fin, "
            "z vertical pour une pièce horizontale (Iy = axe fort). β tourne la section autour de son axe."
        )
    with droite:
        if "p3d.res" in st.session_state:
            calcul = st.session_state["p3d.res"]
            if calcul["empreinte"] != _empreinte(tables, pp):
                st.warning(
                    "Saisie modifiée depuis le dernier calcul : la vue et les résultats ci-dessous sont ceux de "
                    "l'ancienne saisie. Cliquez sur « Calculer » pour les mettre à jour."
                )
            _resultats(calcul["res"], calcul["data"])
        else:
            st.info("Choisissez un exemple ou remplissez les tableaux, puis cliquez sur « Calculer ».")
