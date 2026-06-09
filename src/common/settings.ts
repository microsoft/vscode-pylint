// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

// Extension-specific settings: ISettings type extension and legacy settings logging.
// All shared settings resolution is handled by @vscode/common-python-lsp directly.

import {
    IBaseSettings,
    getConfiguration,
    getWorkspaceFolders,
    logLegacySettings as _logLegacySettings,
    traceWarn,
} from '@vscode/common-python-lsp';

export interface ISettings extends IBaseSettings {
    enabled: boolean;
    severity: Record<string, string>;
    path: string[];
    ignorePatterns: string[];
    lintOnChange: boolean;
}

export function logLegacySettings(): void {
    // Handle pylintEnabled separately — it has custom messaging not covered
    // by the shared helper's simple "use X instead" pattern.
    getWorkspaceFolders().forEach((workspace) => {
        try {
            const legacyConfig = getConfiguration('python', workspace.uri);
            const legacyPylintEnabled = legacyConfig.get<boolean>('linting.pylintEnabled', false);
            const legacyPylintPath = legacyConfig.get<string>('linting.pylintPath', '');
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
            if (legacyPylintPath.length > 0 && legacyPylintPath !== 'pylint') {
                traceWarn(`"python.linting.pylintPath" is deprecated. Use "pylint.path" instead.`);
                traceWarn(`"python.linting.pylintPath" value for workspace ${workspace.uri.fsPath}:`);
                traceWarn(`\n${JSON.stringify(legacyPylintPath, null, 4)}`);
            }
        } catch (err) {
            traceWarn(`Error while logging legacy settings: ${err}`);
        }
    });

    // Standard legacy key → new key mappings handled by the shared helper.
    _logLegacySettings('pylint', [
        { legacyKey: 'linting.cwd', newKey: 'cwd' },
        { legacyKey: 'linting.pylintArgs', newKey: 'args', isArray: true },
    ]);
}
