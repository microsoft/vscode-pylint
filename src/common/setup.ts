// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import * as path from 'path';
import * as fs from 'fs-extra';
import { EXTENSION_ROOT_DIR } from './constants';

export interface ILinterPattern {
    regex: string;
    args: string[];
    lineStartsAt1: boolean;
    columnStartsAt1: boolean;
    useStdin: boolean;
}

export interface ILinter {
    name: string;
    module: string;
    patterns: Record<string, ILinterPattern>;
    version: string;
}

export function loadLinterDefaults(): ILinter {
    const linterJson = path.join(EXTENSION_ROOT_DIR, 'package.json');
    const content = fs.readFileSync(linterJson).toString();
    const config = JSON.parse(content);
    return config.linter as ILinter;
}
