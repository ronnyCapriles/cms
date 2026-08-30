import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import "./styles/index.css";
import App from "./App.jsx";
import { initialMode } from "./prefs.js";

// Fallbacks only: the shell's pre-paint script normally sets both, so a light
// visitor never sees a dark flash.
document.documentElement.dataset.theme ||= "a";
document.documentElement.dataset.mode ||= initialMode();

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
);
