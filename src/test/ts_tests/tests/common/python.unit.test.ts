// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import { assert } from 'chai';
import * as sinon from 'sinon';
import * as vscode from 'vscode';
import { PythonExtension, ResolvedEnvironment } from '@vscode/python-extension';
import { resolveInterpreter } from '../../../../common/python';
import { PythonEnvironment } from '../../../../typings/pythonEnvironments';

// Standalone stubs shared across suites; reset manually in each setup hook.
// These survive sinon.restore() so they can be used as stable object references
// even after the module-level _envsApi / _api caches are populated.
const mockGetEnvironment = sinon.stub();
const mockEnvsApi = {
    getEnvironment: mockGetEnvironment,
    onDidChangeEnvironment: sinon.stub(),
};

const mockResolveEnvironment = sinon.stub();
const mockLegacyApi = {
    environments: {
        resolveEnvironment: mockResolveEnvironment,
        getActiveEnvironmentPath: sinon.stub(),
    },
};

suite('resolveInterpreter Tests', () => {
    // Suite 1: Environments extension is NOT available.
    // This suite must run before Suite 2 so that the module-level _envsApi cache
    // is still undefined when these tests execute.
    suite('when Environments extension is not available', () => {
        setup(() => {
            sinon.stub(vscode.extensions, 'getExtension').returns(undefined);
            sinon.stub(PythonExtension, 'api').resolves(mockLegacyApi as unknown as PythonExtension);
            mockResolveEnvironment.reset();
        });

        teardown(() => {
            sinon.restore();
        });

        test('falls back to legacy API and returns resolved environment', async () => {
            const expected = {
                executable: { uri: vscode.Uri.file('/usr/bin/python3') },
            } as ResolvedEnvironment;
            mockResolveEnvironment.resolves(expected);

            const result = await resolveInterpreter(['/usr/bin/python3']);

            assert.strictEqual(result, expected);
        });

        test('returns undefined when legacy API also has no environment', async () => {
            mockResolveEnvironment.resolves(undefined);

            const result = await resolveInterpreter(['/usr/bin/python3']);

            assert.isUndefined(result);
        });
    });

    // Suite 2: Environments extension IS available.
    // suiteSetup populates the module-level _envsApi cache once for all tests in
    // this suite. Individual tests control behaviour via mockGetEnvironment.
    suite('when Environments extension is available', () => {
        suiteSetup(async () => {
            // Populate _envsApi by stubbing getExtension for one call.
            const getExtensionStub = sinon.stub(vscode.extensions, 'getExtension');
            getExtensionStub.withArgs('ms-python.vscode-python-envs').returns({
                isActive: true,
                exports: mockEnvsApi,
            } as unknown as vscode.Extension<unknown>);
            sinon.stub(PythonExtension, 'api').resolves(mockLegacyApi as unknown as PythonExtension);
            // Trigger cache population by calling the function once.
            mockGetEnvironment.resolves(undefined);
            await resolveInterpreter(['/tmp/seed']);
            sinon.restore();
        });

        setup(() => {
            sinon.stub(PythonExtension, 'api').resolves(mockLegacyApi as unknown as PythonExtension);
            mockGetEnvironment.reset();
            mockResolveEnvironment.reset();
        });

        teardown(() => {
            sinon.restore();
        });

        test('returns PythonEnvironment when active environment matches interpreter', async () => {
            const matchingEnv: PythonEnvironment = {
                envId: { id: 'test-env', managerId: 'test-manager' },
                name: 'test',
                displayName: 'Test Env',
                version: '3.10.0',
                environmentPath: vscode.Uri.file('/usr/bin'),
                execInfo: { run: { executable: '/usr/bin/python3' } },
                sysPrefix: '/usr',
            };
            mockGetEnvironment.resolves(matchingEnv);

            const result = await resolveInterpreter(['/usr/bin/python3']);

            assert.strictEqual(result, matchingEnv);
        });

        test('falls back to legacy API when active environment does not match interpreter', async () => {
            const nonMatchingEnv: PythonEnvironment = {
                envId: { id: 'other-env', managerId: 'test-manager' },
                name: 'other',
                displayName: 'Other Env',
                version: '3.9.0',
                environmentPath: vscode.Uri.file('/usr/local/bin'),
                execInfo: { run: { executable: '/usr/local/bin/python3' } },
                sysPrefix: '/usr/local',
            };
            const expectedLegacy = {
                executable: { uri: vscode.Uri.file('/usr/bin/python3') },
            } as ResolvedEnvironment;
            mockGetEnvironment.resolves(nonMatchingEnv);
            mockResolveEnvironment.resolves(expectedLegacy);

            const result = await resolveInterpreter(['/usr/bin/python3']);

            assert.strictEqual(result, expectedLegacy);
        });
    });
});
