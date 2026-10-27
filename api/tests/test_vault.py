"""Accounts: the browser crypto, and the WordPress plugin that stores the encrypted vaults."""

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
PLUGIN = ROOT / "wordpress" / "mimir-vault" / "mimir-vault.php"

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="node is not installed")
needs_php = pytest.mark.skipif(not shutil.which("php"), reason="php is not installed")


@needs_node
def test_vault_crypto_round_trip_and_merge():
    r = subprocess.run(["node", str(ROOT / "demo" / "vault.test.cjs")], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr


@needs_php
def test_plugin_lints_and_passes_the_contract_tests():
    assert subprocess.run(["php", "-l", str(PLUGIN)], capture_output=True).returncode == 0
    r = subprocess.run(["php", str(ROOT / "wordpress" / "tests" / "harness.php")], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr


@needs_php
def test_build_makes_a_plugin_zip_and_a_snippet_that_both_lint(tmp_path):
    subprocess.run([sys.executable, str(ROOT / "wordpress" / "build.py")], check=True, capture_output=True)
    dist = ROOT / "wordpress" / "dist"
    with zipfile.ZipFile(dist / "mimir-vault.zip") as z:
        assert z.namelist() == ["mimir-vault/mimir-vault.php"]
    snippet = tmp_path / "snippet.php"
    snippet.write_text("<?php\n" + (dist / "mimir-vault-snippet.php").read_text())
    assert subprocess.run(["php", "-l", str(snippet)], capture_output=True).returncode == 0
    assert "Plugin Name" not in snippet.read_text()
