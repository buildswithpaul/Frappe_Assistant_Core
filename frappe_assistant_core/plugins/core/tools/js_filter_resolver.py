# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Static resolver for query-report filter definitions declared in JavaScript.

Report JS rarely declares a plain ``filters: [...]`` array. The idiomatic
Frappe/ERPNext shape *composes* it across files: a shared namespace supplies a
base array through a builder function, and the report appends its own fields
with ``.push()``. Issue #220.

This module is deliberately **frappe-free** (stdlib only) so the whole
resolution path is pure string-in / data-out and unit-testable without a site
or a database. The one capability it cannot provide itself — reading another
app's JavaScript off disk — is injected as the ``load_shared`` callback.

Design notes
------------
Everything here is driven by a small string- and comment-aware scanner rather
than per-key regexes. That distinction is not cosmetic: regexes over raw JS
happily read filter definitions out of commented-out code, truncate values at
an apostrophe inside a double-quoted string, and interleave ``value``/``label``
pairs into a single flat options list. A scanner that knows where strings and
comments begin and end removes that entire class of defect at once.

The resolver never guesses. A value it cannot evaluate statically becomes an
:class:`Unresolved` marker, which surfaces to the caller as an explicit
``*_source: "runtime"`` hint plus the original expression — never as a silently
dropped key, and never as a fabricated value.
"""

import re
from typing import Any, Callable, Dict, List, Optional, Tuple

__all__ = ["Unresolved", "Resolution", "resolve_filters", "blank_non_code"]

# Keys we lift out of a filter object. Anything else in the object is ignored.
_TRUTHY = (1, True, "1", "true", "True")

# Frappe's Select fieldtype accepts a newline-joined string as its option list.
_NEWLINE_OPTION_FIELDTYPES = ("Select", "Autocomplete")

# Presence of any of these keys means the option list / default is computed by
# the browser at runtime and cannot be known statically.
_RUNTIME_OPTION_KEYS = ("get_data", "get_query", "get_options")

_IDENT_RE = re.compile(r"[A-Za-z_$][\w$]*")
_DOTTED_RE = re.compile(r"[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)+\Z")
_NUMBER_RE = re.compile(r"-?(?:0[xX][0-9a-fA-F]+|\d+\.?\d*(?:[eE][-+]?\d+)?|\.\d+)(?![\w$])")

# ``frappe.query_reports["Some Report"]``
_QUERY_REPORTS_RE = re.compile(
    r"frappe\s*\.\s*query_reports\s*\[\s*(?:([\"']) (.*?)\1|([A-Za-z_$][\w$]*))\s*\]".replace(" ", "")
)

# ``const PL_REPORT_NAME = "Profit and Loss Statement";`` — ERPNext v16 binds
# the report name to a module constant before subscripting query_reports.
_STRING_CONST_TMPL = r"\b(?:const|let|var)\s+{}\s*=\s*([\"'])(.*?)\1"

# ``...["filters"].push(`` / ``....filters.splice(``
_MUTATION_RE = re.compile(
    r"""(?:\[\s*["']filters["']\s*\]|\.\s*filters)\s*\.\s*(push|splice|unshift|concat)\s*\("""
)

# ``...["filters"] = [...]`` / ``....filters = [...]`` assigned post-registration.
_FILTERS_ASSIGN_RE = re.compile(r"""(?:\[\s*["']filters["']\s*\]|\.\s*filters)\s*=(?!=)""")

# Filters injected by a server round-trip after the config is declared.
_RUNTIME_INJECTOR_RE = re.compile(r"\b(add_dimensions|add_inventory_dimensions)\s*\(")

# Mutation of a filter property inside a builder body, e.g. ``x.default = fy``.
_PROP_ASSIGN_RE = re.compile(r"\.\s*(default|options|reqd|hidden)\s*=(?!=)")


class Unresolved:
    """A JS expression that cannot be evaluated statically.

    Carries the original source text so callers can surface *what* they could
    not resolve instead of dropping the key and implying it does not exist.
    """

    __slots__ = ("expr",)

    def __init__(self, expr: str):
        self.expr = " ".join(str(expr).split())

    def __repr__(self):  # pragma: no cover - debugging aid
        return f"Unresolved({self.expr!r})"

    def __eq__(self, other):
        return isinstance(other, Unresolved) and other.expr == self.expr

    def __hash__(self):
        return hash(("Unresolved", self.expr))

    def __bool__(self):
        return True


class Resolution:
    """Outcome of resolving one report's filter contract.

    ``status`` is the field that matters most to a caller:

    ``resolved``
        Filters were found and parsed.
    ``no_filters_declared``
        The report genuinely declares no filters (``filters: []`` or a config
        object with no ``filters`` key). This is a *successful* answer, not a
        failure — conflating the two is the defect issue #203 was filed for.
    ``unresolved``
        Nothing could be determined. ``notes`` says why.
    """

    def __init__(self):
        self.filters: List[Dict[str, Any]] = []
        self.status: str = "unresolved"
        self.sources: List[str] = []
        self.notes: List[str] = []
        self.partial: bool = False
        # True when a filter source was found but could not be evaluated. Kept
        # separate from `notes` so the status tree can never report
        # "no_filters_declared" for a report whose filters merely failed to
        # resolve - that would assert the opposite of the truth.
        self.failed: bool = False

    def note(self, message: str) -> None:
        if message and message not in self.notes:
            self.notes.append(message)

    def fail(self, message: str) -> None:
        """Record a resolution failure, not merely an informational note."""
        self.failed = True
        self.note(message)

    def source(self, name: str) -> None:
        if name and name not in self.sources:
            self.sources.append(name)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "filters": self.filters,
            "status": self.status,
            "sources": self.sources,
            "notes": self.notes,
            "partial": self.partial,
        }


# ---------------------------------------------------------------------------
# Lexical layer — string- and comment-aware
# ---------------------------------------------------------------------------


def scan(source: str) -> Tuple[str, str, bool]:
    """Split *source* into two same-length views used by the rest of the module.

    Returns ``(sanitized, code, clean)``:

    ``sanitized``
        Comment bodies **and** string contents blanked to spaces. Brackets and
        separators inside strings vanish, so balanced-group matching cannot be
        thrown off by a ``}`` in a message or a ``//`` in a URL.
    ``code``
        Comments blanked, string contents **kept**. Needed by the handful of
        patterns that must read a string literal in a code position — the
        report name in ``frappe.query_reports["X"]`` and the ``"filters"`` key
        in ``["filters"].push(...)``.
    ``clean``
        False if an unterminated string or block comment was seen, meaning the
        scan is unreliable and the caller should degrade to a diagnostic rather
        than trust the result.

    Offsets are preserved in both views, so a match in either indexes correctly
    into the original source.
    """
    sanitized = list(source)
    code = list(source)
    i, n = 0, len(source)
    clean = True

    def blank(target, start, end):
        for k in range(start, end):
            if target[k] != "\n":
                target[k] = " "

    while i < n:
        ch = source[i]

        if ch == "/" and i + 1 < n and source[i + 1] == "/":
            end = source.find("\n", i)
            end = n if end == -1 else end
            blank(sanitized, i, end)
            blank(code, i, end)
            i = end

        elif ch == "/" and i + 1 < n and source[i + 1] == "*":
            end = source.find("*/", i + 2)
            if end == -1:
                clean = False
                end = n
            else:
                end += 2
            blank(sanitized, i, end)
            blank(code, i, end)
            i = end

        elif ch == "`":
            # Template literals nest: `a${ `b` }c`. Track the ${…} stack so the
            # closing backtick is found correctly, and blank the whole literal
            # (substitutions included — they never hold filter definitions).
            end, terminated = _consume_template(source, i, n)
            if not terminated:
                clean = False
            blank(sanitized, i + 1, max(i + 1, end - 1))
            i = end

        elif ch in "\"'":
            quote = ch
            j = i + 1
            terminated = False
            while j < n:
                if source[j] == "\\":
                    j += 2
                    continue
                if source[j] == quote:
                    terminated = True
                    break
                # An unescaped newline ends a normal string literal.
                if source[j] == "\n":
                    break
                j += 1
            if not terminated:
                clean = False
                j = min(j, n)
            blank(sanitized, i + 1, min(j, n))
            i = min(j + 1, n) if terminated else min(j, n)

        elif ch == "/" and _starts_regex(sanitized, i):
            # A regex literal is neither code nor a string. Left alone, a `/*`
            # inside one opens a phantom block comment that swallows the report
            # config, and a quote inside one inverts the two views for the rest
            # of the file. Blank the body in both views so it can do neither.
            end, terminated = _consume_regex(source, i, n)
            if terminated:
                blank(sanitized, i + 1, end - 1)
                blank(code, i + 1, end - 1)
                i = end
            else:
                i += 1

        else:
            i += 1

    return "".join(sanitized), "".join(code), clean


# Characters after which a `/` begins a regex literal rather than a division.
_REGEX_PRECEDERS = set("(,=:[!&|?{};+-*%~^<>")
_REGEX_KEYWORDS = frozenset(
    ("return", "typeof", "instanceof", "in", "of", "new", "delete", "void", "case", "do", "else", "yield")
)


def _starts_regex(sanitized: List[str], i: int) -> bool:
    """Decide whether the ``/`` at *i* opens a regex literal."""
    j = i - 1
    while j >= 0 and sanitized[j].isspace():
        j -= 1
    if j < 0:
        return True
    ch = sanitized[j]
    if ch in _REGEX_PRECEDERS:
        return True
    if ch.isalnum() or ch in "_$":
        k = j
        while k >= 0 and (sanitized[k].isalnum() or sanitized[k] in "_$"):
            k -= 1
        return "".join(sanitized[k + 1 : j + 1]) in _REGEX_KEYWORDS
    # A closing bracket, quote or dot means the `/` is division.
    return False


def _consume_regex(source: str, i: int, n: int) -> Tuple[int, bool]:
    """Return ``(index_past_the_literal_and_flags, terminated)``."""
    j = i + 1
    in_class = False
    while j < n:
        ch = source[j]
        if ch == "\\":
            j += 2
            continue
        if ch == "\n":
            return i + 1, False
        if in_class:
            if ch == "]":
                in_class = False
        elif ch == "[":
            in_class = True
        elif ch == "/":
            j += 1
            while j < n and source[j].isalpha():
                j += 1
            return j, True
        j += 1
    return i + 1, False


def _consume_template(source: str, i: int, n: int) -> Tuple[int, bool]:
    """Return ``(index_past_the_closing_backtick, terminated)`` for a template literal."""
    stack = ["`"]
    j = i + 1
    while j < n and stack:
        ch = source[j]
        if ch == "\\":
            j += 2
            continue
        if stack[-1] == "`":
            if ch == "`":
                stack.pop()
            elif ch == "$" and j + 1 < n and source[j + 1] == "{":
                stack.append("{")
                j += 2
                continue
        else:  # inside a ${ … } substitution
            if ch == "`":
                stack.append("`")
            elif ch == "{":
                stack.append("{")
            elif ch == "}":
                stack.pop()
            elif ch in "\"'":
                quote = ch
                j += 1
                while j < n and source[j] != quote:
                    if source[j] == "\\":
                        j += 1
                    j += 1
        j += 1
    return min(j, n), not stack


def blank_non_code(source: str) -> Tuple[str, bool]:
    """Back-compat shim returning only the fully-sanitized view."""
    sanitized, _code, clean = scan(source)
    return sanitized, clean


def _report_name_at(match, source: str, sanitized: str, code: str) -> Optional[str]:
    """Report name from a ``frappe.query_reports[...]`` match.

    Returns None when the subscript is an identifier whose string binding
    cannot be found. Callers treat that as "owner unknown" rather than
    dropping the site — losing the name is not a reason to lose the filters.
    """
    if match.group(2) is not None:
        return match.group(2)
    ident = match.group(3)
    if not ident:
        return None
    decl = re.search(_STRING_CONST_TMPL.format(re.escape(ident)), code)
    if decl and _in_code(sanitized, source, decl.start()):
        return decl.group(2)
    return None


def _in_code(sanitized: str, source: str, index: int) -> bool:
    """True if *index* is a code position rather than inside a string literal."""
    return 0 <= index < len(sanitized) and sanitized[index] == source[index]


def _skip_trivia(sanitized: str, i: int) -> int:
    """Advance past whitespace (comments are already blanked)."""
    n = len(sanitized)
    while i < n and sanitized[i].isspace():
        i += 1
    return i


def _match_bracket(sanitized: str, start: int) -> int:
    """Index of the bracket closing the one at *start*, or -1.

    Operates on sanitized text, so brackets inside strings and comments are
    invisible and cannot unbalance the count.
    """
    pairs = {"{": "}", "[": "]", "(": ")"}
    opener = sanitized[start]
    closer = pairs.get(opener)
    if closer is None:
        return -1
    depth = 0
    for i in range(start, len(sanitized)):
        c = sanitized[i]
        if c == opener:
            depth += 1
        elif c == closer:
            depth -= 1
            if depth == 0:
                return i
    return -1


# ---------------------------------------------------------------------------
# Value layer — reads JS literals into Python objects
# ---------------------------------------------------------------------------


class _ValueReader:
    """Reads JS literal values, returning :class:`Unresolved` for expressions."""

    def __init__(self, source: str, sanitized: str):
        self.src = source
        self.san = sanitized

    def read(self, i: int) -> Tuple[Any, int]:
        """Read a value, rejecting literals that are only part of an expression.

        ``default: ["Jan", ..., "Dec"][getMonth()]`` starts with an array
        literal but its value is one element chosen at runtime. Returning the
        literal would hand the caller a 12-element list as the default of a
        scalar Select. Any literal followed by a member access, index or call
        is therefore surfaced as :class:`Unresolved` instead.
        """
        value, end = self._read_atom(i)
        after = _skip_trivia(self.san, end)
        if after < len(self.san) and self.san[after] in ".[(":
            return self._read_expression(i)
        return value, end

    def _read_atom(self, i: int) -> Tuple[Any, int]:
        i = _skip_trivia(self.san, i)
        if i >= len(self.san):
            return Unresolved(""), i
        ch = self.san[i]

        if ch == "{":
            return self._read_object(i)
        if ch == "[":
            return self._read_array(i)
        if ch in "\"'`":
            return self._read_string(i)

        # ``__("Label")`` is Frappe's translation call. The first argument is
        # the human-readable label, so treat the call as that string.
        ident = _IDENT_RE.match(self.san, i)
        if ident and ident.group(0) == "__":
            j = _skip_trivia(self.san, ident.end())
            if j < len(self.san) and self.san[j] == "(":
                close = _match_bracket(self.san, j)
                if close != -1:
                    inner, _ = self.read(j + 1)
                    if isinstance(inner, str):
                        return inner, close + 1
                    return Unresolved(self.src[i : close + 1]), close + 1

        if ident:
            word = ident.group(0)
            if word in ("true", "false"):
                return word == "true", ident.end()
            if word in ("null", "undefined"):
                return None, ident.end()

        num = _NUMBER_RE.match(self.san, i)
        if num and (not ident or num.end() > ident.end()):
            text = num.group(0)
            try:
                if text.lstrip("-")[:2].lower() == "0x":
                    return int(text, 16), num.end()
                if "." in text or "e" in text.lower():
                    return float(text), num.end()
                return int(text), num.end()
            except ValueError:
                pass

        return self._read_expression(i)

    def _read_string(self, i: int) -> Tuple[Any, int]:
        quote = self.san[i]
        n = len(self.src)

        if quote == "`":
            # Templates nest, so their extent must be found the same way scan()
            # finds it — not by hunting for the next backtick, which stops
            # inside `a${ `b` }c`.
            end, _terminated = _consume_template(self.src, i, n)
            raw = self.src[i + 1 : max(i + 1, end - 1)]
            if "${" in raw:
                return Unresolved(self.src[i:end]), end
            return _unescape(raw), end

        j = i + 1
        while j < n:
            if self.src[j] == "\\":
                j += 2
                continue
            if self.src[j] == quote:
                break
            if self.src[j] == "\n" and quote != "`":
                break
            j += 1
        raw = self.src[i + 1 : j]
        if quote == "`" and "${" in raw:
            return Unresolved(self.src[i : j + 1]), j + 1
        return _unescape(raw), j + 1

    def _read_array(self, i: int) -> Tuple[Any, int]:
        close = _match_bracket(self.san, i)
        if close == -1:
            return Unresolved(self.src[i:]), len(self.src)
        items: List[Any] = []
        j = i + 1
        while True:
            j = _skip_trivia(self.san, j)
            if j >= close:
                break
            if self.san[j] in ",;":
                j += 1
                continue
            start = j
            value, j = self.read(j)
            if j <= start:  # malformed input; never spin
                j = start + 1
                continue
            items.append(value)
        return items, close + 1

    def _read_object(self, i: int) -> Tuple[Any, int]:
        close = _match_bracket(self.san, i)
        if close == -1:
            return Unresolved(self.src[i:]), len(self.src)
        obj: Dict[str, Any] = {}
        j = i + 1
        while True:
            j = _skip_trivia(self.san, j)
            if j >= close:
                break
            if self.san[j] in ",;":
                j += 1
                continue

            start = j
            if self.san[j] in "\"'`":
                key, j = self._read_string(j)
            else:
                ident = _IDENT_RE.match(self.san, j)
                if not ident:
                    # Spread element or something exotic — skip to the next
                    # top-level comma rather than misreading it as a key.
                    j = self._skip_to_separator(j, close)
                    if j <= start:  # stray closer; never spin
                        j = start + 1
                    continue
                key, j = ident.group(0), ident.end()

            j = _skip_trivia(self.san, j)
            if j < close and self.san[j] == "(":
                # ES6 method shorthand: ``get_options() { ... }``. The body is
                # not statically evaluable, but the key must still be recorded.
                end = self._skip_to_separator(j, close)
                if isinstance(key, str):
                    obj[key] = Unresolved(self.src[j:end].strip())
                j = end if end > start else start + 1
                continue
            if j >= close or self.san[j] != ":":
                j = self._skip_to_separator(j, close)
                if j <= start:
                    j = start + 1
                continue

            value, j = self.read(j + 1)
            if j <= start:
                j = start + 1
            if isinstance(key, str):
                obj[key] = value
        return obj, close + 1

    def _read_expression(self, i: int) -> Tuple[Any, int]:
        """Consume an arbitrary expression up to the next top-level separator.

        Always advances. A stray closing bracket makes _skip_to_separator stop
        where it started; returning that index unchanged would spin the calling
        array/object loop forever on malformed (or mis-scanned) input.
        """
        j = self._skip_to_separator(i, len(self.san))
        if j <= i:
            j = i + 1
        return Unresolved(self.src[i:j]), j

    def _skip_to_separator(self, i: int, limit: int) -> int:
        """Index of the separator ending the expression that starts at *i*.

        Balanced groups are skipped whole, so the only stoppers seen here are
        at the expression's own level: a comma, a statement-ending semicolon,
        or the closer of the group we sit inside. May return *i* itself when
        *i* already points at a stopper — callers must not rely on progress.
        """
        j = i
        while j < limit:
            c = self.san[j]
            if c in "{[(":
                close = _match_bracket(self.san, j)
                j = (close + 1) if close != -1 else limit
                continue
            if c in "}])" or c in ",;":
                return j
            j += 1
        return limit


def _unescape(raw: str) -> str:
    out = []
    i, n = 0, len(raw)
    simple = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v", "0": "\0"}
    while i < n:
        if raw[i] == "\\" and i + 1 < n:
            nxt = raw[i + 1]
            if nxt == "u" and raw[i + 2 : i + 3] == "{":
                end = raw.find("}", i + 3)
                if end != -1:
                    try:
                        out.append(chr(int(raw[i + 3 : end], 16)))
                        i = end + 1
                        continue
                    except (ValueError, OverflowError):
                        pass
            elif nxt == "u" and i + 5 < n:
                try:
                    point = int(raw[i + 2 : i + 6], 16)
                except ValueError:
                    point = None
                if point is not None:
                    # Join a surrogate pair, otherwise the result is a lone
                    # surrogate that cannot be encoded to UTF-8 later.
                    if 0xD800 <= point <= 0xDBFF and raw[i + 6 : i + 8] == "\\u":
                        try:
                            low = int(raw[i + 8 : i + 12], 16)
                        except ValueError:
                            low = None
                        if low is not None and 0xDC00 <= low <= 0xDFFF:
                            out.append(chr(0x10000 + ((point - 0xD800) << 10) + (low - 0xDC00)))
                            i += 12
                            continue
                    out.append(chr(point))
                    i += 6
                    continue
            elif nxt == "x" and i + 3 < n:
                try:
                    out.append(chr(int(raw[i + 2 : i + 4], 16)))
                    i += 4
                    continue
                except ValueError:
                    pass
            out.append(simple.get(nxt, nxt))
            i += 2
            continue
        out.append(raw[i])
        i += 1
    return "".join(out)


# ---------------------------------------------------------------------------
# Normalisation — JS filter object to FAC filter definition
# ---------------------------------------------------------------------------


def _normalize_filter(obj: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Convert one parsed JS filter object into FAC's filter-definition shape.

    Returns None for entries that are not user-facing filters (layout breaks,
    objects with no resolvable fieldname).
    """
    if not isinstance(obj, dict):
        return None

    fieldname = obj.get("fieldname")
    if not isinstance(fieldname, str) or not fieldname.strip():
        return None

    fieldtype = obj.get("fieldtype")
    if not isinstance(fieldtype, str):
        fieldtype = None
    if fieldtype in ("Break", "Section Break", "Column Break", "HTML"):
        return None

    out: Dict[str, Any] = {"fieldname": fieldname}

    # ``lable`` is a typo present in shipped ERPNext report JS.
    label = obj.get("label")
    if not isinstance(label, str):
        label = obj.get("lable") if isinstance(obj.get("lable"), str) else None
    out["label"] = label or fieldname

    if fieldtype:
        out["fieldtype"] = fieldtype

    options, options_note = _normalize_options(obj, fieldtype)
    if options is not None:
        out["options"] = options
    if options_note:
        out["options_source"] = "runtime"
        out["options_expr"] = options_note

    default, default_expr = _normalize_default(obj.get("default"))
    if default is not None:
        out["default"] = default
    if default_expr:
        out["default_source"] = "runtime"
        out["default_expr"] = default_expr

    # ``mandatory`` is an accepted alias for ``reqd`` in report JS.
    reqd = obj.get("reqd")
    if reqd is None:
        reqd = obj.get("mandatory")
    out["required"] = reqd in _TRUTHY

    for key in ("depends_on", "mandatory_depends_on"):
        value = obj.get(key)
        if isinstance(value, str) and value.strip():
            out[key] = value

    if obj.get("hidden") in _TRUTHY:
        out["hidden"] = True

    if obj.get("wildcard_filter") in _TRUTHY:
        out["wildcard_filter"] = True

    return out


def _normalize_options(obj: Dict[str, Any], fieldtype: Optional[str]):
    """Return ``(options, runtime_expr)`` for a filter object.

    Handles every option form found in the wild: an array of strings, an array
    of ``{value, label}`` objects (including numeric values), a mixed array
    with a leading blank choice, a newline-joined Select string, and a plain
    DocType name for Link fields.
    """
    raw = obj.get("options")

    if raw is None:
        for key in _RUNTIME_OPTION_KEYS:
            if key in obj:
                return None, f"{key}()"
        return None, None

    if isinstance(raw, Unresolved):
        return None, raw.expr

    if isinstance(raw, list):
        values: List[Any] = []
        for item in raw:
            if isinstance(item, dict):
                value = item.get("value")
                if isinstance(value, Unresolved) or value is None:
                    continue
                values.append(value)
            elif isinstance(item, Unresolved):
                continue
            elif item is None:
                continue
            elif isinstance(item, str):
                # A leading "" is Frappe's "no selection" placeholder, not a
                # selectable value.
                if item.strip():
                    values.append(item)
            else:
                values.append(item)
        return values, None

    if isinstance(raw, str):
        if "\n" in raw:
            values = [line.strip() for line in raw.split("\n") if line.strip()]
            return values, None
        if fieldtype in _NEWLINE_OPTION_FIELDTYPES and not raw.strip():
            return [], None
        # Link / MultiSelectList / Dynamic Link: the target DocType.
        return raw, None

    return None, None


def _normalize_default(raw: Any):
    """Return ``(literal_default, runtime_expression)``."""
    if raw is None:
        return None, None
    if isinstance(raw, Unresolved):
        return None, raw.expr
    if isinstance(raw, list):
        literals = [v for v in raw if not isinstance(v, (Unresolved, dict, list))]
        if not literals:
            return None, None
        # ERPNext writes ``default: ["Fiscal Year"]`` for a scalar Select.
        return (literals[0] if len(literals) == 1 else literals), None
    if isinstance(raw, dict):
        return None, None
    return raw, None


# ---------------------------------------------------------------------------
# Structural layer — locating and composing the filter array
# ---------------------------------------------------------------------------


def _find_config_assignments(source: str, sanitized: str, code: str, report_name: Optional[str]):
    """Find ``frappe.query_reports["X"] = ...`` sites.

    Matched against the *code* view so the report name inside the brackets is
    readable, then validated against the sanitized view so an occurrence inside
    a string literal is rejected.
    """
    results = []
    for match in _QUERY_REPORTS_RE.finditer(code):
        if not _in_code(sanitized, source, match.start()):
            continue
        after = _skip_trivia(sanitized, match.end())
        if after < len(sanitized) and sanitized[after] == "=" and sanitized[after + 1 : after + 2] != "=":
            name = _report_name_at(match, source, sanitized, code)
            results.append((match, after + 1, report_name is None or name is None or name == report_name))
    return results


def _find_function_body(source: str, sanitized: str, name: str):
    """Return ``(body_start, body_end)`` for a function declared as *name*."""
    escaped = re.escape(name)
    patterns = (
        rf"\bfunction\s+{escaped}\s*\(",
        rf"\b(?:const|let|var)\s+{escaped}\s*=\s*(?:async\s+)?function\s*\*?\s*\(",
        rf"\b(?:const|let|var)\s+{escaped}\s*=\s*(?:async\s+)?\(",
        rf"\b(?:const|let|var)\s+{escaped}\s*=\s*(?:async\s+)?[A-Za-z_$][\w$]*\s*=>",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, sanitized):
            i = match.end() - 1
            if sanitized[i] == "(":
                close = _match_bracket(sanitized, i)
                if close == -1:
                    continue
                i = _skip_trivia(sanitized, close + 1)
                if sanitized[i : i + 2] == "=>":
                    i = _skip_trivia(sanitized, i + 2)
            else:
                i = _skip_trivia(sanitized, match.end())
                if sanitized[i : i + 2] == "=>":
                    i = _skip_trivia(sanitized, i + 2)
            if i < len(sanitized) and sanitized[i] == "{":
                end = _match_bracket(sanitized, i)
                if end != -1:
                    return i, end
    return None


def _top_level_return(sanitized: str, start: int, end: int) -> int:
    """Index just past the ``return`` keyword of *this* function body.

    Balanced groups are skipped wholesale, so a ``return`` inside a nested
    ``get_data``/``get_query`` callback — which real report builders are full
    of — is never mistaken for the builder's own return statement.
    """
    i = start + 1
    while i < end:
        ch = sanitized[i]
        if ch in "{[(":
            close = _match_bracket(sanitized, i)
            if close == -1 or close > end:
                return -1
            i = close + 1
            continue
        if ch == "r" and sanitized.startswith("return", i):
            before = sanitized[i - 1] if i else " "
            after = sanitized[i + 6] if i + 6 < len(sanitized) else " "
            if not (before.isalnum() or before in "_$") and not (after.isalnum() or after in "_$"):
                return i + 6
        i += 1
    return -1


def _array_from_function_body(source, sanitized, start, end, result: Resolution):
    """Extract the filter array a builder function returns."""
    reader = _ValueReader(source, sanitized)
    body_san = sanitized[start:end]

    ret = _top_level_return(sanitized, start, end)
    if ret == -1:
        return None

    after = _skip_trivia(sanitized, ret)
    if after < end and sanitized[after] == "[":
        value, _ = reader.read(after)
        array_end = _match_bracket(sanitized, after)
        _note_builder_mutations(source, sanitized, array_end, end, value, result)
        return value

    ident = _IDENT_RE.match(sanitized, after)
    if not ident:
        return None

    var = ident.group(0)
    decl = re.search(rf"\b(?:let|const|var)\s+{re.escape(var)}\s*=\s*\[", body_san)
    if not decl:
        result.fail(f"builder returns '{var}', which is not declared as a literal array in its body")
        return None

    bracket = start + decl.end() - 1
    value, _ = reader.read(bracket)
    array_end = _match_bracket(sanitized, bracket)
    _note_builder_mutations(source, sanitized, array_end, end, value, result)
    return value


def _note_builder_mutations(source, sanitized, array_end, body_end, array_value, result: Resolution):
    """Flag filters whose default/options the builder overwrites after declaration.

    ``financial_statements.get_filters()`` fills in fiscal-year defaults with a
    ``forEach`` after building the literal array. Reporting those fields as
    "no default" would tell an agent to ask the user for a value the UI always
    pre-fills.
    """
    if array_end == -1 or array_end >= body_end:
        return
    if not _PROP_ASSIGN_RE.search(sanitized[array_end:body_end]):
        return

    fieldnames = set()
    if isinstance(array_value, list):
        for item in array_value:
            if isinstance(item, dict) and isinstance(item.get("fieldname"), str):
                fieldnames.add(item["fieldname"])

    # String contents are blanked in the sanitized view, so the field names the
    # mutation targets have to be matched against the original source. Restrict
    # the match to bracketed array literals — the real shape is
    # ``["from_fiscal_year", "to_fiscal_year"].includes(x.fieldname)`` — so a
    # field name merely mentioned in a msgprint or comment is not attributed.
    tail = source[array_end:body_end]
    selectors = " ".join(re.findall(r"\[[^\[\]]*\]", tail))
    touched = sorted(fn for fn in fieldnames if re.search(rf"[\"']{re.escape(fn)}[\"']", selectors))
    if touched:
        result.note(
            "builder assigns values at runtime for: "
            + ", ".join(touched)
            + " (treat their default/options as supplied by the UI)"
        )
        result._runtime_assigned = touched  # noqa: SLF001 - consumed below
    else:
        result.note("builder mutates filter properties at runtime after declaring the array")


def _resolve_filters_value(value, source, sanitized, result: Resolution, load_shared, depth=0):
    """Resolve whatever sits to the right of a ``filters:`` key into a list."""
    if isinstance(value, list):
        return value

    if not isinstance(value, Unresolved):
        return None

    expr = value.expr

    # ``filters: get_filters()`` — a local builder function.
    # fullmatch, not match: ``base().concat([...])`` starts like a builder call
    # but the trailing .concat() changes the result, so returning the builder's
    # array alone would silently drop the concatenated filters.
    call = re.fullmatch(r"([A-Za-z_$][\w$]*)\s*\([^()]*\)\s*;?", expr)
    if call:
        name = call.group(1)
        body = _find_function_body(source, sanitized, name)
        if body:
            array = _array_from_function_body(source, sanitized, body[0], body[1], result)
            if array is not None:
                result.source(f"builder:{name}()")
                return array
            result.fail(f"builder {name}() found but its returned array could not be read")
            return None
        result.fail(f"filters are built by {name}(), which is not defined in this file")
        return None

    # ``filters: erpnext.some_namespace.filters`` — a cross-file reference.
    # Strip a trailing semicolon: expressions now stop at `;`, and the raw text
    # would otherwise defeat the \Z-anchored dotted-identifier test.
    bare = expr.rstrip().rstrip(";").rstrip()
    if _DOTTED_RE.match(bare) and depth < 3 and load_shared:
        namespace = bare.rsplit(".", 1)[0] if bare.endswith(".filters") else bare
        shared = _resolve_namespace(namespace, result, load_shared, depth + 1)
        if shared is not None:
            return shared

    result.fail(f"filters value is not a static array: {expr[:120]}")
    return None


def _resolve_namespace(namespace: str, result: Resolution, load_shared, depth=0):
    """Load a shared namespace's JS and return its filter array."""
    if not load_shared or depth > 3:
        return None

    shared_source = load_shared(namespace)
    if not shared_source:
        result.fail(f"shared namespace '{namespace}' referenced but its source was not found")
        return None

    shared_san, shared_code, clean = scan(shared_source)
    if not clean:
        result.note(f"shared namespace '{namespace}' has unbalanced quotes or comments; scan may be partial")

    assign = re.search(rf"{re.escape(namespace)}\s*=\s*\{{", shared_san)
    if not assign:
        result.fail(f"shared namespace '{namespace}' source found but no object assignment in it")
        return None

    reader = _ValueReader(shared_source, shared_san)
    config, _ = reader.read(assign.end() - 1)
    if not isinstance(config, dict) or "filters" not in config:
        result.fail(f"shared namespace '{namespace}' declares no filters")
        return None

    result.source(f"shared:{namespace}")
    return _resolve_filters_value(
        config["filters"], shared_source, shared_san, result, load_shared, depth + 1
    )


def _resolve_config(value, source, sanitized, result: Resolution, load_shared, depth=0):
    """Resolve a report config value (object or ``$.extend(...)``) to its filters."""
    if isinstance(value, dict):
        if "filters" not in value:
            # A config object that exists and declares no `filters` key means
            # the report takes no filters. Frappe reads filters from nowhere
            # else, so this is a definite answer rather than a parse failure.
            return []
        return _resolve_filters_value(value["filters"], source, sanitized, result, load_shared, depth)

    if not isinstance(value, Unresolved):
        return None

    expr = value.expr
    extend = re.match(r"(?:\$\.extend|jQuery\.extend|Object\.assign)\s*\(", expr)
    if not extend:
        if _DOTTED_RE.match(expr):
            return _resolve_namespace(expr, result, load_shared, depth + 1)
        result.fail(f"report config is not a static object: {expr[:120]}")
        return None

    # Read the call arguments. jQuery.extend merges left-to-right, so a later
    # argument's ``filters`` wins over an earlier one's.
    arg_san, _arg_code, _arg_clean = scan(expr)
    open_paren = arg_san.index("(", extend.end() - 1)
    close = _match_bracket(arg_san, open_paren)
    if close == -1:
        result.fail("unbalanced $.extend() call in report config")
        return None

    reader = _ValueReader(expr, arg_san)
    args: List[Any] = []
    i = open_paren + 1
    while True:
        i = _skip_trivia(arg_san, i)
        if i >= close:
            break
        if arg_san[i] == ",":
            i += 1
            continue
        arg, i = reader.read(i)
        args.append(arg)

    # ``$.extend(true, {}, ns)`` — a leading boolean means deep copy.
    args = [a for a in args if not isinstance(a, bool)]

    resolved = None
    for arg in args:
        if isinstance(arg, dict) and "filters" in arg:
            candidate = _resolve_filters_value(arg["filters"], source, sanitized, result, load_shared, depth)
            if candidate is not None:
                resolved = candidate
        elif isinstance(arg, Unresolved) and _DOTTED_RE.match(arg.expr):
            candidate = _resolve_namespace(arg.expr, result, load_shared, depth + 1)
            if candidate is not None:
                # jQuery.extend merges left to right, so a later argument's
                # filters override an earlier one's.
                resolved = candidate

    if resolved is None:
        result.fail("report config mixes in a namespace whose filters could not be resolved")
    return resolved


# Only member access may separate ``frappe.query_reports["X"]`` from the
# ``.filters`` it owns — whitespace, dots, brackets, quotes and the word itself.
_MEMBER_ACCESS_RE = re.compile(r"[\s.\[\]\"']*(?:filters[\s.\[\]\"']*)?\Z")


def _owner_lookup(source, sanitized, code):
    """Build a resolver from a source offset to the report name that owns it."""
    owners = [
        (match.end(), _report_name_at(match, source, sanitized, code))
        for match in _QUERY_REPORTS_RE.finditer(code)
        if _in_code(sanitized, source, match.start())
    ]

    def owner_of(position):
        best = None
        for end, name in owners:
            if end <= position and (best is None or end > best[0]):
                best = (end, name)
        if best is None:
            return None
        # Matched against the sanitized view so a comment mentioning another
        # report cannot redirect the mutation.
        return best[1] if _MEMBER_ACCESS_RE.match(sanitized[best[0] : position]) else None

    return owner_of


def _collect_mutations(source, sanitized, code, report_name, result: Resolution):
    """Find ``.filters`` mutations for this report, in source order.

    Each site is attributed by walking back to the nearest preceding
    ``frappe.query_reports["X"]`` and requiring that only member access
    separates the two. Substring matching on the report name would let
    "Sales Register" steal a push belonging to "Sales Register Detail", and a
    line-based lookback loses a push that prettier wrapped onto its own line.
    """
    owner_of = _owner_lookup(source, sanitized, code)
    mutations = []

    def owned(position):
        if not report_name:
            return True
        owner = owner_of(position)
        # An unresolvable subscript means the owner is unknown, not foreign.
        return owner is None or owner == report_name

    for match in _MUTATION_RE.finditer(code):
        if not _in_code(sanitized, source, match.start()) or not owned(match.start()):
            continue
        open_paren = match.end() - 1
        close = _match_bracket(sanitized, open_paren)
        if close == -1:
            continue
        mutations.append((match.start(), match.group(1), open_paren, close))

    # ``frappe.query_reports["X"].filters = [...]`` assigns the list after the
    # config object was registered; without this the report looks filter-less.
    for match in _FILTERS_ASSIGN_RE.finditer(code):
        if not _in_code(sanitized, source, match.start()) or not owned(match.start()):
            continue
        mutations.append((match.start(), "assign", match.end(), None))

    mutations.sort(key=lambda m: m[0])
    return mutations


def _apply_mutations(filters, mutations, source, sanitized, result: Resolution):
    """Replay ``push`` mutations; refuse index-based ones.

    ``splice`` is replayed by index into the base array. If any base entry
    failed to parse, every index shifts and the replay silently removes the
    wrong filter — two errors in opposite directions with no diagnostic. The
    honest move is to refuse and say so.
    """
    reader = _ValueReader(source, sanitized)
    by_name = {f.get("fieldname"): i for i, f in enumerate(filters) if isinstance(f, dict)}

    for _pos, kind, open_paren, close in mutations:
        if kind == "assign":
            value, _ = reader.read(open_paren)
            if isinstance(value, list):
                filters[:] = value
                by_name = {f.get("fieldname"): n for n, f in enumerate(filters) if isinstance(f, dict)}
                result.source("assign")
            else:
                result.fail("report assigns its filters from an expression that could not be evaluated")
            continue

        if kind != "push":
            result.partial = True
            result.note(
                f"report mutates its filter list with .{kind}() — that call is not replayed, so this "
                "list may include a filter the report removes or omit one it reorders"
            )
            continue

        i = open_paren + 1
        added = 0
        while True:
            i = _skip_trivia(sanitized, i)
            if i >= close:
                break
            if sanitized[i] == ",":
                i += 1
                continue
            value, i = reader.read(i)
            for obj in value if isinstance(value, list) else [value]:
                if not isinstance(obj, dict):
                    continue
                name = obj.get("fieldname")
                if isinstance(name, str) and name in by_name:
                    filters[by_name[name]] = obj
                else:
                    by_name[name] = len(filters)
                    filters.append(obj)
                added += 1
        if added:
            result.source("push")

    return filters


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def resolve_filters(
    js_text: str,
    report_name: Optional[str] = None,
    load_shared: Optional[Callable[[str], Optional[str]]] = None,
) -> Resolution:
    """Resolve a report's filter contract from its JavaScript.

    Args:
        js_text: contents of the report's ``.js`` (or ``Report.javascript``).
        report_name: the report's exact name, used to attribute
            ``frappe.query_reports["..."]`` assignments and ``.push()`` calls
            when one file configures several reports.
        load_shared: callback resolving a JS namespace such as
            ``"erpnext.financial_statements"`` to that file's source, or None.
            Injected so this module stays free of Frappe imports.

    Returns:
        A :class:`Resolution`. Check ``status`` before ``filters`` — an empty
        list with ``status == "no_filters_declared"`` is a real answer.
    """
    result = Resolution()

    if not js_text or not js_text.strip():
        result.note("no JavaScript source available")
        return result

    source = js_text
    sanitized, code, clean = scan(source)
    if not clean:
        result.note("unterminated string or comment in JS; parse may be incomplete")
        result.partial = True

    reader = _ValueReader(source, sanitized)
    raw_filters = None
    config_found = False

    assignments = _find_config_assignments(source, sanitized, code, report_name)
    for _match, value_start, is_ours in assignments:
        if not is_ours:
            continue
        config_found = True
        value, _ = reader.read(value_start)
        raw_filters = _resolve_config(value, source, sanitized, result, load_shared)
        if raw_filters is not None:
            result.source("report_js")
            break

    # A file may configure a report under a name that differs from the Report
    # doc (or we may have been given no name at all) — retry unfiltered.
    if raw_filters is None and report_name and assignments and not config_found:
        for _match, value_start, _is_ours in assignments:
            value, _ = reader.read(value_start)
            raw_filters = _resolve_config(value, source, sanitized, result, load_shared)
            if raw_filters is not None:
                config_found = True
                result.source("report_js")
                break

    if not assignments:
        # Bare ``filters: [...]`` with no frappe.query_reports wrapper — the
        # shape used by hand-written Report.javascript snippets.
        key = re.search(r"[\"']?\bfilters[\"']?\s*:", sanitized)
        if key:
            config_found = True
            value, _ = reader.read(key.end())
            raw_filters = _resolve_filters_value(value, source, sanitized, result, load_shared)
            if raw_filters is not None:
                result.source("report_js")
        else:
            result.note("no report configuration found in JS")

    working = list(raw_filters) if raw_filters is not None else []
    mutations = _collect_mutations(source, sanitized, code, report_name, result)
    if mutations:
        config_found = True
        working = _apply_mutations(working, mutations, source, sanitized, result)

    if _RUNTIME_INJECTOR_RE.search(sanitized):
        result.note(
            "report injects additional filters at runtime via add_dimensions()/"
            "add_inventory_dimensions(); accounting or inventory dimension filters are not listed here"
        )
        result.partial = True

    normalized = []
    for obj in working:
        filter_def = _normalize_filter(obj)
        if filter_def:
            normalized.append(filter_def)

    runtime_assigned = getattr(result, "_runtime_assigned", ())
    for filter_def in normalized:
        if filter_def["fieldname"] in runtime_assigned and "default" not in filter_def:
            filter_def["default_source"] = "runtime"

    result.filters = normalized

    # "no_filters_declared" is a positive assertion — the caller is told the
    # report genuinely takes none. It is only ever safe to make it when
    # nothing failed along the way; every other outcome must degrade to
    # "unresolved" so the diagnostics get read instead of trusted away.
    if normalized:
        result.status = "resolved"
    elif working:
        # Entries were present but none read as a filter definition (e.g. an
        # array of factory calls). Emphatically not "this report has none".
        result.fail("filter entries were found but none could be read as filter definitions")
        result.status = "unresolved"
    elif result.failed:
        result.status = "unresolved"
    elif raw_filters is not None:
        result.status = "no_filters_declared"
        result.note("report explicitly declares an empty filter list")
    elif not config_found and clean and not result.partial and not _mentions_filters(sanitized):
        # The JS scanned cleanly and does not mention `filters` anywhere in a
        # code position — only, at most, inside comments. Frappe registers
        # filters solely from `frappe.query_reports[...].filters` and the
        # Report.filters child table, so there is genuinely nothing to find.
        # Saying so is far more useful than reporting a parse failure.
        result.status = "no_filters_declared"
        result.note("report JS declares no filter configuration")
    else:
        result.status = "unresolved"

    return result


def _mentions_filters(sanitized: str) -> bool:
    """True if ``filters`` appears in a code position (not only in comments)."""
    return re.search(r"\bfilters\b", sanitized) is not None
