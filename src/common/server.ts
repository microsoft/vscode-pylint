// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import { Disposable, l10n, LanguageStatusSeverity, LogOutputChannel } from 'vscode';
import { State } from 'vscode-languageclient';
import { LanguageClient } from 'vscode-languageclient/node';
import { IBaseSettings, restartServer as _restartServer } from '@vscode/common-python-lsp';
import { PYLINT_TOOL_CONFIG } from './constants';
import { traceError, traceVerbose } from './logging';
import { ISettings, isLintOnChangeEnabled } from './settings';
import { getLSClientTraceLevel } from './utilities';
import { updateScore, updateStatus } from './status';

// Lazy-initialized PythonEnvironmentsProvider
import { PythonEnvironmentsProvider } from '@vscode/common-python-lsp';

let _provider: PythonEnvironmentsProvider | undefined;
export function getPythonProvider(): PythonEnvironmentsProvider {
    if (!_provider) {
        _provider = new PythonEnvironmentsProvider(PYLINT_TOOL_CONFIG);
    }
    return _provider;
}

let _disposables: Disposable[] = [];

export async function restartServer(
    workspaceSetting: ISettings,
    serverId: string,
    serverName: string,
    outputChannel: LogOutputChannel,
    oldLsClient?: LanguageClient,
): Promise<LanguageClient | undefined> {
    _disposables.forEach((d) => {
        try {
            d.dispose();
        } catch (ex) {
            traceError(`Failed to dispose: ${ex}`);
        }
    });
    _disposables = [];
    updateStatus(undefined, LanguageStatusSeverity.Information, true);

    // Build extra env vars including VSCODE_PYLINT_LINT_ON_CHANGE
    const toolConfig = { ...PYLINT_TOOL_CONFIG };
    if (isLintOnChangeEnabled(serverId)) {
        toolConfig.extraEnvVars = {
            ...toolConfig.extraEnvVars,
            VSCODE_PYLINT_LINT_ON_CHANGE: '1',
        };
    }

    const result = await _restartServer(
        {
            settings: workspaceSetting as unknown as IBaseSettings,
            serverId,
            serverName,
            outputChannel,
            toolConfig,
            pythonProvider: getPythonProvider(),
        },
        oldLsClient,
    );

    _disposables = result.disposables;
    const newLSClient = result.client;

    if (!newLSClient) {
        updateStatus(l10n.t('Server failed to start.'), LanguageStatusSeverity.Error);
        return undefined;
    }

    // Register pylint-specific notification handlers
    _disposables.push(
        newLSClient.onNotification('pylint/score', (params: { uri: string; score: number }) => {
            updateScore(params.uri, params.score);
        }),
    );
    _disposables.push(
        newLSClient.onNotification('pylint/lintingStarted', (params: { uri: string }) => {
            updateScore(params.uri, undefined);
        }),
    );
    _disposables.push(
        newLSClient.onNotification('pylint/lintingFailed', (params: { uri: string }) => {
            updateScore(params.uri, -1);
        }),
    );
    _disposables.push(
        newLSClient.onDidChangeState((e) => {
            switch (e.newState) {
                case State.Stopped:
                    traceVerbose(`Server State: Stopped`);
                    break;
                case State.Starting:
                    traceVerbose(`Server State: Starting`);
                    break;
                case State.Running:
                    traceVerbose(`Server State: Running`);
                    updateStatus(undefined, LanguageStatusSeverity.Information, false);
                    break;
            }
        }),
    );

    try {
        const { env } = await import('vscode');
        await newLSClient.setTrace(getLSClientTraceLevel(outputChannel.logLevel, env.logLevel));
    } catch (ex) {
        traceError(`Server: Failed to set trace level: ${ex}`);
    }

    return newLSClient;
}
