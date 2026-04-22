"""Pure-Python parser for VLESS+Reality URLs.

The parser converts one line of the form::

    vless://<uuid>@<host>:<port>?encryption=none&security=reality&...#<name>

into a typed :class:`VlessNode`. It is intentionally tolerant — unknown query
params are preserved under :attr:`VlessNode.extra` so we never silently drop
information, and :func:`parse_vless_list` keeps going after a bad line instead
of aborting the whole batch.

No network I/O, no subprocess, no filesystem. Safe to import in any context.
"""
from __future__ import annotations

import urllib.parse
from dataclasses import dataclass, field


class VlessParseError(ValueError):
    """Raised when a single VLESS URL cannot be parsed.

    The message is deliberately descriptive — downstream code (especially the
    tolerant :func:`parse_vless_list`) aggregates these errors for logging so
    operators can diagnose upstream source drift without reading source code.
    """


@dataclass
class VlessNode:
    """Typed representation of a single VLESS+Reality outbound.

    Attributes map 1:1 to the fields the xray-core VLESS outbound needs. The
    defaults mirror what igareck-style RU configs typically ship with. Unknown
    query params are preserved in :attr:`extra` so future param additions do
    not require a parser change.
    """

    uuid: str
    host: str
    port: int
    name: str
    reality_pbk: str
    reality_sni: str
    reality_sid: str = ""
    reality_spx: str = ""
    reality_fp: str = "chrome"
    flow: str = ""
    transport: str = "tcp"
    encryption: str = "none"
    header_type: str = "none"
    extra: dict = field(default_factory=dict)

    @property
    def address(self) -> str:
        """Return the human-readable host:port for this node."""
        return f"{self.host}:{self.port}"


# Query params we recognize and map to explicit fields. Any param not in this
# set is preserved in ``VlessNode.extra`` so callers can round-trip.
_KNOWN_PARAMS = frozenset(
    {
        "security",
        "sni",
        "fp",
        "pbk",
        "sid",
        "spx",
        "flow",
        "type",
        "encryption",
        "headerType",
    }
)


def _first(values: list[str]) -> str:
    """Return the first value of a query-param list, or empty string."""
    return values[0] if values else ""


def parse_vless_url(url: str) -> VlessNode:
    """Parse one VLESS URL into a :class:`VlessNode`.

    Raises :class:`VlessParseError` on any structural issue (wrong scheme,
    missing uuid, missing host, non-numeric port, missing reality public key,
    or an explicit ``security=`` value other than ``reality``).
    """
    if not isinstance(url, str):
        raise VlessParseError(f"expected str, got {type(url).__name__}")

    raw = url.strip()
    if not raw:
        raise VlessParseError("empty VLESS URL")

    parsed = urllib.parse.urlparse(raw)
    if parsed.scheme.lower() != "vless":
        raise VlessParseError(f"unexpected scheme {parsed.scheme!r} (need 'vless')")

    uuid = urllib.parse.unquote(parsed.username or "")
    if not uuid:
        raise VlessParseError("missing uuid before '@'")

    host = parsed.hostname
    if not host:
        raise VlessParseError("missing host after '@'")

    if parsed.port is None:
        raise VlessParseError(f"missing or invalid port in {raw!r}")
    port = int(parsed.port)

    # ``parse_qs`` naturally collapses empty values to empty strings for us.
    params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)

    security = _first(params.get("security", [])).lower()
    if security and security != "reality":
        raise VlessParseError(
            f"unsupported security={security!r}; this parser is Reality-only"
        )

    pbk = _first(params.get("pbk", []))
    if not pbk:
        raise VlessParseError("missing reality public key (pbk=...)")

    sni = _first(params.get("sni", []))
    sid = _first(params.get("sid", []))
    spx = _first(params.get("spx", []))
    fp = _first(params.get("fp", [])) or "chrome"
    flow = _first(params.get("flow", []))
    transport = _first(params.get("type", [])) or "tcp"
    encryption = _first(params.get("encryption", [])) or "none"
    header_type = _first(params.get("headerType", [])) or "none"

    extra: dict[str, str] = {}
    for key, values in params.items():
        if key in _KNOWN_PARAMS:
            continue
        # Preserve the first non-empty value; unknown multi-value params are
        # out of scope for v1 and have never been observed in the wild.
        extra[key] = _first(values)

    fragment = urllib.parse.unquote(parsed.fragment or "")
    name = fragment.strip() or f"{host}:{port}"

    return VlessNode(
        uuid=uuid,
        host=host,
        port=port,
        name=name,
        reality_pbk=pbk,
        reality_sni=sni,
        reality_sid=sid,
        reality_spx=spx,
        reality_fp=fp,
        flow=flow,
        transport=transport,
        encryption=encryption,
        header_type=header_type,
        extra=extra,
    )


def parse_vless_list(text: str) -> tuple[list[VlessNode], list[tuple[int, str, str]]]:
    """Parse a newline-delimited list of VLESS URLs tolerantly.

    Blank lines and comment lines (leading ``#``) are skipped. Malformed lines
    do not abort the run — they are collected and returned as the second tuple
    element so the caller can log or persist the parse errors.

    Returns a tuple ``(nodes, errors)`` where ``errors`` is a list of
    ``(line_number, raw_line, reason)`` triples (1-indexed line numbers,
    matching what a human sees in an editor).
    """
    if text is None:
        return [], []

    nodes: list[VlessNode] = []
    errors: list[tuple[int, str, str]] = []

    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            nodes.append(parse_vless_url(line))
        except VlessParseError as exc:
            errors.append((lineno, raw_line, str(exc)))
        except Exception as exc:  # noqa: BLE001 — defensive; never crash a batch
            errors.append((lineno, raw_line, f"unexpected: {exc!r}"))

    return nodes, errors
