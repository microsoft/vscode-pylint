// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import { Disposable, Event, EventEmitter, extensions, Uri } from 'vscode';
import { traceError } from './logging';
import { getWorkspaceFolder, getWorkspaceFolders } from './vscodeapi';

interface IExtensionApi {
    ready: Promise<void>;
    debug: {
        getRemoteLauncherCommand(host: string, port: number, waitUntilDebuggerAttaches: boolean): Promise<string[]>;
        getDebuggerPackagePath(): Promise<string | undefined>;
    };
    settings: {
        readonly onDidChangeExecutionDetails: Event<Uri | undefined>;
        getExecutionDetails(resource?: Uri | undefined): {
            execCommand: string[] | undefined;
        };
    };
}

interface IInterpreterDetails {
    path?: string[];
    resource?: Uri;
}

const onDidChangePythonInterpreterEvent = new EventEmitter<IInterpreterDetails>();
export const onDidChangePythonInterpreter: Event<IInterpreterDetails> = onDidChangePythonInterpreterEvent.event;

const interpreterMap: Map<string, string[] | undefined> = new Map();

function updateInterpreterFromExtension(api: IExtensionApi, resource?: Uri | undefined) {
    const execCommand = api.settings.getExecutionDetails(resource).execCommand;
    const workspaceFolder = resource ? getWorkspaceFolder(resource) : undefined;
    const key = workspaceFolder?.uri.toString() ?? '';

    const currentInterpreter = interpreterMap.get(key)?.join(' ') ?? '';
    const newInterpreter = execCommand?.join(' ') ?? '';
    if (currentInterpreter !== newInterpreter) {
        interpreterMap.set(key, execCommand);
        onDidChangePythonInterpreterEvent.fire({
            path: execCommand,
            resource,
        });
    }
}

export async function initializePython(disposables: Disposable[]): Promise<void> {
    try {
        interpreterMap.set('', undefined);
        getWorkspaceFolders().forEach((w) => interpreterMap.set(w.uri.toString(), undefined));

        const extension = extensions.getExtension('ms-python.python');
        if (extension) {
            if (!extension.isActive) {
                await extension.activate();
            }

            const api: IExtensionApi = extension.exports as IExtensionApi;

            disposables.push(
                api.settings.onDidChangeExecutionDetails((resource) => {
                    updateInterpreterFromExtension(api, resource);
                }),
            );

            updateInterpreterFromExtension(api);
        }
    } catch (error) {
        traceError('Error initializing python: ', error);
    }
}

export function getInterpreterDetails(resource?: Uri): IInterpreterDetails {
    const workspaceFolder = resource ? getWorkspaceFolder(resource) : undefined;
    const key = workspaceFolder?.uri.toString() ?? '';
    return { path: interpreterMap.get(key), resource };
}
