// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

// Extension-specific settings: ISettings type extension and legacy settings logging.
// All shared settings resolution is handled by @vscode/common-python-lsp directly.

import { IBaseSettings, getConfiguration, getWorkspaceFolders, traceWarn } from '@vscode/common-python-lsp';

export interface ISettings extends IBaseSettings {
    enabled: boolean;
    severity: Record<string, string>;
    path: string[];
    ignorePatterns: string[];
    lintOnChange: boolean;
}

export function logLegacySettings(): void {
    getWorkspaceFolders().forEach((workspace) => {
        try {
            const legacyConfig = getConfiguration('python', workspace.uri);

            const legacyPylintEnabled = legacyConfig.get<boolean>('linting.pylintEnabled', false);
            if (legacyPylintEnabled) {
                traceWarn(`"python.linting.pylintEnabled" is deprecated. You can remove that setting.`);
                traceWarn(
                    'The pylint extension is always enabled. However, you can disable it per workspace using the extensions view.',
                );
                traceWarn('You can exclude files and folders using the `python.linting.ignorePatterns` setting.');
                traceWarn(
                    `"python.linting.pylintEnabled" value for workspace ${workspace.uri.fsPath}: ${legacyPylintEnabled}`,
                );
            }

            const legacyCwd = legacyConfig.get<string>('linting.cwd');
            if (legacyCwd) {
                traceWarn(`"python.linting.cwd" is deprecated. Use "pylint.cwd" instead.`);
                traceWarn(`"python.linting.cwd" value for workspace ${workspace.uri.fsPath}: ${legacyCwd}`);
            }

            const legacyArgs = legacyConfig.get<string[]>('linting.pylintArgs', []);
            if (legacyArgs.length > 0) {
                traceWarn(`"python.linting.pylintArgs" is deprecated. Use "pylint.args" instead.`);
                traceWarn(`"python.linting.pylintArgs" value for workspace ${workspace.uri.fsPath}:`);
                traceWarn(`\n${JSON.stringify(legacyArgs, null, 4)}`);
            }

            const legacyPath = legacyConfig.get<string>('linting.pylintPath', '');
            if (legacyPath.length > 0 && legacyPath !== 'pylint') {
                traceWarn(`"python.linting.pylintPath" is deprecated. Use "pylint.path" instead.`);
                traceWarn(`"python.linting.pylintPath" value for workspace ${workspace.uri.fsPath}:`);
                traceWarn(`\n${JSON.stringify(legacyPath, null, 4)}`);
            }
        } catch (err) {
            traceWarn(`Error while logging legacy settings: ${err}`);
        }
    });
}
