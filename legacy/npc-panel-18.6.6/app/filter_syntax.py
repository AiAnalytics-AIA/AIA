"""Normalization of questionnaire filter expressions.

Filters are authored by an LLM or typed by a user, so they arrive in whatever
syntax felt natural: ``s1 = 'Ano'``, ``s1 == "Ano" AND s2 != 'Ne'``, Czech
connectives, smart quotes. The runtime evaluator understands a small Python
subset, so anything else used to surface as a hard BLOCKER ("Neplatná syntaxe
filtru: invalid syntax") with no way to fix it from the UI.

This module converts the common variants into the supported subset before both
linting and evaluation, so lint and runtime can never disagree.
"""
from __future__ import annotations

import ast
import re

_QUOTES = {"\u201e": "'", "\u201c": "'", "\u201d": "'", "\u2018": "'", "\u2019": "'", "\u00ab": "'", "\u00bb": "'", '"': "'"}

_WORD_OPS = [
    (r"\bAND\b", " and "), (r"\bOR\b", " or "), (r"\bNOT\b", " not "),
    (r"\ba\s+zároveň\b", " and "), (r"\bzároveň\b", " and "),
    (r"\bnebo\b", " or "), (r"\banebo\b", " or "),
    (r"(?<=[\)\]'\"\w])\s+a\s+(?=[\w\(\'\"])", " and "),
    (r"\bnení\b", " != "), (r"\bje\s+různé\s+od\b", " != "),
    (r"\bje\s+rovno\b", " == "), (r"\bje\b", " == "),
    (r"\bobsahuje\b", " in "), (r"\bv\s*\[", " in ["),
    (r"\bIN\b", " in "), (r"\bNOT\s+IN\b", " not in "),
]


def normalize_filter(expr: str | None) -> str:
    """Return an expression the safe evaluator can parse (best effort, lossless intent)."""
    s = str(expr or "").strip()
    if not s:
        return ""
    for bad, good in _QUOTES.items():
        s = s.replace(bad, good)
    s = s.replace("&&", " and ").replace("||", " or ")
    s = re.sub(r"(?<![!<>=])!(?=\s*[\w'(])", " not ", s)
    for pattern, repl in _WORD_OPS:
        s = re.sub(pattern, repl, s)
    # Single '=' used as comparison, but never inside ==, !=, <=, >=.
    s = re.sub(r"(?<![=!<>])=(?!=)", "==", s)
    # 'in (a, b)' -> 'in [a, b]'
    s = re.sub(r"\bin\s*\(([^()]*)\)", lambda m: "in [" + m.group(1) + "]", s)
    s = re.sub(r"\s+", " ", s).strip().strip(";")
    return s


def _bare_names(expr: str) -> set[str]:
    return {n.id for n in ast.walk(ast.parse(expr, mode="eval")) if isinstance(n, ast.Name)}


class _QuestionIdCaseNormalizer(ast.NodeTransformer):
    """Map question references to their canonical compiled IDs case-insensitively.

    Project normalization slugifies IDs (e.g. ``O1`` -> ``o1``). Filters authored
    before normalization must follow the same renaming or the compiled project
    falsely appears to reference a missing/forward question.
    """
    def __init__(self, known: set[str]):
        self.by_fold={str(x).casefold():str(x) for x in known}
        self.changed=False

    def visit_Name(self, node: ast.Name) -> ast.AST:
        canonical=self.by_fold.get(str(node.id).casefold())
        if canonical and canonical != node.id:
            self.changed=True
            return ast.copy_location(ast.Name(id=canonical,ctx=node.ctx),node)
        return node


class _QuoteRightHandLiterals(ast.NodeTransformer):
    """Turn ``s1 == Ano`` into ``s1 == 'Ano'`` without touching question references.

    Only the right-hand side of a comparison (and list members) may be an answer
    label. The left-hand identifier must stay a name, otherwise a forward reference
    to a question that does not exist would silently stop being detected.
    """

    def __init__(self, known: set[str]):
        self.known = known
        self.changed = False

    def _literalize(self, node: ast.AST) -> ast.AST:
        if isinstance(node, ast.Name) and node.id not in self.known and node.id not in {"True", "False", "None"}:
            self.changed = True
            return ast.Constant(value=node.id)
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            node.elts = [self._literalize(x) for x in node.elts]
            return node
        return node

    def visit_Compare(self, node: ast.Compare) -> ast.AST:
        node.left = self.generic_visit(node.left) if not isinstance(node.left, ast.Name) else node.left
        node.comparators = [self._literalize(c) for c in node.comparators]
        return node


def repair_filter(expr: str | None, known_ids: set[str] | None = None) -> tuple[str, str]:
    """Normalize and, when safe, quote bare literals like ``s1 == Ano``.

    Returns ``(expression, note)``. ``note`` is empty when nothing was changed.
    """
    original = str(expr or "").strip()
    s = normalize_filter(original)
    if not s:
        return "", ""
    known = {str(x) for x in (known_ids or set())}
    try:
        tree = ast.parse(s, mode="eval")
    except SyntaxError:
        return s, ("Filtr nelze rozparsovat: " + original) if original else ""
    if known:
        # IDs are canonicalized by project compilation, so normalize references
        # before deciding whether a bare comparator token is an answer literal.
        ids = _QuestionIdCaseNormalizer(known)
        tree = ast.fix_missing_locations(ids.visit(tree))
        tr = _QuoteRightHandLiterals(known)
        tree = ast.fix_missing_locations(tr.visit(tree))
        if ids.changed or tr.changed:
            try:
                s = ast.unparse(tree)
            except Exception:
                s = normalize_filter(original)
    note = "" if s == original else f"Filtr byl normalizován: {original} → {s}"
    return s, note


def filter_error(expr: str | None, known_ids: set[str] | None = None) -> str:
    """Return an actionable Czech error, or '' when the filter is usable."""
    s, _ = repair_filter(expr, known_ids)
    if not s:
        return ""
    try:
        ast.parse(s, mode="eval")
    except SyntaxError as exc:
        return (f"Filtr '{expr}' není platný výraz ({exc.msg}). "
                "Použijte tvar jako s1 == 'Ano', s1 != 'Ne', s1 in ['A','B'] "
                "a spojujte podmínky pomocí and / or.")
    return ""
