import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";

// Suppress benign "ResizeObserver loop" warnings that CRA's error overlay
// intercepts and renders as an intrusive full-screen modal. This is a
// well-known Chromium false-positive triggered by Radix popovers / shadcn
// Select components and is safe to ignore.
const RESIZE_OBSERVER_ERR_RE = /^ResizeObserver loop (limit exceeded|completed with undelivered notifications)/;
const _origErrorHandler = window.onerror;
window.addEventListener("error", (e) => {
  if (e?.message && RESIZE_OBSERVER_ERR_RE.test(e.message)) {
    e.stopImmediatePropagation();
    e.preventDefault();
  }
});
window.onerror = function (message, ...rest) {
  if (typeof message === "string" && RESIZE_OBSERVER_ERR_RE.test(message)) return true;
  return _origErrorHandler ? _origErrorHandler(message, ...rest) : false;
};

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
