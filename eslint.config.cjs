const tsParser = require("@typescript-eslint/parser");
const tsPlugin = require("@typescript-eslint/eslint-plugin");

module.exports = [
    {
        files: ["src/**/*.ts"],
        ignores: ["out", "dist", "**/*.d.ts"],
        languageOptions: {
            ecmaVersion: 6,
            sourceType: "module",
            parser: tsParser,
        },
        plugins: {
            "@typescript-eslint": tsPlugin,
        },
        linterOptions: {
            reportUnusedDisableDirectives: "warn",
        },
        rules: {
            "@typescript-eslint/naming-convention": "warn",
            curly: "warn",
            eqeqeq: "warn",
            "no-throw-literal": "warn",
            semi: "warn",
        },
    },
];
