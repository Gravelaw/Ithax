/**
 * Whether the component is still mounted, for an answer that arrives after it is gone (a
 * screen that was left never navigates or sets state).
 */
import { type RefObject, useEffect, useRef } from "react";

export function useMounted(): RefObject<boolean> {
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  return mounted;
}
