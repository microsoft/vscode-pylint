// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

// NOTE: Variable resolution and getWorkspaceSettings tests live in the shared
// package (@vscode/common-python-lsp) test suite. Extension-level tests focus
// on extension-specific wrapper behavior.

import { assert } from 'chai';
import * as sinon from 'sinon';
import * as TypeMoq from 'typemoq';
import { WorkspaceConfiguration } from 'vscode';
import { isLintOnChangeEnabled, checkIfConfigurationChanged, getTrackedSettings } from '../../../../common/settings';
import * as vscodeapi from '../../../../common/vscodeapi';

suite('Settings Tests', () => {
    suite('isLintOnChangeEnabled tests', () => {
        let getConfigurationStub: sinon.SinonStub;
        let configMock: TypeMoq.IMock<WorkspaceConfiguration>;

        setup(() => {
            getConfigurationStub = sinon.stub(vscodeapi, 'getConfiguration');
            configMock = TypeMoq.Mock.ofType<WorkspaceConfiguration>();
            getConfigurationStub.returns(configMock.object);
        });

        teardown(() => {
            sinon.restore();
        });

        [true, false].forEach((value) => {
            test(`Lint on change settings: ${value}`, () => {
                configMock
                    .setup((c) => c.get<boolean>('lintOnChange', false))
                    .returns(() => value)
                    .verifiable(TypeMoq.Times.atLeastOnce());
                assert.deepStrictEqual(isLintOnChangeEnabled('pylint'), value);
            });
        });
    });

    suite('checkIfConfigurationChanged tests', () => {
        teardown(() => {
            sinon.restore();
        });

        test('Returns true when a tracked setting changes', () => {
            const trackedSettings = getTrackedSettings('pylint');
            for (const setting of trackedSettings) {
                const mockEvent = {
                    affectsConfiguration: (section: string) => section === setting,
                };
                assert.isTrue(
                    checkIfConfigurationChanged(mockEvent as any, 'pylint'),
                    `Expected true for setting: ${setting}`,
                );
            }
        });

        test('Returns false when unrelated setting changes', () => {
            const mockEvent = {
                affectsConfiguration: (_section: string) => false,
            };
            assert.isFalse(checkIfConfigurationChanged(mockEvent as any, 'pylint'));
        });
    });
});
