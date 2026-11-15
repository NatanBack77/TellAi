import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "src/routeTree.gen.ts"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ["**/*.{ts,tsx}"],
    languageOptions: { ecmaVersion: 2022, globals: globals.browser },
    plugins: { "react-hooks": reactHooks, "react-refresh": reactRefresh },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": [
        "warn",
        { allowConstantExport: true, allowExportNames: ["Route"] },
      ],
      // Views não acessam services diretamente: passam pelo ViewModel.
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["**/services/*", "@/features/*/services/*"],
              message: "Na camada View, use o ViewModel em vez de chamar services.",
            },
          ],
        },
      ],
    },
  },
  {
    // Cenas 3D exportam peças, constantes e helpers juntos; fast refresh não é crítico ali.
    files: ["src/features/*/components/three/**", "src/shared/components/ui/IconButton.tsx"],
    rules: { "react-refresh/only-export-components": "off" },
  },
  {
    // Quem pode importar services: viewmodels, services, rotas (guards/loaders) e testes.
    files: [
      "src/features/*/viewmodels/**",
      "src/features/*/services/**",
      "src/routes/**",
      "**/*.test.{ts,tsx}",
    ],
    rules: { "no-restricted-imports": "off" },
  },
);
