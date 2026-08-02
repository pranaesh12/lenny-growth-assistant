import React from "react";
import ReactDOM from "react-dom/client";

import App from "./App";
import QueryProvider from "./providers/QueryProvider";

import "./styles/globals.css";

console.log("API URL:", import.meta.env.VITE_API_BASE_URL);

ReactDOM.createRoot(
  document.getElementById("root") as HTMLElement,
).render(
  <React.StrictMode>
    <QueryProvider>
      <App />
    </QueryProvider>
  </React.StrictMode>,
);