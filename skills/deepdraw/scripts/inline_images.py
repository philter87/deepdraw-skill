"""Turn every picture an `image` node points at into the bytes themselves.

A spec may write an `image` node's `href` three ways, and only the first
survives on its own:

    "href": "data:image/png;base64,iVBORw0…"   already the bytes
    "href": "./diagrams/logo.png"               a file beside the spec
    "href": "https://example.com/logo.png"      an address

This module rewrites the second and third into the first, so what
`build_html.py` writes is one file that needs nothing else. That is not tidiness.
A drawing that references a picture somewhere else loses it three separate ways:

- **On deepdraw.ai.** The page's `img-src` is `'self' data: blob:`, so an
  address on somebody else's origin is refused by the browser and the shape
  draws as an empty frame. A file that looked right on a disk quietly loses its
  pictures the moment it is imported.
- **In a PNG export.** An SVG rasterized through an `<img>` loads no external
  references at all, so the picture is missing from the export with no error to
  notice. Re-inlining first is the only thing that puts it there.
- **In time.** A drawing is a thing people keep and send on. One that depends on
  a stranger's server working is a drawing with a hole in it later.

`deepdraw_doc.py` deliberately never touches the network or the disk, which is
why this is a module of its own rather than another step in `build_document`.
"""

from __future__ import annotations

import base64
import urllib.error
import urllib.request
from pathlib import Path

#: Matches what deepdraw.ai's own upload endpoint accepts, so a drawing built
#: here holds nothing the app would have refused. SVG is absent from both for
#: the same reason: an `icon` node takes inline `<svg>` markup and is the right
#: home for a vector glyph.
MAGIC: list[tuple[str, object]] = [
    ("image/png", lambda b: b.startswith(b"\x89PNG\r\n\x1a\n")),
    ("image/jpeg", lambda b: b.startswith(b"\xff\xd8\xff")),
    ("image/gif", lambda b: b.startswith(b"GIF87a") or b.startswith(b"GIF89a")),
    ("image/webp", lambda b: b.startswith(b"RIFF") and b[8:12] == b"WEBP"),
    ("image/avif", lambda b: b[4:8] == b"ftyp" and (b"avif" in b[8:64] or b"avis" in b[8:64])),
]

#: Past this, one picture is most of the file. Not refused — a photograph is
#: sometimes the point — but said out loud, because the drawing has to travel.
LARGE_IMAGE_BYTES = 2 * 1024 * 1024

#: Refused. The standalone HTML carries the library already, and a document this
#: big is one nobody can mail, and one deepdraw.ai will not take from an
#: anonymous account (5 MB of image storage; 50 MB signed in).
MAX_IMAGE_BYTES = 10 * 1024 * 1024

TIMEOUT_SECONDS = 20

# Some hosts (Wikimedia among them) answer a 400 to a client that introduces
# itself as Python. Saying what this is costs nothing and works.
USER_AGENT = "deepdraw-skill (+https://github.com/philter87/deepdraw-skill)"


class ImageError(Exception):
    """A picture the spec asked for that could not be turned into bytes."""


def sniff(content: bytes) -> str | None:
    """The content type these bytes really are, or None for anything else."""
    for content_type, matches in MAGIC:
        if matches(content):  # type: ignore[operator]
            return content_type
    return None


def inline_images(document: dict, base_dir: Path) -> list[str]:
    """Rewrites every `image` href in place. Returns warnings; raises on failure.

    Paths are resolved against `base_dir`, which is the spec file's own
    directory — so a spec can say `./logo.png` and mean the file beside it,
    wherever the build is run from.
    """
    warnings: list[str] = []
    # Two shapes may point at the same picture, and it is fetched once.
    resolved: dict[str, str] = {}
    total = 0

    for node_id, node in document.get("nodes", {}).items():
        if node.get("type") != "image":
            continue
        href = (node.get("href") or "").strip()
        if not href or href.startswith("data:"):
            continue

        if href not in resolved:
            try:
                content = _read_remote(href) if _is_url(href) else _read_file(href, base_dir)
            except ImageError as error:
                raise ImageError(f"{node_id!r}: {error}") from None

            content_type = sniff(content)
            if content_type is None:
                raise ImageError(
                    f"{node_id!r}: {href} is not a PNG, JPEG, GIF, WebP or AVIF image. "
                    "For a vector glyph use an `icon` node, which takes inline <svg> markup."
                )
            if len(content) > MAX_IMAGE_BYTES:
                raise ImageError(
                    f"{node_id!r}: {href} is {_size(len(content))}, past the "
                    f"{_size(MAX_IMAGE_BYTES)} one picture may be. Scale it down first."
                )
            if len(content) > LARGE_IMAGE_BYTES:
                warnings.append(
                    f"{node_id!r}: {href} is {_size(len(content))}, so the drawing "
                    "carries it in full. Scaling it down makes the file easier to send."
                )

            resolved[href] = f"data:{content_type};base64,{base64.b64encode(content).decode('ascii')}"
            total += len(content)

        node["href"] = resolved[href]

    # The whole point of the 5 MB line is that it is the anonymous ceiling on
    # deepdraw.ai, which is where most of these drawings are opened.
    if total > 5 * 1024 * 1024:
        warnings.append(
            f"the drawing carries {_size(total)} of pictures. deepdraw.ai gives an "
            "anonymous browser 5 MB of image storage (50 MB signed in), so import "
            "this one signed in, or use fewer and smaller pictures."
        )

    return warnings


def _is_url(href: str) -> bool:
    return href.startswith("http://") or href.startswith("https://")


def _read_remote(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "image/*"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            # One byte past the ceiling is enough to know it is over it, and
            # stops a URL that streams forever from filling this process.
            return response.read(MAX_IMAGE_BYTES + 1)
    except urllib.error.HTTPError as error:
        raise ImageError(f"{url} answered {error.code} {error.reason}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise ImageError(f"{url} could not be fetched ({error})") from None


def _read_file(href: str, base_dir: Path) -> bytes:
    path = Path(href).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    try:
        return path.read_bytes()
    except OSError as error:
        raise ImageError(f"{href} could not be read ({error.strerror or error})") from None


def _size(count: int) -> str:
    if count >= 1024 * 1024:
        return f"{count / (1024 * 1024):.1f} MB"
    return f"{count / 1024:.0f} KB"
