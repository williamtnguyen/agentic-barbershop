/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_BUSINESS_NAME?: string;
  readonly VITE_API_BASE_URL?: string;
}

// Font packages are CSS-only imports.
declare module "@fontsource/*";
declare module "@fontsource-variable/*";
