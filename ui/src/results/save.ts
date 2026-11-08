/**
 * Hands a file the interface made or received to the browser, which saves it (the exports
 * of the Results screen). Nothing is sent anywhere: the file is a `blob:` address of the
 * page's own, given up a minute later.
 */
export const RELEASE_MS = 60_000;

export function saveFile(blob: Blob, name: string): void {
  const address = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = address;
  link.download = name;
  link.hidden = true;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(address), RELEASE_MS);
}
