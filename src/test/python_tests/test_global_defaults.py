# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Unit tests for _get_global_defaults() in lsp_server.

Validates that global settings are correctly read (or hardcoded) in the
pylint extension.  Mock setup is provided by conftest.py (setup_lsp_mocks).
"""

# pylint: disable=protected-access
import lsp_server
import pytest


def _with_global_settings(overrides, func):
    """Run *func* with GLOBAL_SETTINGS temporarily set to *overrides*."""
    original = lsp_server.GLOBAL_SETTINGS.copy()
    try:
        lsp_server.GLOBAL_SETTINGS.clear()
        lsp_server.GLOBAL_SETTINGS.update(overrides)
        return func()
    finally:
        lsp_server.GLOBAL_SETTINGS.clear()
        lsp_server.GLOBAL_SETTINGS.update(original)


@pytest.mark.parametrize(
    "overrides, key, expected",
    [
        pytest.param({}, "ignorePatterns", [], id="ignorePatterns-default"),
        pytest.param(
            {"ignorePatterns": ["**/vendor/**", "**/.tox/**"]},
            "ignorePatterns",
            [],
            id="ignorePatterns-hardcoded-empty",
        ),
        pytest.param(
            {"showNotifications": "always"},
            "showNotifications",
            "always",
            id="showNotifications-set",
        ),
        pytest.param(
            {"importStrategy": "fromEnvironment"},
            "importStrategy",
            "fromEnvironment",
            id="importStrategy-set",
        ),
    ],
)
def test_global_defaults_setting(overrides, key, expected):
    """Each global setting is correctly read or defaults when absent."""
    result = _with_global_settings(overrides, lsp_server._get_global_defaults)
    assert result[key] == expected
