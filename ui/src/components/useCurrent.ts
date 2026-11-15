/**
 * The current value of `value`, for a completion that runs after an await: it acts on the
 * state as it is when the answer arrives, never on what it captured when its request was
 * sent (review of pull request 201: removing project A ended project B's lesson, started
 * while the removal awaited its answer). See also `AnswerOrder`.
 */
import { useCallback, useLayoutEffect, useRef } from "react";

export function useCurrent<T>(value: T): () => T {
  const ref = useRef(value);
  useLayoutEffect(() => {
    ref.current = value;
  });
  return useCallback(() => ref.current, []);
}
