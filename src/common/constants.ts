// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import * as path from 'path';
import { resolveExtensionRoot, ToolConfig } from '@vscode/common-python-lsp';

export const EXTENSION_ROOT_DIR = resolveExtensionRoot(__dirname);

export const PYLINT_CONFIG_FILES = ['.pylintrc', 'pylintrc', 'pyproject.toml', 'setup.cfg', 'tox.ini'];

/* eslint-disable @typescript-eslint/naming-convention */
export const PYLINT_TOOL_CONFIG: ToolConfig = {
    toolId: 'pylint',
    toolDisplayName: 'Pylint',
    toolModule: 'pylint',
    minimumPythonVersion: { major: 3, minor: 10 },
    configFiles: PYLINT_CONFIG_FILES,
    serverScript: path.join(EXTENSION_ROOT_DIR, 'bundled', 'tool', 'lsp_server.py'),
    debugServerScript: path.join(EXTENSION_ROOT_DIR, 'bundled', 'tool', '_debug_server.py'),
    pythonUtf8: true,
    settingsDefaults: {
        enabled: true,
        severity: {
            convention: 'Information',
            error: 'Error',
            fatal: 'Error',
            refactor: 'Hint',
            warning: 'Warning',
            info: 'Information',
        },
        ignorePatterns: [],
        lintOnChange: false,
    },
    trackedSettings: [
        'args',
        'cwd',
        'enabled',
        'severity',
        'path',
        'interpreter',
        'importStrategy',
        'showNotifications',
        'ignorePatterns',
        'lintOnChange',
    ],
};
