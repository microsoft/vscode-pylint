// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import { Disposable, OutputChannel } from 'vscode';
import { State } from 'vscode-languageclient';
import {
    LanguageClient,
    LanguageClientOptions,
    RevealOutputChannelOn,
    ServerOptions,
} from 'vscode-languageclient/node';
import { LINTER_SCRIPT_PATH } from './constants';
import { traceInfo, traceVerbose } from './logging';
import { ISettings } from './settings';
import { traceLevelToLSTrace } from './utilities';
import { isVirtualWorkspace } from './vscodeapi';

export type ILinterInitOptions = { settings: ISettings };

export async function createLinterServer(
    interpreter: string,
    serverName: string,
    outputChannel: OutputChannel,
    initializationOptions: ILinterInitOptions,
): Promise<LanguageClient> {
    const serverOptions: ServerOptions = {
        command: interpreter,
        args: [LINTER_SCRIPT_PATH],
    };

    // Options to control the language client
    const clientOptions: LanguageClientOptions = {
        // Register the server for python documents
        documentSelector: isVirtualWorkspace()
            ? [{ language: 'python' }]
            : [
                  { scheme: 'file', language: 'python' },
                  { scheme: 'untitled', language: 'python' },
                  { scheme: 'vscode-notebook', language: 'python' },
                  { scheme: 'vscode-notebook-cell', language: 'python' },
                  { scheme: 'vscode-interactive-input', language: 'python' },
              ],
        outputChannel: outputChannel,
        traceOutputChannel: outputChannel,
        revealOutputChannelOn: RevealOutputChannelOn.Never,
        initializationOptions,
    };

    return new LanguageClient(serverName, serverName, serverOptions, clientOptions);
}

let _disposables: Disposable[] = [];
export async function restartLinterServer(
    interpreter: string,
    serverName: string,
    outputChannel: OutputChannel,
    initializationOptions: ILinterInitOptions,
    lsClient?: LanguageClient,
): Promise<LanguageClient> {
    if (lsClient) {
        traceInfo(`Server: Stop requested`);
        await lsClient.stop();
        _disposables.forEach((d) => d.dispose());
        _disposables = [];
    }
    const newLSClient = await createLinterServer(interpreter, serverName, outputChannel, initializationOptions);
    newLSClient.trace = traceLevelToLSTrace(initializationOptions.settings.trace);
    traceInfo(`Server: Start requested.`);
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
                    break;
            }
        }),
        newLSClient.start(),
    );
    return newLSClient;
}
