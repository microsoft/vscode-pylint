// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import * as dotenv from 'dotenv';
import * as fsapi from 'fs-extra';
import { Disposable, env, l10n, LanguageStatusSeverity, LogOutputChannel, Uri } from 'vscode';
import { State } from 'vscode-languageclient';
import {
    LanguageClient,
    LanguageClientOptions,
    RevealOutputChannelOn,
    ServerOptions,
} from 'vscode-languageclient/node';
import { DEBUG_SERVER_SCRIPT_PATH, SERVER_SCRIPT_PATH } from './constants';
import { traceError, traceInfo, traceVerbose } from './logging';
import { getDebuggerPath } from './python';
import { getExtensionSettings, getGlobalSettings, ISettings, isLintOnChangeEnabled } from './settings';
import { getLSClientTraceLevel, getDocumentSelector } from './utilities';
import { updateScore, updateStatus } from './status';
import { getConfiguration } from './vscodeapi';

export type IInitOptions = { settings: ISettings[]; globalSettings: ISettings };

async function loadEnvVarsFromFile(workspace: Uri): Promise<Record<string, string>> {
    const pythonConfig = getConfiguration('python', workspace);
    let envFileSetting = pythonConfig.get<string>('envFile', '${workspaceFolder}/.env');
    envFileSetting = envFileSetting.replace('${workspaceFolder}', workspace.fsPath);

    if (!envFileSetting || !(await fsapi.pathExists(envFileSetting))) {
        return {};
    }

    try {
        const content = await fsapi.readFile(envFileSetting, 'utf-8');
        traceInfo(`Loaded environment variables from ${envFileSetting}`);
        return dotenv.parse(content);
    } catch (ex) {
        traceError(`Failed to read env file ${envFileSetting}: ${ex}`);
        return {};
    }
}

async function createServer(
    settings: ISettings,
    serverId: string,
    serverName: string,
    outputChannel: LogOutputChannel,
    initializationOptions: IInitOptions,
): Promise<LanguageClient> {
    const command = settings.interpreter[0];
    const cwd = settings.cwd === '${fileDirname}' ? Uri.parse(settings.workspace).fsPath : settings.cwd;

    // Set debugger path needed for debugging Python code.
    const newEnv = { ...process.env };

    // Load environment variables from the envFile (python.envFile setting)
    const workspaceUri = Uri.parse(settings.workspace);
    const envFileVars = await loadEnvVarsFromFile(workspaceUri);
    Object.assign(newEnv, envFileVars);

    const debuggerPath = await getDebuggerPath();
    const isDebugScript = await fsapi.pathExists(DEBUG_SERVER_SCRIPT_PATH);
    if (newEnv.USE_DEBUGPY && debuggerPath) {
        newEnv.DEBUGPY_PATH = debuggerPath;
    } else {
        newEnv.USE_DEBUGPY = 'False';
    }

    // Set import strategy
    newEnv.LS_IMPORT_STRATEGY = settings.importStrategy;

    // Set notification type
    newEnv.LS_SHOW_NOTIFICATION = settings.showNotifications;

    newEnv.PYTHONUTF8 = '1';

    if (isLintOnChangeEnabled(serverId)) {
        newEnv.VSCODE_PYLINT_LINT_ON_CHANGE = '1';
    }

    const args =
        newEnv.USE_DEBUGPY === 'False' || !isDebugScript
            ? settings.interpreter.slice(1).concat([SERVER_SCRIPT_PATH])
            : settings.interpreter.slice(1).concat([DEBUG_SERVER_SCRIPT_PATH]);
    traceInfo(`Server run command: ${[command, ...args].join(' ')}`);

    const serverOptions: ServerOptions = {
        command,
        args,
        options: { cwd, env: newEnv },
    };

    // Options to control the language client
    const clientOptions: LanguageClientOptions = {
        // Register the server for Python documents
        documentSelector: getDocumentSelector(),
        outputChannel: outputChannel,
        traceOutputChannel: outputChannel,
        revealOutputChannelOn: RevealOutputChannelOn.Never,
        initializationOptions,
    };

    return new LanguageClient(serverId, serverName, serverOptions, clientOptions);
}

let _disposables: Disposable[] = [];
export async function restartServer(
    workspaceSetting: ISettings,
    serverId: string,
    serverName: string,
    outputChannel: LogOutputChannel,
    oldLsClient?: LanguageClient,
): Promise<LanguageClient | undefined> {
    if (oldLsClient) {
        traceInfo(`Server: Stop requested`);
        try {
            await oldLsClient.stop();
        } catch (ex) {
            traceError(`Server: Stop failed: ${ex}`);
        }
    }
    _disposables.forEach((d) => d.dispose());
    _disposables = [];
    updateStatus(undefined, LanguageStatusSeverity.Information, true);

    const newLSClient = await createServer(workspaceSetting, serverId, serverName, outputChannel, {
        settings: await getExtensionSettings(serverId, true),
        globalSettings: await getGlobalSettings(serverId, false),
    });

    traceInfo(`Server: Start requested.`);
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
            updateScore(params.uri, -1); // Show -1 score if linting failed, as we won't have a valid score to display.
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
        await newLSClient.start();
    } catch (ex) {
        updateStatus(l10n.t('Server failed to start.'), LanguageStatusSeverity.Error);
        traceError(`Server: Start failed: ${ex}`);
        return undefined;
    }

    try {
        await newLSClient.setTrace(getLSClientTraceLevel(outputChannel.logLevel, env.logLevel));
    } catch (ex) {
        traceError(`Server: Failed to set trace level: ${ex}`);
    }

    return newLSClient;
}
