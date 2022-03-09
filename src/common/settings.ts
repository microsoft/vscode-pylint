// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import { ConfigurationChangeEvent } from 'vscode';
import { LoggingLevelSettingType } from './types';
import { getConfiguration } from './vscodeapi';

export interface ISettings {
    trace: LoggingLevelSettingType;
    args: string[];
    severity: Record<string, string>;
    path: string[];
}

export function getLinterExtensionSettings(moduleName: string): ISettings {
    const config = getConfiguration('python');
    return {
        trace: config.get<LoggingLevelSettingType>(`${moduleName}Trace`) ?? 'error',
        args: config.get<string[]>(`${moduleName}Args`) ?? [],
        severity: config.get<Record<string, string>>(`${moduleName}Severity`) ?? {},
        path: config.get<string[]>(`${moduleName}Path`) ?? [],
    };
}

export function checkIfConfigurationChanged(e: ConfigurationChangeEvent, moduleName: string): boolean {
    const settings = [
        `python.${moduleName}Trace`,
        `python.${moduleName}Args`,
        `python.${moduleName}Severity`,
        `python.${moduleName}Path`,
    ];
    const changed = settings.map((s) => e.affectsConfiguration(s));
    return changed.includes(true);
}
