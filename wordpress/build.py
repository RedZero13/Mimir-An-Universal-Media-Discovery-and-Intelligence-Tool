#!/usr/bin/env python3
"""Builds, for each plugin here, dist/<name>.zip (upload as a plugin) and dist/<name>-snippet.php (paste into a code-snippets plugin).

    python3 wordpress/build.py

Both come from the same file, wordpress/<name>/<name>.php. Nothing in dist/ is committed.
"""

import re
import zipfile
from pathlib import Path

HERE = Path(__file__).parent
DIST = HERE / "dist"
PLUGINS = [("mimir-vault", "Mimir Vault 0.2.0"), ("terratales-indexing", "Terratales Indexing Fixes 0.1.0")]


def build(slug: str, label: str) -> None:
    code = (HERE / slug / f"{slug}.php").read_text()
    zip_path = DIST / f"{slug}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{slug}/{slug}.php", code)
    # Snippet plugins add the opening tag themselves and run the code inside WordPress, so drop both the tag and the
    # plugin header, and the ABSPATH guard they already provide.
    snippet = re.sub(r"\A<\?php\s*/\*\*.*?\*/\s*", "", code, count=1, flags=re.S)
    snippet = re.sub(r"if \( ! defined\( 'ABSPATH' \) \) \{\s*exit;\s*\}\s*", "", snippet, count=1)
    (DIST / f"{slug}-snippet.php").write_text(f"// {label} (snippet form). Source: wordpress/{slug}/{slug}.php\n" + snippet)
    print(f"wrote {zip_path} and {DIST / f'{slug}-snippet.php'}")


def main() -> None:
    DIST.mkdir(exist_ok=True)
    for slug, label in PLUGINS:
        build(slug, label)


if __name__ == "__main__":
    main()
