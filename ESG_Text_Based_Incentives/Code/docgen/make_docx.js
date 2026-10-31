// Generic JSON -> .docx renderer used by Step 17.
// Usage: node make_docx.js spec.json out.docx
// spec = {title, subtitle, meta:[[k,v],...], blocks:[{type, ...}]}
// block types: h1 h2 h3 | p {text, bold, italic, color} | bullets {items} | numbered {items}
//              table {header:[...], rows:[[...]], widths:[dxa...]} | code {text} | note {text} | pagebreak
const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell, WidthType, ShadingType,
  AlignmentType, BorderStyle, LevelFormat, Footer, Header, PageNumber, TableLayoutType,
} = require("docx");

const [, , specPath, outPath] = process.argv;
const spec = JSON.parse(fs.readFileSync(specPath, "utf8"));
const FONT = { ascii: "Calibri", hAnsi: "Calibri", eastAsia: "Microsoft YaHei", cs: "Calibri" };
const MONO = { ascii: "Consolas", hAnsi: "Consolas", eastAsia: "Microsoft YaHei", cs: "Consolas" };
const PAGE_W = 11906, MARGIN = 1134, CONTENT_W = PAGE_W - 2 * MARGIN;   // A4, 2 cm margins

const clean = (s) => String(s ?? "").replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, "");
function runs(text, opts = {}) {
  // supports **bold** inline markup
  const out = [];
  clean(text).split(/(\*\*[^*]+\*\*)/).forEach((part) => {
    if (!part) return;
    const b = part.startsWith("**") && part.endsWith("**");
    out.push(new TextRun({ text: b ? part.slice(2, -2) : part, bold: b || opts.bold, italics: opts.italic,
                           color: opts.color, font: opts.mono ? MONO : FONT, size: opts.size }));
  });
  return out;
}
const para = (text, opts = {}) => new Paragraph({ children: runs(text, opts), spacing: { after: 100 }, ...(opts.para || {}) });

function table(b) {
  const n = b.header.length;
  let widths = b.widths && b.widths.length === n ? b.widths.slice() : Array(n).fill(Math.floor(CONTENT_W / n));
  const sum = widths.reduce((a, c) => a + c, 0);
  widths = widths.map((w) => Math.floor((w * CONTENT_W) / sum));
  widths[n - 1] += CONTENT_W - widths.reduce((a, c) => a + c, 0);
  const border = { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF" };
  const borders = { top: border, bottom: border, left: border, right: border };
  const cell = (t, i, head) => new TableCell({
    width: { size: widths[i], type: WidthType.DXA }, borders,
    shading: head ? { type: ShadingType.CLEAR, color: "auto", fill: "D9E2F3" } : undefined,
    margins: { top: 40, bottom: 40, left: 80, right: 80 },
    children: clean(t).split("\n").map((line) => new Paragraph({ children: runs(line, { bold: head, size: b.size || 17 }) })),
  });
  const rows = [new TableRow({ tableHeader: true, children: b.header.map((h, i) => cell(h, i, true)) })];
  (b.rows || []).forEach((r) => rows.push(new TableRow({ children: r.map((c, i) => cell(c, i, false)) })));
  return new Table({ width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: widths, layout: TableLayoutType.FIXED, rows });
}

const children = [];
children.push(new Paragraph({ heading: HeadingLevel.TITLE, children: runs(spec.title, { size: 40, bold: true }) }));
if (spec.subtitle) children.push(para(spec.subtitle, { italic: true, color: "595959" }));
if (spec.meta && spec.meta.length) children.push(table({ header: ["Item", "Value"], rows: spec.meta, widths: [2600, 7000] }));
children.push(new Paragraph({ children: [] }));
for (const b of spec.blocks) {
  switch (b.type) {
    case "h1": children.push(new Paragraph({ heading: HeadingLevel.HEADING_1, children: runs(b.text), spacing: { before: 240, after: 120 } })); break;
    case "h2": children.push(new Paragraph({ heading: HeadingLevel.HEADING_2, children: runs(b.text), spacing: { before: 200, after: 100 } })); break;
    case "h3": children.push(new Paragraph({ heading: HeadingLevel.HEADING_3, children: runs(b.text), spacing: { before: 160, after: 80 } })); break;
    case "p": children.push(para(b.text, b)); break;
    case "note": children.push(new Paragraph({ children: runs(b.text, { italic: true, color: "7F6000" }),
      shading: { type: ShadingType.CLEAR, color: "auto", fill: "FFF2CC" }, spacing: { after: 120 } })); break;
    case "bullets": b.items.forEach((t) => children.push(new Paragraph({ numbering: { reference: "bul", level: b.level || 0 }, children: runs(t) }))); break;
    case "numbered": b.items.forEach((t) => children.push(new Paragraph({ numbering: { reference: "num", level: 0 }, children: runs(t) }))); break;
    case "table": children.push(table(b)); children.push(new Paragraph({ children: [] })); break;
    case "code": clean(b.text).split("\n").forEach((line) => children.push(new Paragraph({
      children: [new TextRun({ text: line || " ", font: MONO, size: 15 })],
      shading: { type: ShadingType.CLEAR, color: "auto", fill: "F2F2F2" }, spacing: { after: 0 } }))); children.push(new Paragraph({ children: [] })); break;
    case "pagebreak": children.push(new Paragraph({ pageBreakBefore: true, children: [] })); break;
    default: children.push(para(b.text || ""));
  }
}

const doc = new Document({
  creator: "ESG_Text_Based_Incentives pipeline", title: clean(spec.title),
  styles: { default: { document: { run: { font: FONT, size: 20 } } } },
  numbering: { config: [
    { reference: "bul", levels: [0, 1, 2].map((l) => ({ level: l, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 360 * (l + 1), hanging: 260 } } } })) },
    { reference: "num", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 400, hanging: 300 } } } }] },
  ] },
  sections: [{
    properties: { page: { size: { width: PAGE_W, height: 16838 }, margin: { top: MARGIN, bottom: MARGIN, left: MARGIN, right: MARGIN } } },
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT,
      children: [new TextRun({ text: clean(spec.header || spec.title), size: 16, color: "808080", font: FONT })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [new TextRun({ children: ["Page ", PageNumber.CURRENT, " / ", PageNumber.TOTAL_PAGES], size: 16, color: "808080", font: FONT })] })] }) },
    children,
  }],
});
Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(outPath, buf); console.log("wrote", outPath); });
