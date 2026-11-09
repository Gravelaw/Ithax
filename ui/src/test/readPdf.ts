/**
 * Reads a PDF's text page by page with Mozilla's pdf.js (a development dependency), an
 * independent reader for the tests of the PDF export (AKS-138).
 */
import { getDocument } from "pdfjs-dist/legacy/build/pdf.mjs";

export interface PageText {
  text: string;
  items: { str: string; x: number; width: number }[];
}

export async function readPdf(bytes: Uint8Array): Promise<PageText[]> {
  const document = await getDocument({ data: bytes.slice(), useSystemFonts: false }).promise;
  const pages: PageText[] = [];
  for (let number = 1; number <= document.numPages; number += 1) {
    const page = await document.getPage(number);
    const content = await page.getTextContent();
    const items = content.items.flatMap((item) =>
      "str" in item ? [{ str: item.str, x: item.transform[4] as number, width: item.width }] : [],
    );
    pages.push({
      text: items
        .map((item) => item.str)
        .join(" ")
        .replace(/\s+/g, " "),
      items,
    });
  }
  await document.destroy();
  return pages;
}
