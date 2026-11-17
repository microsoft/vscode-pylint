Please see [our wiki](https://github.com/microsoft/vscode-pylint/wiki) on how to contribute to this project.

## Building the pinned shared runtime

Use the Node version in `.nvmrc`, initialize the Git submodule, then run
`npm run setup` and `npm run compile`. Setup installs Python tools in `.venv`
and bundles the Python library from `external/vscode-common-python-lsp/python`
via `nox --session install_bundled_libs`. No shared npm or PyPI package is used.
The compile, watch, test-compilation and production-package commands first
build the same checkout's `typescript/dist` public entry point; webpack bundles
it and its runtime dependencies into `dist/extension.js`. Re-run setup after
changing the shared pin to refresh the bundled Python library too.

Run `npm run test:runtime` for headless activation/launch-hook regressions,
`npm run pretest && npm run tests` for extension-host tests, and
`npm run vsce-package` to build a VSIX after setup. For manual testing, open
this checkout in VS Code, select **Debug Extension Only** and press F5. Open a
Python file in the Extension Development Host, then check diagnostics, score
updates and toggling `pylint.lintOnChange` across server restarts. Returning from
activation is not a client-ready signal; wait for Pylint's startup log.
