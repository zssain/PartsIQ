// eslint-config-next 16 ships native flat configs (no FlatCompat / @eslint/eslintrc needed).
import coreWebVitals from "eslint-config-next/core-web-vitals";
import typescript from "eslint-config-next/typescript";

const eslintConfig = [
  ...coreWebVitals,
  ...typescript,
  { ignores: ["node_modules/**", ".next/**", "next-env.d.ts"] },
];

export default eslintConfig;
