// Builds the shared package that lives in the git submodule after install.
//
// Note: a clone made without `--recurse-submodules` actually fails earlier,
// when npm resolves the `file:` dependency during the install phase, before
// this postinstall script runs. The guard below only adds a friendlier message
// on the rarer paths that still reach postinstall (e.g. the submodule was
// removed after a prior install); it is not a substitute for initializing the
// submodule.
const { existsSync } = require("fs");
const { execSync } = require("child_process");

const pkgDir = "external/vscode-common-python-lsp/typescript";

if (!existsSync(`${pkgDir}/package.json`)) {
  console.warn(
    `[postinstall] Shared package submodule not found at "${pkgDir}". ` +
      "Run `git submodule update --init --recursive` and reinstall to build it.",
  );
  process.exit(0);
}

// Already built (e.g. by a prior install or the packaging pipeline); nothing to do.
if (existsSync(`${pkgDir}/dist/index.js`)) {
  process.exit(0);
}

// Root npm installs do not bring along the submodule's devDependencies, so
// install the shared package when its TypeScript toolchain is missing.
if (
  !existsSync(`${pkgDir}/node_modules/.bin/tsc`) &&
  !existsSync(`${pkgDir}/node_modules/.bin/tsc.cmd`) &&
  !existsSync(`${pkgDir}/node_modules/typescript`)
) {
  execSync(`npm --prefix ${pkgDir} ci`, { stdio: "inherit" });
}

execSync(`npm --prefix ${pkgDir} run build`, { stdio: "inherit" });
