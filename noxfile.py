# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import json
import nox
import os
import re


@nox.session(python="3.7")
def bundled_libs_install(session):
    session.install("wheel")
    session.install(
        "-t",
        "./bundled/libs",
        "--no-cache-dir",
        "--implementation",
        "py",
        "--no-deps",
        "--upgrade",
        "-r" "./requirements.txt",
    )


@nox.session()
def tests(session):
    session.install("-r", "src/test/python_tests/requirements.txt")
    session.run("pytest", "src/test/python_tests")

    session.install("freezegun")
    session.run("pytest", "build")


@nox.session()
def lint(session):
    session.install("-r" "./requirements.txt")

    # check linting using the linter from package.json
    package_json_path = os.path.join(os.path.dirname(__file__), "package.json")
    session.log("Reading linter from: {0}".format(package_json_path))

    with open(package_json_path, "r") as f:
        package_json = json.load(f)

    session.install(package_json["linter"]["module"])
    session.run(package_json["linter"]["module"], "./bundled/linter")

    # check formatting using black
    session.install("black")
    session.run("black", "--check", "./bundled/linter")


@nox.session()
def updateBuildNumber(session):
    if len(session.posargs) == 0:
        session.log("No updates to package version")
        return

    package_json_path = os.path.join(os.path.dirname(__file__), "package.json")
    session.log("Reading package.json at: {0}".format(package_json_path))

    with open(package_json_path, "r") as f:
        package_json = json.load(f)

    parts = re.split("\\.|-", package_json["version"])
    major, minor = parts[:2]

    version = "{0}.{1}.{2}".format(major, minor, session.posargs[0])
    version = (
        version if len(parts) == 3 else "{0}-{1}".format(version, "".join(parts[3:]))
    )

    session.log(
        "Updating version from {0} to {1}".format(package_json["version"], version)
    )
    package_json["version"] = version
    with open(package_json_path, "w") as f:
        json.dump(package_json, f, indent=4)
