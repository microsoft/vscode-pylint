# Pylint extension for Visual Studio Code

A Visual Studio Code extension with support for the `pylint` linter. The extension ships with `pylint=2.12.2`.

## Settings

| Settings              | Default                                                                                                                                | Description                                                                                                                                                                                                                                                                                                              |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| python.pylintArgs     | `[]`                                                                                                                                   | Custom arguments passed to `pylint`. E.g `"python.pylintArgs" = ["--rcfile=<file>"]`                                                                                                                                                                                                                                     |
| python.pylintSeverity | `{ "convention": "Information", "error": "Error", "fatal": "Error", "refactor": "Hint", "warning": "Warning", "info": "Information" }` | Controls mapping of severity from `pylint` to VS Code severity when displaying in the problems window. You can override specific `pylint` error codes `{ "convention": "Information", "error": "Error", "fatal": "Error", "refactor": "Hint", "warning": "Warning", "W0611": "Error", "undefined-variable": "Warning" }` |
| python.pylintTrace    | `error`                                                                                                                                | Sets the tracing level for the extension.                                                                                                                                                                                                                                                                                |
| python.pylintPath     | `[]`                                                                                                                                   | Setting to provide custom `pylint` executable. Example 1: `["~/global_env/pylint"]` Example 2: `["conda", "run", "-n", "lint_env", "python", "-m", "pylint"]`                                                                                                                                                            |

## Commands

| Command                | Description                       |
| ---------------------- | --------------------------------- |
| Pylint: Restart Linter | Force re-start the linter server. |
