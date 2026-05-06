/**
 * WhatTheChip — Page Editor
 * =========================
 * Editor de código HTML baseado em CodeMirror 5, carregado dinamicamente
 * via CDN. Substitui o textarea padrão do Django admin por um editor com:
 *   - Syntax highlighting HTML/XML (tema Dracula)
 *   - Numeração de linhas
 *   - Toolbar compacta de templates
 *   - Barra de status (linha/coluna + contagem de chars)
 *   - Auto-close tags, match-brackets
 */

(function () {
  'use strict';

  /* ── CDN ────────────────────────────────────────────────────────────────── */
  var CM = 'https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16';

  /* ── Templates agrupados ────────────────────────────────────────────────── */
  var GROUPS = [
    {
      label: 'Anatomy',
      items: [
        {
          label: 'Geral',
          title: 'Tabela de anatomia genérica — edite os <th> com os chars do PN',
          html:
`<div class="tbl-wrap">
  <table>
    <thead>
      <tr class="decode-gabarito">
        <th>X</th><th>X</th><th>X</th><th>X</th><th>X</th><th>-</th><th>X</th><th>X</th>
      </tr>
    </thead>
    <tbody>
      <tr class="decode-labels">
        <td>FAM</td><td>SÉRIE</td><td colspan="2">CAPACIDADE</td><td>GEN</td><td>-</td><td>ENC</td><td>VCC</td>
      </tr>
      <tr class="decode-example">
        <td>Descrição 1</td><td>Descrição 2</td><td colspan="2">Descrição 3</td><td>Descrição 4</td><td>-</td><td>Descrição 5</td><td>Descrição 6</td>
      </tr>
    </tbody>
  </table>
</div>`,
        },
        {
          label: 'eMMC / UFS',
          title: 'Gabarito eMMC ou UFS com capacidade e geração',
          html:
`<div class="tbl-wrap">
  <table>
    <thead>
      <tr class="decode-gabarito">
        <th>X</th><th>X</th><th>X</th><th>X</th><th>X</th><th>X</th><th>X</th><th>X</th><th>X</th><th>-</th><th>X</th><th>X</th>
      </tr>
    </thead>
    <tbody>
      <tr class="decode-labels">
        <td colspan="3">FAM / SÉRIE</td><td>CAP</td><td colspan="2">ORG</td><td>GEN</td><td>ENC</td><td>VCC</td><td>-</td><td colspan="2">REV</td>
      </tr>
      <tr class="decode-example">
        <td colspan="3">—</td><td>—</td><td colspan="2">—</td><td>—</td><td>BGA</td><td>—</td><td>-</td><td colspan="2">—</td>
      </tr>
    </tbody>
  </table>
</div>`,
        },
        {
          label: 'DRAM',
          title: 'Gabarito para DDR1–DDR5 / LPDDR standalone',
          html:
`<div class="tbl-wrap">
  <table>
    <thead>
      <tr class="decode-gabarito">
        <th>X</th><th>X</th><th>X</th><th>X</th><th>X</th><th>X</th><th>X</th><th>X</th><th>-</th><th>X</th><th>X</th><th>X</th>
      </tr>
    </thead>
    <tbody>
      <tr class="decode-labels">
        <td>FAM</td><td colspan="3">DENSIDADE / ORG</td><td>GEN/VCC</td><td>DIE</td><td>REV</td><td>ENC</td><td>-</td><td colspan="3">VELOCIDADE</td>
      </tr>
      <tr class="decode-example">
        <td>DRAM</td><td colspan="3">—</td><td>—</td><td>—</td><td>—</td><td>BGA</td><td>-</td><td colspan="3">—</td>
      </tr>
    </tbody>
  </table>
</div>`,
        },
        {
          label: 'NAND Flash',
          title: 'Gabarito para NAND Flash standalone',
          html:
`<div class="tbl-wrap">
  <table>
    <thead>
      <tr class="decode-gabarito">
        <th>X</th><th>X</th><th>X</th><th>X</th><th>X</th><th>X</th><th>X</th><th>-</th><th>X</th><th>X</th><th>X</th><th>X</th><th>-</th><th>X</th>
      </tr>
    </thead>
    <tbody>
      <tr class="decode-labels">
        <td>TIPO</td><td>SÉRIE</td><td colspan="3">DENSIDADE (Gb)</td><td colspan="2">LARGURA</td><td>-</td><td>VCC</td><td>ENC</td><td colspan="2">SILÍCIO</td><td>-</td><td>DIES</td>
      </tr>
      <tr class="decode-example">
        <td>Flash</td><td>—</td><td colspan="3">—</td><td colspan="2">—</td><td>-</td><td>—</td><td>BGA</td><td colspan="2">—</td><td>-</td><td>—</td>
      </tr>
    </tbody>
  </table>
</div>`,
        },
        {
          label: 'eMCP / uMCP',
          title: 'Gabarito para eMCP / uMCP (NAND + RAM no mesmo package)',
          html:
`<div class="tbl-wrap">
  <table>
    <thead>
      <tr class="decode-gabarito">
        <th>X</th><th>X</th><th>X</th><th>X</th><th>X</th><th>X</th><th>X</th><th>X</th><th>-</th><th>X</th><th>X</th><th>X</th><th>X</th><th>X</th><th>X</th>
      </tr>
    </thead>
    <tbody>
      <tr class="decode-labels">
        <td colspan="2">CAP NAND</td><td colspan="4">FAMÍLIA</td><td colspan="2">CAP RAM</td><td>-</td><td>REV</td><td colspan="2">GEN RAM</td><td colspan="3">DIE / PKG</td>
      </tr>
      <tr class="decode-example">
        <td colspan="2">—</td><td colspan="4">eMCP</td><td colspan="2">—</td><td>-</td><td>—</td><td colspan="2">—</td><td colspan="3">—</td>
      </tr>
    </tbody>
  </table>
</div>`,
        },
      ],
    },
    {
      label: 'Tabelas',
      items: [
        {
          label: 'Prefixos',
          title: 'Tabela mestra de decodificação de prefixos (Prefixo / Categoria / Tecnologia / Direcionamento)',
          html:
`<h4>Tabela Mestra de Decodificação &mdash; Prefixos <small style="font-weight:normal;color:#666">(Leitura Rápida na Esteira)</small></h4>
<div class="tbl-wrap">
  <table>
    <thead>
      <tr>
        <th>Prefixo</th>
        <th>Categoria</th>
        <th>Tecnologia / Geração</th>
        <th>Direcionamento</th>
      </tr>
    </thead>
    <tbody>
      <tr><td><code>XXX</code></td><td>Categoria</td><td>Geração</td><td>Direcionamento</td></tr>
      <tr><td><code>XXX</code></td><td>Categoria</td><td>Geração</td><td>Direcionamento</td></tr>
    </tbody>
  </table>
</div>`,
        },
        {
          label: '2 colunas',
          title: 'Tabela simples de 2 colunas (Código / Significado)',
          html:
`<div class="tbl-wrap">
  <table>
    <thead>
      <tr><th>Código</th><th>Significado</th></tr>
    </thead>
    <tbody>
      <tr><td><code>X</code></td><td>Descrição</td></tr>
      <tr><td><code>X</code></td><td>Descrição</td></tr>
    </tbody>
  </table>
</div>`,
        },
      ],
    },
    {
      label: 'Callouts',
      items: [
        {
          label: 'Info',
          title: 'Caixa de nota informativa',
          html:
`<div class="nota">
  <strong>Nota:</strong> Texto da nota aqui.
</div>`,
        },
        {
          label: 'Aviso',
          title: 'Caixa de aviso / atenção',
          html:
`<div class="nota warn">
  <strong>Atenção:</strong> Texto do aviso aqui.
</div>`,
        },
      ],
    },
  ];

  /* ── Utilitários de carregamento ────────────────────────────────────────── */
  function loadCSS(href) {
    var el = document.createElement('link');
    el.rel = 'stylesheet';
    el.href = href;
    document.head.appendChild(el);
  }

  function loadScript(src, cb) {
    var el = document.createElement('script');
    el.src = src;
    el.onload = cb;
    document.head.appendChild(el);
  }

  /* ── Estilos inline ─────────────────────────────────────────────────────── */
  function injectStyles() {
    var css = `
      /* ── Wrapper do editor ── */
      #wtc-editor-wrap {
        border: 1px solid #2d2d2d;
        border-radius: 6px;
        overflow: hidden;
        font-family: 'Fira Code', 'JetBrains Mono', 'Courier New', monospace;
        box-shadow: 0 2px 12px rgba(0,0,0,.25);
      }

      /* ── Toolbar ── */
      #wtc-toolbar {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 6px 10px;
        padding: 7px 10px;
        background: #21222c;
        border-bottom: 1px solid #383a4a;
      }
      .wtc-group {
        display: flex;
        align-items: center;
        gap: 3px;
      }
      .wtc-group-sep {
        width: 1px;
        height: 18px;
        background: #383a4a;
        margin: 0 2px;
      }
      .wtc-group-label {
        font-size: 9px;
        font-weight: 700;
        letter-spacing: .06em;
        text-transform: uppercase;
        color: #6272a4;
        margin-right: 4px;
        font-family: system-ui, sans-serif;
        white-space: nowrap;
      }
      .wtc-btn {
        font-size: 11px;
        padding: 2px 9px;
        line-height: 18px;
        background: #282a36;
        color: #f8f8f2;
        border: 1px solid #44475a;
        border-radius: 4px;
        cursor: pointer;
        font-family: 'Fira Code', 'Courier New', monospace;
        white-space: nowrap;
        transition: background .1s, border-color .1s;
        user-select: none;
      }
      .wtc-btn:hover {
        background: #44475a;
        border-color: #6272a4;
        color: #fff;
      }
      .wtc-btn:active {
        background: #6272a4;
        border-color: #bd93f9;
      }

      /* ── CodeMirror overrides ── */
      #wtc-editor-wrap .CodeMirror {
        height: 680px;
        font-size: 13px;
        font-family: 'Fira Code', 'JetBrains Mono', 'Courier New', monospace;
        line-height: 1.6;
        border: none;
        border-radius: 0;
      }
      #wtc-editor-wrap .CodeMirror-scroll {
        padding-bottom: 40px;
      }

      /* ── Barra de status ── */
      #wtc-statusbar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 4px 12px;
        background: #21222c;
        border-top: 1px solid #383a4a;
        font-size: 11px;
        color: #6272a4;
        font-family: system-ui, sans-serif;
      }
      #wtc-statusbar span { color: #f8f8f2; }
    `;
    var style = document.createElement('style');
    style.textContent = css;
    document.head.appendChild(style);
  }

  /* ── Constrói toolbar ───────────────────────────────────────────────────── */
  function buildToolbar(editor) {
    var bar = document.createElement('div');
    bar.id = 'wtc-toolbar';

    GROUPS.forEach(function (group, gi) {
      if (gi > 0) {
        var sep = document.createElement('div');
        sep.className = 'wtc-group-sep';
        bar.appendChild(sep);
      }

      var grpEl = document.createElement('div');
      grpEl.className = 'wtc-group';

      var lbl = document.createElement('span');
      lbl.className = 'wtc-group-label';
      lbl.textContent = group.label;
      grpEl.appendChild(lbl);

      group.items.forEach(function (item) {
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'wtc-btn';
        btn.textContent = item.label;
        btn.title = item.title || '';
        btn.addEventListener('click', function () {
          editor.replaceSelection('\n' + item.html + '\n');
          editor.focus();
        });
        grpEl.appendChild(btn);
      });

      bar.appendChild(grpEl);
    });

    return bar;
  }

  /* ── Barra de status ────────────────────────────────────────────────────── */
  function buildStatusBar(editor) {
    var bar = document.createElement('div');
    bar.id = 'wtc-statusbar';

    var pos = document.createElement('div');
    pos.innerHTML = 'Linha <span id="wtc-line">1</span> : Col <span id="wtc-col">1</span>';

    var chars = document.createElement('div');
    chars.innerHTML = '<span id="wtc-chars">0</span> chars';

    bar.appendChild(pos);
    bar.appendChild(chars);

    editor.on('cursorActivity', function () {
      var cur = editor.getCursor();
      document.getElementById('wtc-line').textContent = cur.line + 1;
      document.getElementById('wtc-col').textContent  = cur.ch + 1;
    });
    editor.on('change', function () {
      document.getElementById('wtc-chars').textContent = editor.getValue().length;
    });

    return bar;
  }

  /* ── Inicializa o editor ────────────────────────────────────────────────── */
  function initEditor() {
    var textarea = document.getElementById('id_content');
    if (!textarea) return;

    injectStyles();
    loadCSS(CM + '/codemirror.min.css');
    loadCSS(CM + '/theme/dracula.min.css');

    loadScript(CM + '/codemirror.min.js', function () {
      loadScript(CM + '/mode/xml/xml.min.js', function () {
        loadScript(CM + '/addon/edit/closetag.min.js', function () {
          loadScript(CM + '/addon/edit/matchbrackets.min.js', function () {

            var editor = window.CodeMirror.fromTextArea(textarea, {
              mode:           'xml',
              theme:          'dracula',
              lineNumbers:    true,
              lineWrapping:   true,
              autoCloseTags:  true,
              matchBrackets:  true,
              indentWithTabs: false,
              tabSize:        2,
              extraKeys: {
                Tab: function (cm) {
                  cm.replaceSelection('  ', 'end');
                },
              },
            });

            // Embrulha tudo num wrapper estilizado
            var wrap = editor.getWrapperElement();
            var outer = document.createElement('div');
            outer.id = 'wtc-editor-wrap';
            wrap.parentNode.insertBefore(outer, wrap);

            var toolbar   = buildToolbar(editor);
            var statusbar = buildStatusBar(editor);

            outer.appendChild(toolbar);
            outer.appendChild(wrap);
            outer.appendChild(statusbar);

            // Garante que o valor seja sincronizado para o textarea antes de salvar
            var form = textarea.closest('form');
            if (form) {
              form.addEventListener('submit', function () {
                editor.save();
              });
            }

            // Atualiza contagem inicial
            document.getElementById('wtc-chars').textContent = editor.getValue().length;

          }); // matchbrackets
        }); // closetag
      }); // xml
    }); // codemirror
  }

  document.addEventListener('DOMContentLoaded', initEditor);

})();
