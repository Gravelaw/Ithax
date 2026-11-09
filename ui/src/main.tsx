/**
 * The interface's entry point: take the token from the launcher's address, install the
 * design tokens and the bundled fonts, and start (spec 3 "Service rules", Interface page).
 */
import "@fontsource-variable/atkinson-hyperlegible-next";
import "@fontsource-variable/bricolage-grotesque";
import "@fontsource-variable/jetbrains-mono";
import "./theme/global.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { ApiClient } from "./api/client";
import { takeToken } from "./api/token";
import { Boot, NoToken } from "./app/Boot";
import { installTheme } from "./theme/tokens";

installTheme(document);
const token = takeToken({ location, history, storage: () => window.sessionStorage });
const container = document.getElementById("root");
if (container === null) throw new Error("index.html has no #root");
createRoot(container).render(
  <StrictMode>
    {token === null ? (
      <NoToken />
    ) : (
      <Boot
        client={new ApiClient({ origin: location.origin, token })}
        root={document.documentElement}
      />
    )}
  </StrictMode>,
);
