import js from '@eslint/js';
import tseslint from 'typescript-eslint';
import reactHooks from 'eslint-plugin-react-hooks';

export default tseslint.config(
  { ignores: ['dist', 'node_modules', 'doc', 'docs'] },
  {
    files: ['src/**/*.{ts,tsx}'],
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    plugins: {
      'react-hooks': reactHooks,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      // Empty catch blocks are deliberate graceful degradation here
      // (localStorage quota, backend offline); everything else stays banned.
      'no-empty': ['error', { allowEmptyCatch: true }],
      // TypeScript itself flags unknown identifiers; no-undef misfires on
      // DOM lib globals under flat config.
      'no-undef': 'off',
    },
  },
  {
    // Ambient global declarations require `declare var` semantics.
    files: ['src/**/*.d.ts'],
    rules: { 'no-var': 'off' },
  }
);
