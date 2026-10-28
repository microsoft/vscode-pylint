# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import datetime

import pytest
import update_python_versions

NOW = datetime.datetime(2026, 8, 2, tzinfo=datetime.timezone.utc)
RELEASES = [
    {
        "name": "Python 3.15.0rc1",
        "release_date": "2020-08-01T00:00:00Z",
        "is_published": True,
        "pre_release": True,
        "version": 3,
    }
]


@pytest.mark.parametrize("version", ["3.15", "3.15.1", "3.15-dev", "3.15.0rc1"])
def test_configured_versions_compares_major_minor(tmp_path, version):
    workflow = tmp_path / "pr-check.yml"
    workflow.write_text(f"python: ['{version}']\n", encoding="utf-8")

    assert update_python_versions.configured_versions(workflow) == {"3.15"}


@pytest.mark.parametrize(
    "pr_version, push_version, expected",
    [
        ("3.14", "3.14", "3.15"),
        ("3.15", "3.14", "3.15"),
        ("3.14", "3.15", "3.15"),
        ("3.15", "3.15", None),
        ("3.15.1", "3.15.0-rc.2", None),
        ("3.150", "3.15", "3.15"),
    ],
)
def test_unconfigured_version(tmp_path, pr_version, push_version, expected):
    workflows = [tmp_path / name for name in ("pr-check.yml", "push-check.yml")]
    for workflow, version in zip(workflows, (pr_version, push_version)):
        workflow.write_text(f"python: ['{version}']\n", encoding="utf-8")

    assert (
        update_python_versions.unconfigured_version(RELEASES, workflows, NOW)
        == expected
    )


@pytest.mark.parametrize(
    "push_version, expected", [("3.14", "3.15\n"), ("3.15-dev", "")]
)
def test_main_checks_both_matrices(
    tmp_path, monkeypatch, capsys, push_version, expected
):
    workflow_dir = tmp_path / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)
    (workflow_dir / "pr-check.yml").write_text("python: ['3.15.1']\n", encoding="utf-8")
    (workflow_dir / "push-check.yml").write_text(
        f"python: ['{push_version}']\n", encoding="utf-8"
    )
    monkeypatch.setattr(
        update_python_versions,
        "__file__",
        str(tmp_path / "build" / "update_python_versions.py"),
    )
    monkeypatch.setattr(update_python_versions, "fetch_releases", lambda: RELEASES)

    update_python_versions.main()

    assert capsys.readouterr().out == expected
