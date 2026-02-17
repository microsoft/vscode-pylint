// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import { assert } from 'chai';
import * as sinon from 'sinon';
import * as vscode from 'vscode';
import { createConfigFileWatchers } from '../../../../common/configWatcher';
import { PYLINT_CONFIG_FILES } from '../../../../common/constants';

suite('Config File Watcher Tests', () => {
    let createFileSystemWatcherStub: sinon.SinonStub;
    let mockWatcher: {
        onDidChange: sinon.SinonStub;
        onDidCreate: sinon.SinonStub;
        onDidDelete: sinon.SinonStub;
        dispose: sinon.SinonStub;
    };
    let changeDisposable: { dispose: sinon.SinonStub };
    let createDisposable: { dispose: sinon.SinonStub };
    let deleteDisposable: { dispose: sinon.SinonStub };
    let onConfigChangedCallback: sinon.SinonStub;

    setup(() => {
        // Create separate mock disposables for each event subscription
        changeDisposable = { dispose: sinon.stub() };
        createDisposable = { dispose: sinon.stub() };
        deleteDisposable = { dispose: sinon.stub() };

        // Create mock watcher
        mockWatcher = {
            onDidChange: sinon.stub().returns(changeDisposable),
            onDidCreate: sinon.stub().returns(createDisposable),
            onDidDelete: sinon.stub().returns(deleteDisposable),
            dispose: sinon.stub(),
        };

        // Stub workspace.createFileSystemWatcher
        createFileSystemWatcherStub = sinon.stub(vscode.workspace, 'createFileSystemWatcher');
        createFileSystemWatcherStub.returns(mockWatcher as any);

        // Create callback stub
        onConfigChangedCallback = sinon.stub().resolves();
    });

    teardown(() => {
        sinon.restore();
    });

    test('Should create file watchers for each pylint config file pattern', () => {
        const watchers = createConfigFileWatchers(onConfigChangedCallback);

        assert.strictEqual(watchers.length, PYLINT_CONFIG_FILES.length);
        assert.strictEqual(createFileSystemWatcherStub.callCount, PYLINT_CONFIG_FILES.length);

        PYLINT_CONFIG_FILES.forEach((pattern, index) => {
            assert.strictEqual(
                createFileSystemWatcherStub.getCall(index).args[0],
                `**/${pattern}`,
                `Expected watcher for pattern: ${pattern}`,
            );
        });
    });

    test('Should call callback when config file is changed', async () => {
        createConfigFileWatchers(onConfigChangedCallback);

        // Get the change handler that was registered
        const changeHandler = mockWatcher.onDidChange.getCall(0).args[0];

        // Call it
        await changeHandler();

        assert.strictEqual(onConfigChangedCallback.callCount, 1);
    });

    test('Should call callback when config file is created', async () => {
        createConfigFileWatchers(onConfigChangedCallback);

        // Get the create handler that was registered
        const createHandler = mockWatcher.onDidCreate.getCall(0).args[0];

        // Call it
        await createHandler();

        assert.strictEqual(onConfigChangedCallback.callCount, 1);
    });

    test('Should call callback when config file is deleted', async () => {
        createConfigFileWatchers(onConfigChangedCallback);

        // Get the delete handler that was registered
        const deleteHandler = mockWatcher.onDidDelete.getCall(0).args[0];

        // Call it
        await deleteHandler();

        assert.strictEqual(onConfigChangedCallback.callCount, 1);
    });

    test('Should create watchers for all config file types', () => {
        const expectedPatterns = ['.pylintrc', 'pylintrc', 'pyproject.toml', 'setup.cfg', 'tox.ini'];
        const watchers = createConfigFileWatchers(onConfigChangedCallback);

        assert.strictEqual(watchers.length, expectedPatterns.length);

        expectedPatterns.forEach((pattern) => {
            const matchingCall = createFileSystemWatcherStub
                .getCalls()
                .find((call) => call.args[0] === `**/${pattern}`);
            assert.isDefined(matchingCall, `Should have created watcher for ${pattern}`);
        });
    });

    test('Should return disposable for each watcher', () => {
        const watchers = createConfigFileWatchers(onConfigChangedCallback);

        watchers.forEach((watcher) => {
            assert.isDefined(watcher.dispose, 'Each watcher should have a dispose method');
        });
    });

    test('Should dispose all subscriptions and watcher on dispose', () => {
        const watchers = createConfigFileWatchers(onConfigChangedCallback);

        watchers[0].dispose();

        assert.strictEqual(changeDisposable.dispose.callCount, 1, 'Change subscription should be disposed');
        assert.strictEqual(createDisposable.dispose.callCount, 1, 'Create subscription should be disposed');
        assert.strictEqual(deleteDisposable.dispose.callCount, 1, 'Delete subscription should be disposed');
        assert.strictEqual(mockWatcher.dispose.callCount, 1, 'Watcher should be disposed');
    });

    test('Should not call callback after dispose', () => {
        const watchers = createConfigFileWatchers(onConfigChangedCallback);

        // Dispose the watcher
        watchers[0].dispose();

        // Get the handlers and call them after disposal
        const changeHandler = mockWatcher.onDidChange.getCall(0).args[0];
        changeHandler();

        assert.strictEqual(onConfigChangedCallback.callCount, 0, 'Callback should not be called after dispose');
    });
});
