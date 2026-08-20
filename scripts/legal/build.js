const fs = require('fs');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  PageBreak, BorderStyle, Table, TableRow, TableCell, WidthType, ShadingType,
  Header, Footer, PageNumber, TabStopType, TabStopPosition,
} = require('docx');
const { EN, ES, PT, FONTES } = require('./content.js');

const INK = '161616';
const GREY = '697077';
const BLUE = '0F62FE';
const FONT = 'Calibri';

const p = (text, o = {}) => new Paragraph({
  alignment: o.align || AlignmentType.JUSTIFIED,
  spacing: { after: o.after === undefined ? 140 : o.after, line: 276 },
  indent: o.indent,
  border: o.border,
  children: [new TextRun({
    text, font: FONT, size: o.size || 21,
    bold: o.bold, italics: o.italics,
    color: o.color || INK,
  })],
});

const h1 = (text) => new Paragraph({
  heading: HeadingLevel.HEADING_1,
  spacing: { before: 260, after: 160 },
  children: [new TextRun({ text, font: FONT, size: 26, bold: true, color: INK })],
});

const kicker = (text) => new Paragraph({
  spacing: { after: 60 },
  children: [new TextRun({
    text, font: FONT, size: 17, bold: true, color: BLUE,
    characterSpacing: 30,
  })],
});

const rule = () => new Paragraph({
  spacing: { after: 200 },
  border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: BLUE, space: 6 } },
  children: [new TextRun({ text: '', font: FONT, size: 2 })],
});

// ── Bloco de assinatura: tabela 2 colunas, larguras em DXA ────────────────
const W = 9360;                       // largura útil A4 com margens de 2,5 cm
const campo = (rot) => new TableCell({
  width: { size: W / 2, type: WidthType.DXA },
  margins: { top: 220, bottom: 60, left: 0, right: 200 },
  borders: {
    top: { style: BorderStyle.NONE }, left: { style: BorderStyle.NONE },
    right: { style: BorderStyle.NONE },
    bottom: { style: BorderStyle.SINGLE, size: 4, color: GREY },
  },
  children: [p('', { after: 0 })],
  __rot: rot,
});

const linhaAssinatura = (a, b) => new TableRow({
  children: [campo(a), campo(b)],
});

const rotulos = (a, b) => new TableRow({
  children: [a, b].map((t) => new TableCell({
    width: { size: W / 2, type: WidthType.DXA },
    margins: { top: 40, bottom: 200, left: 0, right: 200 },
    borders: {
      top: { style: BorderStyle.NONE }, left: { style: BorderStyle.NONE },
      right: { style: BorderStyle.NONE }, bottom: { style: BorderStyle.NONE },
    },
    children: [p(t, { size: 17, color: GREY, after: 0,
                      align: AlignmentType.LEFT })],
  })),
});

const blocoAssinatura = (L) => new Table({
  columnWidths: [W / 2, W / 2],
  width: { size: W, type: WidthType.DXA },
  rows: [
    linhaAssinatura(), rotulos(L.fCompany, L.fName),
    linhaAssinatura(), rotulos(L.fDate, L.fSign),
  ],
});

// ── Uma parte (um idioma) ─────────────────────────────────────────────────
function parte(L, primeira) {
  const out = [];
  if (!primeira) out.push(new Paragraph({ children: [new PageBreak()] }));
  out.push(kicker(L.lang));
  out.push(new Paragraph({
    spacing: { after: 60 },
    children: [new TextRun({ text: L.title, font: FONT, size: 40, bold: true, color: INK })],
  }));
  out.push(p(L.sub, { size: 21, color: GREY, align: AlignmentType.LEFT, after: 60 }));
  out.push(rule());

  out.push(h1(L.preambleH));
  L.preamble.forEach((t) => out.push(p(t)));

  [[L.s1H, L.s1], [L.s2H, L.s2], [L.s3H, L.s3]].forEach(([tit, corpo]) => {
    out.push(h1(tit));
    corpo.forEach((t) => out.push(p(t)));
  });

  out.push(h1(L.s4H));
  FONTES.forEach(([titulo, url]) => {
    out.push(p(titulo, { size: 19, after: 20, align: AlignmentType.LEFT }));
    out.push(p(url, { size: 17, color: GREY, after: 120, align: AlignmentType.LEFT }));
  });

  out.push(h1(L.closeH));
  out.push(p(L.close));
  out.push(blocoAssinatura(L));
  return out;
}

const doc = new Document({
  creator: 'WhatTheChip',
  title: 'Legal clarification — recovered electronic integrated circuits to Macao SAR',
  description: 'Basel Convention status, Macao SAR import licensing and end-use declaration.',
  styles: {
    default: {
      heading1: { run: { font: FONT, size: 26, bold: true, color: INK } },
    },
  },
  sections: [{
    properties: {
      page: { margin: { top: 1418, bottom: 1418, left: 1418, right: 1418 } },
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          spacing: { after: 0 },
          border: { bottom: { style: BorderStyle.SINGLE, size: 3, color: 'DDE1E6', space: 6 } },
          children: [new TextRun({
            text: 'WhatTheChip · Legal clarification / Aclaración legal / Esclarecimento legal',
            font: FONT, size: 15, color: GREY,
          })],
        })],
      }),
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }],
          children: [
            new TextRun({
              text: 'EN · ES · PT — issued on request of the carrier or competent authority',
              font: FONT, size: 15, color: GREY,
            }),
            new TextRun({ text: '\t', font: FONT, size: 15 }),
            new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 15, color: GREY }),
          ],
        })],
      }),
    },
    children: [
      ...parte(EN, true),
      ...parte(ES, false),
      ...parte(PT, false),
    ],
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync('../../ESCLARECIMENTO_LEGAL_MACAU_EN_ES_PT.docx', buf);
  console.log('ok', buf.length);
});
