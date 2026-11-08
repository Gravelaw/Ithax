/**
 * A small PDF writer for the Results export (spec 3 "Screens" 6: the PDF carries the
 * footer on every page). It writes text only, in the two standard fonts every PDF reader
 * has (Helvetica and Helvetica-Bold, with the WinAnsi encoding), so nothing is embedded or
 * fetched, and the page is made in the interface, offline. A character WinAnsi does not
 * have is written as "?" (AKS-138: the same limit jsPDF's standard fonts have).
 *
 * Text is wrapped by the fonts' published widths (Adobe's Helvetica AFM, in thousandths
 * of the font size), with Helvetica-Bold taken 10% wider, which is never narrower than
 * its own widths, so a wrapped line always fits. `docs/design/accessibility.md` "Text
 * size": 11 pt body text, 10 pt for the footer.
 */

/** A paragraph of the report: its text, size in points and weight. */
export interface Block {
  text: string;
  size: number;
  bold?: boolean;
  /** Space above, in points. */
  before?: number;
}

/** A4 in points. */
export const PAGE_WIDTH = 595.28;
export const PAGE_HEIGHT = 841.89;
const MARGIN = 56;
const FOOTER_SIZE = 10;
const LINE = 1.35;

// Helvetica widths of the characters 32 to 126 (Adobe AFM, thousandths of an em).
const ASCII_WIDTHS = [
  278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278, 556, 556, 556,
  556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556, 1015, 667, 667, 722, 722, 667,
  611, 778, 722, 278, 500, 667, 556, 833, 722, 778, 667, 778, 722, 667, 611, 722, 667, 944, 667,
  667, 611, 278, 278, 278, 469, 556, 333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500,
  222, 833, 556, 556, 556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584,
];
/** Every other WinAnsi character is taken as wide as the widest letter, so it fits. */
const OTHER_WIDTH = 1015;

// WinAnsi codes 128 to 159 for the characters that have them (PDF 32000-1, annex D).
const WIN_ANSI_HIGH: Record<number, number> = {
  8364: 0x80,
  8218: 0x82,
  402: 0x83,
  8222: 0x84,
  8230: 0x85,
  8224: 0x86,
  8225: 0x87,
  710: 0x88,
  8240: 0x89,
  352: 0x8a,
  8249: 0x8b,
  338: 0x8c,
  381: 0x8e,
  8216: 0x91,
  8217: 0x92,
  8220: 0x93,
  8221: 0x94,
  8226: 0x95,
  8211: 0x96,
  8212: 0x97,
  732: 0x98,
  8482: 0x99,
  353: 0x9a,
  8250: 0x9b,
  339: 0x9c,
  382: 0x9e,
  376: 0x9f,
};

/** The WinAnsi code of one character, or that of "?" when it has none. */
export function winAnsi(character: string): number {
  const code = character.codePointAt(0) ?? 63;
  if (code >= 32 && code <= 126) return code;
  if (code >= 160 && code <= 255) return code;
  if (code === 0x2212) return 45; // the minus sign, as a hyphen
  return WIN_ANSI_HIGH[code] ?? 63;
}

function charWidth(code: number): number {
  return code >= 32 && code <= 126 ? (ASCII_WIDTHS[code - 32] ?? OTHER_WIDTH) : OTHER_WIDTH;
}

/** The width of `text` in points at `size`. */
export function textWidth(text: string, size: number, bold = false): number {
  let total = 0;
  for (const character of text) total += charWidth(winAnsi(character));
  return (total * size * (bold ? 1.1 : 1)) / 1000;
}

/** `text` broken at spaces into lines no wider than `width`; a longer word is cut. */
export function wrap(text: string, size: number, width: number, bold = false): string[] {
  const lines: string[] = [];
  for (const paragraph of text.split("\n")) {
    let line = "";
    for (const word of paragraph.split(" ")) {
      const tried = line === "" ? word : `${line} ${word}`;
      if (textWidth(tried, size, bold) <= width) {
        line = tried;
        continue;
      }
      if (line !== "") lines.push(line);
      line = "";
      let rest = word;
      while (textWidth(rest, size, bold) > width) {
        let cut = rest.length - 1;
        while (cut > 1 && textWidth(rest.slice(0, cut), size, bold) > width) cut -= 1;
        lines.push(rest.slice(0, cut));
        rest = rest.slice(cut);
      }
      line = rest;
    }
    lines.push(line);
  }
  return lines;
}

/** A PDF string: WinAnsi bytes with `(`, `)` and `\` escaped, the rest as octal. */
function pdfString(text: string): string {
  let out = "(";
  for (const character of text) {
    const code = winAnsi(character);
    if (code === 40 || code === 41 || code === 92) out += `\\${String.fromCharCode(code)}`;
    else if (code < 127) out += String.fromCharCode(code);
    else out += `\\${code.toString(8).padStart(3, "0")}`;
  }
  return `${out})`;
}

