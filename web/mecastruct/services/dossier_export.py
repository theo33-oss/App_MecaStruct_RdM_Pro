"""Dossier de validation en PDF (reportlab) ou en Word (python-docx), à partir de son HTML.

Le HTML des dossiers (validation_report, machine_validation) est lu en blocs simples : titres, paragraphes,
tableaux. Les formules $…$ sont dessinées en images par mathtext de matplotlib ; une formule que mathtext ne sait pas
lire (matrices, array) reste en LaTeX brut. Les diagrammes Plotly (JavaScript) ne sont pas repris : le PDF et le Word
renvoient à la version HTML. Aucun import de streamlit.
"""

import base64
import functools
import io
import re
import threading
from html.parser import HTMLParser
from pathlib import Path
from xml.sax.saxutils import escape

FORMATS = {
    "HTML": (".html", "text/html"),
    "PDF": (".pdf", "application/pdf"),
    "Word": (".docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
}

_DPI = 200
_VERROU = threading.Lock()  # mathtext passe par une figure matplotlib : un dessin à la fois
_VIDES = {"br", "img", "meta", "link", "hr", "input", "col", "area", "base", "source", "wbr"}
_BLOCS = {"h1", "h2", "h3", "p", "div", "li", "details", "ol", "ul", "table", "main", "body", "nav"}
_COULEURS = {"ok": "1d7a3a", "ko": "b3261e", "warn": "9a6a00"}
_NOTE_FIG = "Diagramme interactif non repris ici : voir la version HTML du dossier."

# ------------------------------------------------------------------------------------------------- lecture


class _Lecteur(HTMLParser):
    """HTML d'un dossier -> blocs : ("titre", niveau, runs), ("para", runs, classe), ("table", lignes, classe).

    Run : (texte, style) avec style "", "b", "ok", "ko", "warn", "mono" ou "math" (texte = LaTeX). Ligne de tableau :
    liste de cellules (runs, entête, colspan, classe).
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocs: list[tuple] = []
        self.runs: list[tuple[str, str]] = []
        self.classe = ""  # classe du bloc en cours (div.eq, p.muted, div.rln…)
        self.styles: list[str] = []
        self.saut = 0  # profondeur d'un sous-arbre ignoré (script, style, sommaire, diagramme…)
        self.table: tuple | None = None
        self.cellule: list | None = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get("class") or ""
        if self.saut:
            self.saut += tag not in _VIDES
            return
        ignore = tag in ("script", "style", "title", "nav", "summary") or "display:none" in (a.get("style") or "")
        if ignore or (tag == "a" and cls == "top") or cls == "fig":
            if cls == "fig":
                self._vide()
                self.blocs.append(("para", [(_NOTE_FIG, "")], "muted"))
            self.saut = 1
            return
        if tag in ("td", "th"):
            self.cellule = [[], tag == "th", int(a.get("colspan", 1)), cls]
        elif tag == "tr" and self.table is not None:
            self.table[1].append([])
        elif tag == "table":
            self._vide()
            self.table = ("table", [], cls)
        elif tag in _BLOCS or tag in ("h1", "h2", "h3"):
            self._vide()
            self.classe = tag if tag in ("h1", "h2", "h3") else cls
            if cls == "comment":
                self.blocs.append(("cadre",))
        elif tag == "br":
            self._ajoute("\n")
        elif tag in ("strong", "b"):
            self.styles.append("b")
        elif tag == "span":
            self.styles.append(cls if cls in _COULEURS else "")

    def handle_endtag(self, tag):
        if self.saut:
            self.saut -= tag not in _VIDES
            return
        if tag in ("td", "th") and self.cellule is not None and self.table is not None:
            runs, entete, span, cls = self.cellule
            if self.table[1]:
                self.table[1][-1].append((_maths(runs), entete, span, cls))
            self.cellule = None
        elif tag == "table" and self.table is not None:
            self.blocs.append(self.table)
            self.table = None
        elif tag in _BLOCS or tag in ("h1", "h2", "h3"):
            self._vide()
            self.classe = ""
        elif tag in ("strong", "b", "span") and self.styles:
            self.styles.pop()

    def handle_data(self, data):
        if not self.saut:
            self._ajoute(data)

    def _ajoute(self, texte: str) -> None:
        style = next((s for s in reversed(self.styles) if s), "")
        if self.classe == "rln":
            style = style or "mono"
        cible = self.cellule[0] if self.cellule is not None else self.runs
        cible.append((texte, style))

    def _vide(self) -> None:
        """Termine le paragraphe en cours (texte hors tableau)."""
        runs = _maths(self.runs)
        self.runs = []
        if not any(t.strip() for t, _ in runs):
            return
        if self.classe in ("h1", "h2", "h3"):
            self.blocs.append(("titre", int(self.classe[1]), runs))
        else:
            self.blocs.append(("para", runs, self.classe))


def _maths(runs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Espaces regroupés, puis chaque $…$ isolé en run « math »."""
    out = []
    for texte, style in runs:
        if texte == "\n":
            out.append((texte, style))
            continue
        if style != "mono":
            texte = re.sub(r"\s+", " ", texte)
        for i, morceau in enumerate(re.split(r"\$([^$]+)\$", texte)):
            if morceau:
                out.append((morceau.strip(), "math") if i % 2 else (morceau, style))
    while out and not out[0][0].strip():
        out.pop(0)
    while out and not out[-1][0].strip():
        out.pop()
    if out and out[0][1] != "math":
        out[0] = (out[0][0].lstrip(), out[0][1])
    if out and out[-1][1] != "math":
        out[-1] = (out[-1][0].rstrip(), out[-1][1])
    return out


def _blocs(html: str) -> list[tuple]:
    lecteur = _Lecteur()
    lecteur.feed(html)
    lecteur.close()
    lecteur._vide()
    return lecteur.blocs


# ------------------------------------------------------------------------------------------------ formules


def _groupe(s: str, k: int) -> int:
    """Indice juste après l'accolade fermante du groupe qui s'ouvre en s[k] (fin de chaîne si non fermé)."""
    n = 0
    for i in range(k, len(s)):
        n += {"{": 1, "}": -1}.get(s[i], 0)
        if n == 0:
            return i + 1
    return len(s)


def _compatible(latex: str) -> str:
    r"""Réécrit les commandes que mathtext ne connaît pas : \tfrac, \le, \mbox, \Big, \underbrace{…}_{…}, \'e."""
    s = re.sub(r"\\[td]frac(?![a-zA-Z])", r"\\frac", latex)
    s = re.sub(r"\\frac(\d)(\d)", r"\\frac{\1}{\2}", s)
    s = re.sub(r"\\(le|ge)(?![a-zA-Z])", r"\\\1q", s)
    s = re.sub(r"\\(?:textrm|mbox)(?![a-zA-Z])", r"\\text", s)
    s = re.sub(r"\\[Bb]igg?[lr]?(?![a-zA-Z])", "", s)
    s = re.sub(r"\\'\{?e\}?", "é", s)
    while (i := s.find("\\underbrace{")) >= 0:  # garde le terme, retire l'accolade et sa légende
        j = _groupe(s, i + 11)
        reste = s[j:]
        if reste.startswith("_{"):
            reste = reste[_groupe(reste, 1) :]
        s = s[:i] + s[i + 11 : j] + reste
    return s


@functools.lru_cache(maxsize=4096)
def _image(latex: str) -> tuple[bytes, float, float] | None:
    """Formule dessinée par mathtext : (PNG, largeur en pt, hauteur en pt), None si mathtext ne sait pas la lire."""
    from matplotlib.font_manager import FontProperties
    from matplotlib.mathtext import math_to_image
    from PIL import Image

    buf = io.BytesIO()
    try:
        with _VERROU:
            math_to_image(f"${_compatible(latex)}$", buf, prop=FontProperties(size=10), dpi=_DPI, format="png")
    except Exception:
        return None
    w, h = Image.open(io.BytesIO(buf.getvalue())).size
    return buf.getvalue(), w * 72 / _DPI, h * 72 / _DPI


def _morceaux(latex: str) -> list[str]:
    r"""Formule coupée avant chaque « = » de premier niveau (hors accolades et \left … \right)."""
    out, n, debut, i = [], 0, 0, 0
    while i < len(latex):
        for cmd, d in (("\\left", 1), ("\\right", -1)):
            if latex.startswith(cmd, i) and not latex[i + len(cmd) : i + len(cmd) + 1].isalpha():
                n += d
                i += len(cmd) - 1
                break
        else:
            n += {"{": 1, "}": -1}.get(latex[i], 0)
            if latex[i] == "=" and n == 0 and i > debut:
                out.append(latex[debut:i])
                debut = i
        i += 1
    return [m.strip() for m in [*out, latex[debut:]] if m.strip()]


def _dessins(latex: str, maxi: float) -> list[tuple[bytes, float, float]] | None:
    """Images (PNG, largeur pt, hauteur pt) d'une formule tenant dans `maxi` pt de large ; None si illisible.

    Trop large, elle est coupée en lignes avant chaque « = », puis chaque ligne est réduite si besoin.
    """
    img = _image(latex)
    if img is None:
        return None
    lignes = [img]
    if img[1] > maxi and len(m := _morceaux(latex)) > 1 and None not in (parts := [_image(x) for x in m]):
        lignes = parts
    return [(png, w * min(1.0, maxi / w), h * min(1.0, maxi / w)) for png, w, h in lignes]


def _largeurs(classe: str, n: int, total: float) -> list[float]:
    """Largeurs des colonnes d'un tableau (mêmes proportions que la feuille de style du HTML)."""
    if classe == "hand" and n == 6:
        return [total * p for p in (0.17, 0.34, 0.14, 0.14, 0.08, 0.13)]
    if classe == "kv" and n == 2:
        return [total * 0.55, total * 0.45]
    return [total / n] * n


def _ncols(lignes: list) -> int:
    return max((sum(c[2] for c in ligne) for ligne in lignes), default=0)


# ----------------------------------------------------------------------------------------------------- PDF


def _polices() -> tuple[str, str, str]:
    """Polices DejaVu de matplotlib (lettres grecques, ≤, √, ☐) déclarées une fois auprès de reportlab."""
    import matplotlib
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    if "DejaVu" not in pdfmetrics.getRegisteredFontNames():
        d = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
        for nom, f in (("DejaVu", "DejaVuSans"), ("DejaVu-B", "DejaVuSans-Bold"), ("DejaVuMono", "DejaVuSansMono")):
            pdfmetrics.registerFont(TTFont(nom, str(d / f"{f}.ttf")))
        pdfmetrics.registerFontFamily(
            "DejaVu", normal="DejaVu", bold="DejaVu-B", italic="DejaVu", boldItalic="DejaVu-B"
        )
    return "DejaVu", "DejaVu-B", "DejaVuMono"


def _markup(runs: list[tuple[str, str]], maxi: float) -> str:
    """Texte d'un Paragraph reportlab : gras, couleurs, police à chasse fixe, formules en images."""
    h = ""
    for texte, style in runs:
        if texte == "\n":
            h += "<br/>"
        elif style == "math":
            dessins = _dessins(texte, maxi)
            if dessins is None:
                h += f'<font face="DejaVuMono">{escape(texte)}</font>'
            else:
                h += "<br/>".join(
                    f'<img src="data:image/png;base64,{base64.b64encode(png).decode()}" width="{w:.1f}" '
                    f'height="{ht:.1f}" valign="middle"/>'
                    for png, w, ht in dessins
                )
        elif style in _COULEURS:
            h += f'<font color="#{_COULEURS[style]}"><b>{escape(texte)}</b></font>'
        elif style == "b":
            h += f"<b>{escape(texte)}</b>"
        elif style == "mono":
            h += f'<font face="DejaVuMono">{escape(texte).replace(" ", "&nbsp;")}</font>'
        else:
            h += escape(texte)
    return h


def toPdf(html: str) -> bytes:
    """Dossier de validation en PDF (A4) : mêmes parties, tableaux et formules que le HTML, sans les diagrammes.

    Entrée : texte HTML d'un dossier. Sortie : octets du fichier PDF.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    normal, gras, mono = _polices()
    bleu = colors.HexColor("#14406e")
    # autoLeading : une ligne s'agrandit pour une formule plus haute que le texte (sinon les lignes se chevauchent)
    base = ParagraphStyle("base", fontName=normal, fontSize=9, leading=12, spaceAfter=4, autoLeading="max")
    styles = {
        "": base,
        "muted": ParagraphStyle("muted", parent=base, textColor=colors.HexColor("#5b6370")),
        "mono": ParagraphStyle("mono", parent=base, fontName=mono, fontSize=7.5, leading=9.5, spaceAfter=0),
        "rln": ParagraphStyle("rln", parent=base, fontName=mono, fontSize=7.5, leading=9.5, spaceAfter=0),
        "rsec": ParagraphStyle("rsec", parent=base, fontName=gras, textColor=bleu, spaceBefore=6),
        "eqtitle": ParagraphStyle("eqtitle", parent=base, fontName=gras, textColor=bleu, spaceAfter=1),
        "status": ParagraphStyle("status", parent=base, fontName=gras, fontSize=10.5, leading=14,
                                 backColor=colors.HexColor("#e8f1fb"), borderPadding=4, spaceBefore=4, spaceAfter=8),
        "warnbox": ParagraphStyle("warnbox", parent=base, backColor=colors.HexColor("#fff3d6"), borderPadding=4),
        "box": ParagraphStyle("box", parent=base, backColor=colors.HexColor("#f5f8fc"), borderPadding=4),
    }  # fmt: skip
    titres = {
        1: ParagraphStyle("h1", parent=base, fontName=gras, fontSize=16, leading=20, textColor=bleu, spaceAfter=6),
        2: ParagraphStyle("h2", parent=base, fontName=gras, fontSize=12, leading=16, textColor=colors.white,
                          backColor=bleu, borderPadding=3, spaceBefore=12, spaceAfter=8),
        3: ParagraphStyle("h3", parent=base, fontName=gras, fontSize=10.5, leading=14, textColor=bleu, spaceBefore=8),
    }  # fmt: skip
    cel = ParagraphStyle("cel", parent=base, fontSize=8, leading=10, spaceAfter=0)
    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm,
                            bottomMargin=15 * mm, title="Dossier de validation")  # fmt: skip
    largeur = doc.width
    histoire = []
    for b in _blocs(html):
        if b[0] == "titre":
            histoire.append(Paragraph(_markup(b[2], largeur), titres[b[1]]))
        elif b[0] == "para":
            histoire.append(Paragraph(_markup(b[1], largeur), styles.get(b[2], base)))
        elif b[0] == "cadre":
            t = Table([[""]], colWidths=[largeur], rowHeights=[25 * mm])
            t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, colors.grey)]))
            histoire.append(t)
        elif b[0] == "table" and b[1]:
            lignes, classe = [ligne for ligne in b[1] if ligne], b[2]
            n = _ncols(lignes)
            if n == 0:
                continue
            cw = _largeurs(classe, n, largeur)
            taille = 8 if n <= 6 else 6.5
            st_cel = ParagraphStyle("c", parent=cel, fontSize=taille, leading=taille * 1.25)
            st_ent = ParagraphStyle("e", parent=st_cel, fontName=gras)
            data, cmds = (
                [],
                [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9aa5b4")), ("VALIGN", (0, 0), (-1, -1), "TOP")],
            )
            for i, ligne in enumerate(lignes):
                rangee, j = [], 0
                for runs, entete, span, cls in ligne:
                    w = sum(cw[j : j + span]) - 6
                    rangee.append(Paragraph(_markup(runs, w), st_ent if entete or cls == "grp" else st_cel))
                    if span > 1:
                        cmds.append(("SPAN", (j, i), (j + span - 1, i)))
                        rangee += [""] * (span - 1)
                    if entete or cls == "grp":
                        cmds.append(("BACKGROUND", (j, i), (j + span - 1, i), colors.HexColor("#eef2f7")))
                    j += span
                data.append(rangee + [""] * (n - len(rangee)))
            entete = all(c[1] for c in lignes[0])
            t = Table(data, colWidths=cw, repeatRows=1 if entete else 0)
            t.setStyle(TableStyle(cmds))
            histoire += [t, Spacer(1, 6)]
    doc.build(histoire)
    return out.getvalue()


# ---------------------------------------------------------------------------------------------------- Word


def _runsWord(p, runs: list[tuple[str, str]], maxi_pt: float) -> None:
    """Ajoute les runs à un paragraphe python-docx (formules en images de largeur au plus `maxi_pt`)."""
    from docx.shared import Pt, RGBColor

    for texte, style in runs:
        if texte == "\n":
            p.add_run().add_break()
        elif style == "math":
            dessins = _dessins(texte, maxi_pt)
            if dessins is None:
                p.add_run(texte).font.name = "Consolas"
            for k, (png, w, _) in enumerate(dessins or []):
                if k:
                    p.add_run().add_break()
                p.add_run().add_picture(io.BytesIO(png), width=Pt(w))
        else:
            r = p.add_run(texte)
            r.bold = style in ("b", *_COULEURS)
            if style in _COULEURS:
                r.font.color.rgb = RGBColor.from_string(_COULEURS[style].upper())
            if style == "mono":
                r.font.name = "Consolas"
                r.font.size = Pt(8)


def _fond(cellule, couleur: str) -> None:
    """Couleur de fond d'une cellule Word (pas d'API python-docx : élément w:shd)."""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), couleur)
    cellule._tc.get_or_add_tcPr().append(shd)


def toDocx(html: str) -> bytes:
    """Dossier de validation en Word (.docx) : mêmes parties, tableaux et formules que le HTML, sans les diagrammes.

    Entrée : texte HTML d'un dossier. Sortie : octets du fichier .docx.
    """
    from docx import Document
    from docx.shared import Cm, Pt, RGBColor

    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.left_margin = sec.right_margin = sec.top_margin = sec.bottom_margin = Cm(1.5)
    doc.styles["Normal"].font.size = Pt(9.5)
    largeur = (sec.page_width - sec.left_margin - sec.right_margin) / 12700  # EMU -> pt
    for b in _blocs(html):
        if b[0] == "titre":
            p = doc.add_heading("", level=0 if b[1] == 1 else b[1] - 1)
            _runsWord(p, b[2], largeur)
        elif b[0] == "para":
            p = doc.add_paragraph()
            _runsWord(p, b[1], largeur)
            if b[2] in ("muted", "var"):
                for r in p.runs:
                    r.font.color.rgb = RGBColor(0x5B, 0x63, 0x70)
            elif b[2] in ("status", "eqtitle", "rsec"):
                for r in p.runs:
                    r.bold = True
        elif b[0] == "cadre":
            t = doc.add_table(rows=1, cols=1)
            t.style = "Table Grid"
            t.rows[0].height = Cm(2.5)
        elif b[0] == "table" and b[1]:
            lignes, classe = [ligne for ligne in b[1] if ligne], b[2]
            n = _ncols(lignes)
            if n == 0:
                continue
            cw = _largeurs(classe, n, largeur)
            t = doc.add_table(rows=len(lignes), cols=n)
            t.style = "Table Grid"
            for i, ligne in enumerate(lignes):
                j = 0
                for runs, entete, span, cls in ligne:
                    c = t.cell(i, j) if span == 1 else t.cell(i, j).merge(t.cell(i, min(j + span, n) - 1))
                    p = c.paragraphs[0]
                    _runsWord(p, runs, sum(cw[j : j + span]) - 8)
                    for r in p.runs:
                        r.font.size = Pt(8 if n <= 6 else 7)
                        r.bold = r.bold or entete or cls == "grp"
                    if entete or cls == "grp":
                        _fond(c, "EEF2F7")
                    j += span
            for j, w in enumerate(cw):
                for cellule in t.columns[j].cells:
                    cellule.width = Pt(w)
            doc.add_paragraph()
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


@functools.lru_cache(maxsize=8)
def export(html: str, fmt: str) -> bytes | str:
    """Dossier au format `fmt` (clé de FORMATS) : le HTML tel quel, ou sa conversion en PDF ou en Word.

    Gardé en cache : la page se réexécute à chaque clic, la conversion d'un même dossier n'est faite qu'une fois.
    """
    if fmt == "HTML":
        return html
    return {"PDF": toPdf, "Word": toDocx}[fmt](html)
