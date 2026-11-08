/**
 * How the page gets the service's token (spec 3 "Service rules", Interface page).
 *
 * The launcher opens `http://127.0.0.1:<port>/v1/ui/#token=<token>`. A fragment is never
 * sent to the service, so the token never appears in a request line or a log. The page
 * takes it, removes the fragment from the address bar (and so from the history entry), and
 * keeps it in the tab's session storage, so reloading the tab still works. Another start of
 * the service has another port, so another origin, whose storage is empty.
 */

export const TOKEN_KEY = "lcsim.token";

const FRAGMENT = /^#token=([A-Za-z0-9_-]+)$/;

export interface TokenSources {
  location: Pick<Location, "hash" | "pathname" | "search">;
  history: Pick<History, "replaceState">;
  storage: Pick<Storage, "getItem" | "setItem">;
}

/** The token from the address's fragment, then removed from it; else the stored one. */
export function takeToken({ location, history, storage }: TokenSources): string | null {
  const match = FRAGMENT.exec(location.hash);
  if (match?.[1] !== undefined) {
    const token = match[1];
    history.replaceState(null, "", `${location.pathname}${location.search}`);
    try {
      storage.setItem(TOKEN_KEY, token);
    } catch {
      // Storage refused (a private window): the page works until it is reloaded.
    }
    return token;
  }
  try {
    return storage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}
