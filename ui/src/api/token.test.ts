import { describe, expect, it, vi } from "vitest";
import { TOKEN_KEY, takeToken } from "./token";

function sources(hash: string, stored: string | null = null) {
  const store = new Map<string, string>();
  if (stored !== null) store.set(TOKEN_KEY, stored);
  return {
    location: { hash, pathname: "/v1/ui/", search: "" },
    history: { replaceState: vi.fn() },
    storage: () => ({
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => store.set(key, value),
    }),
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
    const refusing = () => ({
      getItem: () => {
        throw new Error("refused");
      },
      setItem: () => {
        throw new Error("refused");
      },
    });
    const given = { ...sources("#token=t1"), storage: refusing };
    expect(takeToken(given)).toBe("t1");
    expect(takeToken({ ...given, location: { ...given.location, hash: "" } })).toBeNull();
  });

  it("takes the fragment's token when reaching storage itself throws", () => {
    // Reading window.sessionStorage throws a SecurityError when the browser denies storage.
    const denied = () => {
      throw new DOMException("denied", "SecurityError");
    };
    const given = { ...sources("#token=t2"), storage: denied };
    expect(takeToken(given)).toBe("t2");
    expect(given.history.replaceState).toHaveBeenCalledOnce();
    expect(takeToken({ ...given, location: { ...given.location, hash: "" } })).toBeNull();
  });
});
