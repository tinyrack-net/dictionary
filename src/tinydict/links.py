"""Cross-reference links inside definitions.

PyGlossary writes links between entries as ``href="bword://<term>"``. That is
the GoldenDict convention, but WebView based readers such as OSS-Dict / Aard 2
treat ``bword:`` as an unknown scheme and the tap does nothing.

A plain relative href (``href="<url-encoded term>"``) works everywhere we
target:

* OSS-Dict / Aard 2 resolve it against the article URL, which looks up the term
  in the same dictionary.
* GoldenDict-ng's StarDict loader rewrites any scheme-less href to ``bword:``.
* KOReader treats a scheme-less href as the word to look up.
"""

from __future__ import annotations

import html
import re
from urllib.parse import quote

# Match up to the same quote character that opened the attribute, so terms like
# "Murphy's law" inside href="..." are kept whole.
_BWORD_HREF_RE = re.compile(r"""href=(?:"bword://([^"]*)"|'bword://([^']*)')""")


def link_href(term: str) -> str:
    """URL-encode a term so it is a safe relative link.

    Everything is encoded (including ``/``, ``#``, ``?`` and ``:``) so the term
    can't be mistaken for a path, fragment, query or URL scheme.
    """
    return quote(term, safe="")


def rewrite_bword_links(defi: str) -> str:
    def sub(m: re.Match[str]) -> str:
        quote_char = '"' if m.group(1) is not None else "'"
        term = html.unescape(m.group(1) if m.group(1) is not None else m.group(2))
        return f"href={quote_char}{link_href(term)}{quote_char}"

    return _BWORD_HREF_RE.sub(sub, defi)
