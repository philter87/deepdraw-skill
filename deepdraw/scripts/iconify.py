#!/usr/bin/env python3
"""Find icons on the public Iconify API, in the form a DeepDraw node wants.

DeepDraw's own icon picker calls the same two endpoints, and stores what comes
back verbatim in the node's `href` — raw `<svg>` markup, not a URL — so an
exported drawing keeps its icons with no network behind it.

    python3 iconify.py search database            # names, one per line
    python3 iconify.py search database --sets material-symbols,lucide
    python3 iconify.py get material-symbols:database        # the SVG markup
    python3 iconify.py get material-symbols:database --node # a spec node

Search ranks whole icon sets ahead of single glyphs, so pass `--sets` when a
drawing should keep one visual family throughout.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.iconify.design"
TIMEOUT = 20


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "deepdraw-skill"})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read()


def search(query: str, limit: int, sets: list[str] | None, api: str) -> list[str]:
    params = {"query": query, "limit": str(max(32, limit))}
    if sets:
        params["prefixes"] = ",".join(sets)
    url = f"{api}/search?{urllib.parse.urlencode(params)}"
    data = json.loads(_get(url))
    return (data.get("icons") or [])[:limit]


def fetch(name: str, api: str) -> str:
    """The icon's SVG markup. Iconify returns `width/height="1em"` and
    `fill="currentColor"`, which is exactly what DeepDraw scales into the
    node's box and recolours with the node's `textColor`."""
    prefix, _, rest = name.partition(":")
    if not rest:
        raise SystemExit(f"{name!r} is not a 'prefix:name' icon id")
    markup = _get(f"{api}/{prefix}/{urllib.parse.quote(rest)}.svg").decode("utf-8").strip()
    if not markup.startswith("<svg"):
        raise SystemExit(f"{name!r} did not come back as an SVG")
    return markup


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--api", default=API, help="an Iconify-compatible API base URL")
    sub = parser.add_subparsers(dest="command", required=True)

    s = sub.add_parser("search", help="find icon names")
    s.add_argument("query")
    s.add_argument("--limit", type=int, default=24)
    s.add_argument("--sets", help="comma-separated icon set prefixes, e.g. material-symbols,lucide")

    g = sub.add_parser("get", help="fetch one icon's SVG markup")
    g.add_argument("name", help="prefix:name, e.g. material-symbols:database")
    g.add_argument("--node", action="store_true", help="print a ready spec node instead of raw markup")
    g.add_argument("--size", type=int, default=64, help="node width and height (default 64)")
    g.add_argument("--label", default="", help="label drawn below the icon")

    args = parser.parse_args()
    try:
        if args.command == "search":
            names = search(args.query, args.limit, args.sets.split(",") if args.sets else None, args.api)
            if not names:
                print(f"no icons matched {args.query!r}", file=sys.stderr)
                return 1
            print("\n".join(names))
            return 0

        markup = fetch(args.name, args.api)
        if not args.node:
            print(markup)
            return 0
        node = {
            "id": args.name.replace(":", "-"),
            "type": "icon",
            "x": 0, "y": 0, "w": args.size, "h": args.size,
            "text": args.label,
            "href": markup,
        }
        print(json.dumps(node, ensure_ascii=False, indent=2))
        return 0
    except urllib.error.URLError as error:
        print(f"iconify unreachable: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
