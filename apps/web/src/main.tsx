import "@fontsource-variable/geist";
import "./index.css";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { config } from "./config";
import { ChatPage } from "./features/chat/ChatPage";

document.title = config.businessName;

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ChatPage />
  </StrictMode>,
);
