/**
 * Requests for one shared value sent one at a time, each after the one before has its
 * answer (review of pull request 200: overlapping settings reads and writes reached the
 * service out of order, so an answer could hold an older value than one already shown).
 * With one in flight, each answer is the value at its turn, and the answer that arrives
 * last is always the latest.
 *
 * `oneAtATime()` returns a queue; `queue(start)` calls `start` once every earlier request
 * has settled, succeeded or not, and returns its answer.
 */
export function oneAtATime(): <T>(start: () => Promise<T>) => Promise<T> {
  let tail: Promise<unknown> = Promise.resolve();
  return <T>(start: () => Promise<T>): Promise<T> => {
    const turn = tail.then(start);
    tail = turn.catch(() => undefined);
    return turn;
  };
}
