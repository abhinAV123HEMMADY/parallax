import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
// Before index.css, so the app's own rules win where they overlap.
import "katex/dist/katex.min.css";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
