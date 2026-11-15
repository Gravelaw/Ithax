/**
 * Which answers to take when reads and writes of one shared value overlap (reviews of pull
 * requests 200 and 202: an answer is taken against the value as it is now, never against
 * what was known when its request was sent).
 *
 * - A write's answer holds the value after that write: it is taken unless the answer of a
 *   write sent later was taken first.
 * - A read's answer is taken only when no write was awaiting its answer when the read was
 *   sent, and none was sent since: otherwise the service may have read the value before the
 *   write, and the write's own answer is the newer value.
 *
 * Call `write()` or `read()` when the request is sent, and the function it returns with
 * whether the answer succeeded once it arrives; it says whether to take the answer.
 */
export class AnswerOrder {
  private writesSent = 0;
  private writesOpen = 0;
  private writeTaken = 0;

  write(): (ok: boolean) => boolean {
    this.writesSent += 1;
    this.writesOpen += 1;
    const number = this.writesSent;
    return (ok) => {
      this.writesOpen -= 1;
      if (!ok || number < this.writeTaken) return false;
      this.writeTaken = number;
      return true;
    };
  }

  read(): (ok: boolean) => boolean {
    const quiet = this.writesOpen === 0;
    const writes = this.writesSent;
    return (ok) => ok && quiet && this.writesSent === writes;
  }
}
