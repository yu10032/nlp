"""提取 Word 段落中的文字、常见 Office 公式及原文插图引用。"""

from docx.oxml.ns import qn


class UnsupportedFormula(ValueError):
    pass


def office_math_latex(element) -> str:
    tag = element.tag.rsplit("}", 1)[-1]

    def arg(name):
        child = element.find(qn(f"m:{name}"))
        return office_math_latex(child) if child is not None else ""

    if tag == "t":
        return (element.text or "").replace("%", r"\%").replace("#", r"\#")
    if tag.endswith("Pr"):
        return ""
    if tag == "f":
        return rf"\frac{{{arg('num')}}}{{{arg('den')}}}"
    if tag == "sSup":
        return rf"{{{arg('e')}}}^{{{arg('sup')}}}"
    if tag == "sSub":
        return rf"{{{arg('e')}}}_{{{arg('sub')}}}"
    if tag == "sSubSup":
        return rf"{{{arg('e')}}}_{{{arg('sub')}}}^{{{arg('sup')}}}"
    if tag == "rad":
        degree = arg("deg")
        return rf"\sqrt[{degree}]{{{arg('e')}}}" if degree else rf"\sqrt{{{arg('e')}}}"
    if tag == "nary":
        symbol = element.find("m:naryPr/m:chr", element.nsmap)
        symbol = symbol.get(qn("m:val"), "∫") if symbol is not None else "∫"
        operator = {"∑": r"\sum", "∏": r"\prod", "∫": r"\int"}.get(symbol)
        if operator is None:
            raise UnsupportedFormula(f"未支持的运算符 {symbol}")
        return rf"{operator}_{{{arg('sub')}}}^{{{arg('sup')}}} {arg('e')}"
    if tag == "d":
        if len(element.findall(qn("m:e"))) > 1:
            raise UnsupportedFormula("含多个表达式的分隔结构需人工核查")
        left, right = "(", ")"
        for name, default in [("begChr", "("), ("endChr", ")")]:
            node = element.find(f"m:dPr/m:{name}", element.nsmap)
            value = node.get(qn("m:val"), default) if node is not None else default
            value = {"{": r"\{", "}": r"\}", "": "."}.get(value, value)
            if name == "begChr":
                left = value
            else:
                right = value
        return rf"\left{left}{arg('e')}\right{right}"
    if tag == "func":
        return rf"\operatorname{{{arg('fName')}}}\left({arg('e')}\right)"
    if tag == "m":
        rows = [
            " & ".join(office_math_latex(cell) for cell in row if cell.tag == qn("m:e"))
            for row in element
            if row.tag == qn("m:mr")
        ]
        return r"\begin{matrix}" + r" \\ ".join(rows) + r"\end{matrix}"
    if tag == "eqArr":
        return (
            r"\begin{gathered}"
            + r" \\ ".join(office_math_latex(child) for child in element if child.tag == qn("m:e"))
            + r"\end{gathered}"
        )
    if tag in {
        "oMath",
        "oMathPara",
        "r",
        "e",
        "num",
        "den",
        "sup",
        "sub",
        "deg",
        "fName",
        "box",
        "borderBox",
        "lim",
    }:
        value = "".join(office_math_latex(child) for child in element)
        if tag == "oMath" and not value.strip():
            raise UnsupportedFormula("公式没有可提取的内容")
        return value
    raise UnsupportedFormula(f"未支持的公式结构 {tag}")


def paragraph_content(paragraph, warnings: list[str], locator: str) -> str:
    def read(element):
        if element.tag == qn("m:oMath"):
            try:
                return "$" + office_math_latex(element) + "$"
            except UnsupportedFormula as error:
                warnings.append(f"{locator}的 Word 公式需回看原件：{error}")
                return "[未完整提取的 Word 公式，请回看原件]"
        if element.tag == qn("w:t"):
            return element.text or ""
        if element.tag == qn("w:tab"):
            return "\t"
        if element.tag == qn("w:br"):
            return "\n"
        if element.tag == qn("a:blip"):
            relation = element.get(qn("r:embed"))
            return f"\n\n![原文插图，图中内容需人工核查](asset:{relation})\n\n" if relation else ""
        return "".join(read(child) for child in element)

    return read(paragraph._p).strip()
