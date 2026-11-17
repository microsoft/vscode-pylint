# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Tests that bundled package metadata is intact.

The extension ships bundled Python packages in ``bundled/libs/``.
Some packages use ``importlib.metadata`` at runtime to resolve their
version string, which requires the corresponding ``.dist-info``
directory to be present.  These tests verify the metadata was not
accidentally excluded.
"""

import importlib.metadata
import importlib.util
import json
import pathlib
import sys
from urllib.parse import unquote, urlsplit

import pytest

BUNDLED_LIBS = pathlib.Path(__file__).parent.parent.parent.parent / "bundled" / "libs"


@pytest.fixture(autouse=True)
def _ensure_bundled_on_path():
    """Temporarily prepend ``bundled/libs`` to ``sys.path``."""
    libs = str(BUNDLED_LIBS)
    if libs not in sys.path:
        sys.path.insert(0, libs)
        yield
        sys.path.remove(libs)
    else:
        yield


def test_pylint_metadata_version():
    """importlib.metadata must resolve the bundled pylint version."""
    version = importlib.metadata.version("pylint")
    assert version, "pylint version string should not be empty"
    parts = version.split(".")
    assert len(parts) >= 2, f"Unexpected version format: {version}"


def test_common_lsp_package_is_bundled():
    """The server imports this package before it can start."""
    spec = importlib.util.find_spec("vscode_common_python_lsp")
    assert spec is not None
    assert spec.origin is not None
    assert pathlib.Path(spec.origin).is_relative_to(BUNDLED_LIBS)


def test_common_lsp_metadata_matches_local_checkout():
    """The paired runtime must come from the pinned checkout, not a registry."""
    distribution = importlib.metadata.distribution("vscode-python-tool-internal")
    assert (
        pathlib.Path(distribution.locate_file("")).resolve() == BUNDLED_LIBS.resolve()
    )
    direct_url = json.loads(distribution.read_text("direct_url.json"))
    shared = (
        BUNDLED_LIBS.parents[1] / "external" / "vscode-common-python-lsp" / "python"
    )
    origin = urlsplit(direct_url["url"])
    assert origin.scheme == "file"
    assert pathlib.PurePosixPath(unquote(origin.path)).parts[-3:] == (
        "external",
        "vscode-common-python-lsp",
        "python",
    )
    assert "dir_info" in direct_url
    assert not direct_url.get("dir_info", {}).get("editable", False)

    # CI artifacts retain the producer's URI after moving to another checkout.
    installed = BUNDLED_LIBS / "vscode_common_python_lsp"
    source = shared / "vscode_common_python_lsp"
    installed_files = {file.relative_to(installed) for file in installed.rglob("*.py")}
    source_files = {file.relative_to(source) for file in source.rglob("*.py")}
    assert source_files
    assert installed_files == source_files
    for relative in sorted(source_files):
        # Text comparison normalizes checkout-specific line endings only.
        assert (installed / relative).read_text(encoding="utf-8") == (
            source / relative
        ).read_text(encoding="utf-8"), str(relative)
