// ─────────────────────────────────────────────────────────────────────────────
// A FICHA DO COMPRADOR, RODANDO DE VERDADE (2026-09-07).
//
// Existe por causa do bug do dólar do herói: o `tests_par_de_moedas` cobrava o
// JavaScript LENDO o arquivo, e leitura só prova que um trecho existe — nunca
// que a tela chega no número certo. Este harness carrega o HTML que o Django
// serviu num DOM, deixa o script da página rodar, digita a recusa como o
// comprador digita e devolve o que a tela DIZ.
//
//   uso:  node heroi.mjs <ficha.html> '{"<pk da linha>": <recusa>, ...}'
//   saída: JSON {antes, depois, digitou, campos}
//
// `antes` é depois do carregamento e ANTES de qualquer tecla — e não é
// detalhe: o `recalcular()` roda no load, então era ali que o número já saía
// errado, antes de o comprador tocar em nada.
// ─────────────────────────────────────────────────────────────────────────────
import { readFileSync } from 'node:fs';
import { JSDOM } from 'jsdom';

const html = readFileSync(process.argv[2], 'utf8');
const recusas = JSON.parse(process.argv[3] || '{}');

// ⚠ ERROS NÃO CAPTURADOS derrubam o `recalcular()` NO MEIO: a linha já foi
//   escrita e a faixa e o rodapé não. A tela fica com a linha certa e o total
//   velho — plausível, e errado. Aconteceu de verdade em 07/09 (tirei uma
//   variável junto com a classe que a usava) e o harness passou porque ele
//   só olhava o herói. Agora ele escuta.
const erros = [];
const dom = new JSDOM(html, {
  runScripts: 'dangerously',
  pretendToBeVisual: true,
  url: 'http://localhost/compras/1/',
  virtualConsole: new (await import('jsdom')).VirtualConsole()
    .on('jsdomError', e => erros.push(String(e && e.message || e)))
    .on('error', (...a) => erros.push(a.map(String).join(' '))),
});
const w = dom.window, d = w.document;
w.addEventListener('error', e => erros.push(String(e.message || e)));
// A ficha fala com o servidor (autosave do rascunho) e com o htmx. Nenhum dos
// dois existe aqui e nenhum dos dois participa da conta — dublês mudos, para
// o script não morrer no meio e levar o teste junto com um falso verde.
w.fetch = () => new Promise(() => {});
w.htmx = { process: () => {}, ajax: () => {}, on: () => {} };

const ler = (id) => {
  const e = d.getElementById(id);
  return e ? e.textContent.trim() : null;
};
const texto = (sel) => {
  const e = d.querySelector(sel);
  return e ? e.textContent.trim() : null;
};
const foto = () => ({
  kUsd: ler('k-usd'), kRmb: ler('k-rmb'),          // o HERÓI (cartão do topo)
  tUsd: ler('t-pagar-usd'), tRmb: ler('t-pagar-rmb'),  // o RODAPÉ da tabela
  // A FAIXA da 1ª marca e o RODAPÉ, célula a célula. Sem eles o harness não
  // vê um `recalcular()` que morre depois de escrever a linha.
  gRej: texto('[data-grej="0"]'), gOk: texto('[data-gok="0"]'),
  gVal: texto('[data-gval="0"]'), gPerda: texto('[data-gperda="0"]'),
  tRej: ler('t-rej'), tAce: ler('t-ace'), tRejv: ler('t-rejv'),
});

const antes = foto();

let digitou = 0;
for (const [pk, n] of Object.entries(recusas)) {
  const campo = d.querySelector('.rjin[data-rj="' + pk + '"]');
  if (!campo) continue;
  campo.value = String(n);
  // `input`, o mesmo evento que o `addEventListener` da página escuta.
  campo.dispatchEvent(new w.Event('input', { bubbles: true }));
  digitou += 1;
}

console.log(JSON.stringify({
  antes, depois: foto(), digitou, erros,
  campos: d.querySelectorAll('.rjin[data-qty]').length,
}));
