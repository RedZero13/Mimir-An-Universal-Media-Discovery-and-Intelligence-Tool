#!/usr/bin/env python3
"""Builds dist/mimir-vault.zip (upload as a plugin) and dist/mimir-vault-snippet.php (paste into a code-snippets plugin).

    python3 wordpress/build.py

Both come from the same file, wordpress/mimir-vault/mimir-vault.php. Nothing in dist/ is committed.
"""

import re
import zipfile
from pathlib import Path

HERE = Path(__file__).parent
SRC = HERE / "mimir-vault" / "mimir-vault.php"
DIST = HERE / "dist"


def main() -> None:
    DIST.mkdir(exist_ok=True)
    code = SRC.read_text()
    zip_path = DIST / "mimir-vault.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("mimir-vault/mimir-vault.php", code)
    # Snippet plugins add the opening tag themselves and run the code inside WordPress, so drop both the tag and the
    # plugin header, and the ABSPATH guard they already provide.
    snippet = re.sub(r"\A<\?php\s*/\*\*.*?\*/\s*", "", code, count=1, flags=re.S)
    snippet = re.sub(r"if \( ! defined\( 'ABSPATH' \) \) \{\s*exit;\s*\}\s*", "", snippet, count=1)
    (DIST / "mimir-vault-snippet.php").write_text("// Mimir Vault 0.1.0 (snippet form). Source: wordpress/mimir-vault/mimir-vault.php\n" + snippet)
    print(f"wrote {zip_path} and {DIST / 'mimir-vault-snippet.php'}")


if __name__ == "__main__":
    main()