interface Placed {
  text: string;
  size: number;
  bold: boolean;
  y: number;
}

/** Lays the blocks out on pages, leaving room at the bottom for the footer. */
function paginate(blocks: readonly Block[], footerHeight: number): Placed[][] {
  const width = PAGE_WIDTH - 2 * MARGIN;
  const bottom = MARGIN + footerHeight + 12;
  const pages: Placed[][] = [[]];
  let y = PAGE_HEIGHT - MARGIN;
  for (const block of blocks) {
    const bold = block.bold ?? false;
    const height = block.size * LINE;
    y -= block.before ?? 0;
    for (const line of wrap(block.text, block.size, width, bold)) {
      if (y - height < bottom) {
        pages.push([]);
        y = PAGE_HEIGHT - MARGIN;
      }
      y -= height;
      pages.at(-1)?.push({ text: line, size: block.size, bold, y: y + (height - block.size) });
    }
  }
  return pages;
}

/**
 * A PDF of `blocks`, with `footer` (one item per entry, wrapped) at the bottom of every
 * page and `title` in its information dictionary.
 */
export function makePdf(
  blocks: readonly Block[],
  footer: readonly string[],
  title: string,
): Uint8Array {
  const width = PAGE_WIDTH - 2 * MARGIN;
  const footerLines = footer.flatMap((item) => wrap(item, FOOTER_SIZE, width));
  const footerHeight = footerLines.length * FOOTER_SIZE * LINE;
  const pages = paginate(blocks, footerHeight);

  const objects: string[] = [];
  const add = (body: string): number => {
    objects.push(body);
    return objects.length;
  };
  const catalog = add("");
  const pagesObject = add("");
  const regular = add(
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
  );
  const bold = add(
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
  );
  const info = add(`<< /Title ${pdfString(title)} /Producer (lcsim) >>`);
  const kids: number[] = [];
  pages.forEach((placed, index) => {
    const ops: string[] = [];
    const text = (line: string, size: number, isBold: boolean, x: number, y: number) => {
      ops.push(
        `BT /${isBold ? "F2" : "F1"} ${size} Tf ${x.toFixed(2)} ${y.toFixed(2)} Td ${pdfString(line)} Tj ET`,
      );
    };
    for (const line of placed) text(line.text, line.size, line.bold, MARGIN, line.y);
    let y = MARGIN + footerHeight - FOOTER_SIZE;
    ops.push(
      `0.5 w ${MARGIN} ${(MARGIN + footerHeight + 6).toFixed(2)} m ${PAGE_WIDTH - MARGIN} ${(MARGIN + footerHeight + 6).toFixed(2)} l S`,
    );
    for (const line of footerLines) {
      text(line, FOOTER_SIZE, false, MARGIN, y);
      y -= FOOTER_SIZE * LINE;
    }
    text(
      `Page ${index + 1} of ${pages.length}`,
      FOOTER_SIZE,
      false,
      PAGE_WIDTH - MARGIN - 60,
      MARGIN - 24,
    );
    const stream = ops.join("\n");
    const contents = add(`<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`);
    kids.push(
      add(
        `<< /Type /Page /Parent ${pagesObject} 0 R /MediaBox [0 0 ${PAGE_WIDTH} ${PAGE_HEIGHT}] ` +
          `/Resources << /Font << /F1 ${regular} 0 R /F2 ${bold} 0 R >> >> /Contents ${contents} 0 R >>`,
      ),
    );
  });
  objects[catalog - 1] = `<< /Type /Catalog /Pages ${pagesObject} 0 R >>`;
  objects[pagesObject - 1] =
    `<< /Type /Pages /Kids [${kids.map((kid) => `${kid} 0 R`).join(" ")}] /Count ${kids.length} >>`;

  let out = "%PDF-1.4\n%âãÏÓ\n";
  const offsets: number[] = [];
  objects.forEach((body, index) => {
    offsets.push(out.length);
    out += `${index + 1} 0 obj\n${body}\nendobj\n`;
  });
  const xref = out.length;
  out += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  for (const offset of offsets) out += `${String(offset).padStart(10, "0")} 00000 n \n`;
  out += `trailer\n<< /Size ${objects.length + 1} /Root ${catalog} 0 R /Info ${info} 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  // Every character above is a byte (ASCII, or the four comment bytes after the header).
  const bytes = new Uint8Array(out.length);
  for (let index = 0; index < out.length; index += 1) bytes[index] = out.charCodeAt(index);
  return bytes;
}
