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

"""Turn a question or a name into comparable words, so "deliveries" meets "Delivery Note"."""

import re

STOPWORDS = frozenset(
    "a an and are by do does doing for from how in is it me my of on our show the to us was we what "
    "when where which who with".split()
)
_ES_PLURAL_STEMS = ("s", "x", "ch", "sh")


def singular(word: str) -> str:
    """Strip a plural ending: companies -> company, taxes -> tax, sales -> sale, address stays."""
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 4 and word.endswith("es") and word[:-2].endswith(_ES_PLURAL_STEMS):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def tokens(text: str) -> set:
    """Lower-case singular words without stopwords."""
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {singular(w) for w in words if w not in STOPWORDS}
