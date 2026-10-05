import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";

// Suppress benign "ResizeObserver loop" warnings that CRA's error overlay
// intercepts and renders as an intrusive full-screen modal. This is a
// well-known Chromium false-positive triggered by Radix popovers / shadcn
// Select components and is safe to ignore.
const RESIZE_OBSERVER_ERR_RE = /ResizeObserver loop (limit exceeded|completed with undelivered notifications)/;

// 1) Capture-phase window error listener — runs BEFORE React DevTools /
//    webpack-dev-server overlay handlers and swallows the event entirely.
window.addEventListener("error", (e) => {
  const msg = e?.message || e?.error?.message || "";
  if (msg && RESIZE_OBSERVER_ERR_RE.test(msg)) {
    e.stopImmediatePropagation();
    e.preventDefault();
  }
}, true);

// 2) `unhandledrejection` — some polyfills throw it as a rejected promise.
window.addEventListener("unhandledrejection", (e) => {
  const msg = (e && (e.reason?.message || String(e.reason))) || "";
  if (RESIZE_OBSERVER_ERR_RE.test(msg)) {
    e.stopImmediatePropagation();
    e.preventDefault();
  }
}, true);

// 3) Legacy onerror callback used by older browsers / test harnesses.
const _origErrorHandler = window.onerror;
window.onerror = function (message, ...rest) {
  if (typeof message === "string" && RESIZE_OBSERVER_ERR_RE.test(message)) return true;
  return _origErrorHandler ? _origErrorHandler(message, ...rest) : false;
};

// 4) Hide react-error-overlay (CRA) if it manages to sneak the message past
//    the handlers above. The overlay always renders a #webpack-dev-server-
//    client-overlay or a div containing the exact text.
if (typeof window !== "undefined") {
  const origConsoleError = console.error;
  console.error = function (...args) {
    if (args.length && typeof args[0] === "string" && RESIZE_OBSERVER_ERR_RE.test(args[0])) return;
    origConsoleError.apply(console, args);
  };
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
