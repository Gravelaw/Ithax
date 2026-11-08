import { describe, expect, it, vi } from "vitest";
import { TOKEN_KEY, takeToken } from "./token";

function sources(hash: string, stored: string | null = null) {
  const store = new Map<string, string>();
  if (stored !== null) store.set(TOKEN_KEY, stored);
  return {
    location: { hash, pathname: "/v1/ui/", search: "" },
    history: { replaceState: vi.fn() },
    storage: {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => store.set(key, value),
    },
    store,
  };
}

describe("takeToken", () => {
  it("takes the token from the fragment, removes it and keeps it for the tab", () => {
    const given = sources("#token=abc_DEF-123");
    expect(takeToken(given)).toBe("abc_DEF-123");
    expect(given.history.replaceState).toHaveBeenCalledWith(null, "", "/v1/ui/");
    expect(given.store.get(TOKEN_KEY)).toBe("abc_DEF-123");
  });

  it("uses the stored token after a reload", () => {
    const given = sources("#/canvas/p", "kept");
    expect(takeToken(given)).toBe("kept");
    expect(given.history.replaceState).not.toHaveBeenCalled();
  });

  it("has no token without a fragment or a stored one", () => {
    expect(takeToken(sources(""))).toBeNull();
    expect(takeToken(sources("#token=has space"))).toBeNull();
  });

  it("works when storage refuses", () => {
    const given = sources("#token=t1");
    given.storage.setItem = () => {
      throw new Error("refused");
    };
    expect(takeToken(given)).toBe("t1");
    given.storage.getItem = () => {
      throw new Error("refused");
    };
    expect(takeToken({ ...given, location: { ...given.location, hash: "" } })).toBeNull();
  });
});
