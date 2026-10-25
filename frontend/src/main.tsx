import React from "react";
import ReactDOM from "react-dom/client";
// Google Sans Flex (OFL), with the optical-size axis: large headlines tighten, small text opens up.
import "@fontsource-variable/google-sans-flex/opsz.css";
import "./styles.css";
import { App } from "./App";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
