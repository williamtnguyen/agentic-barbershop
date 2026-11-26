import "@fontsource-variable/geist";
import "./index.css";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { config } from "./config";
import { App } from "./App";

document.title = config.businessName;

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
