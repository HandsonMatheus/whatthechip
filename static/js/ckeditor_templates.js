/**
 * WhatTheChip — Templates do CKEditor
 *
 * Aparece no editor pelo botão "Templates" na toolbar.
 * Para adicionar novos templates, copie um bloco { title, html }
 * e ajuste o conteúdo. O HTML inserido pode ser editado normalmente
 * no editor após a inserção.
 */
CKEDITOR.addTemplates('default', {
  imagesPath: '',
  templates: [

    /* ── ANATOMY TABLE — padrão geral ─────────────────────── */
    {
      title: 'Anatomy Table — Padrão (3 colunas exemplo)',
      description: 'Tabela de gabarito de part number. Edite os <th> (caracteres), a linha de labels e a linha de descrição.',
      html: `
<div class="tbl-wrap" style="margin-bottom:20px;">
  <table class="anatomy-table">
    <thead>
      <tr>
        <th>X</th><th>X</th><th>X</th><th>X</th><th>X</th><th>-</th><th>X</th><th>X</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>LABEL 1</td><td>LABEL 2</td><td>LABEL 3</td><td>LABEL 4</td><td>LABEL 5</td><td>SEP</td><td colspan="2">LABEL 6</td>
      </tr>
      <tr>
        <td>Valor 1</td><td>Valor 2</td><td>Valor 3</td><td>Valor 4</td><td>Valor 5</td><td>Traço</td><td colspan="2">Valor 6</td>
      </tr>
    </tbody>
  </table>
</div>`
    },

    /* ── ANATOMY TABLE — DRAM (padrão Samsung/Hynix/Micron) ── */
    {
      title: 'Anatomy Table — DRAM',
      description: 'Gabarito para chips de memória DRAM (DDR1–DDR5). Preencha os <th> com os caracteres do part number.',
      html: `
<div class="tbl-wrap" style="margin-bottom:20px;">
  <table class="anatomy-table">
    <thead>
      <tr>
        <th>X</th><th>X</th><th>X</th><th>X</th><th>X</th><th>X</th><th>X</th><th>X</th><th>-</th><th>X</th><th>X</th><th>X</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>FAM</td><td colspan="3">DENSIDADE / ORG</td><td>GEN/VCC</td><td>DIE (FAB)</td><td>REV</td><td>ENC</td><td>SEP</td><td colspan="3">VELOCIDADE</td>
      </tr>
      <tr>
        <td>DRAM</td><td colspan="3">—</td><td>—</td><td>—</td><td>—</td><td>BGA</td><td>Traço</td><td colspan="3">—</td>
      </tr>
    </tbody>
  </table>
</div>`
    },

    /* ── ANATOMY TABLE — NAND Flash ───────────────────────── */
    {
      title: 'Anatomy Table — NAND Flash',
      description: 'Gabarito para chips de memória NAND Flash (SSD, eMMC, UFS).',
      html: `
<div class="tbl-wrap" style="margin-bottom:20px;">
  <table class="anatomy-table">
    <thead>
      <tr>
        <th>X</th><th>X</th><th>X</th><th>X</th><th>X</th><th>X</th><th>X</th><th>-</th><th>X</th><th>X</th><th>X</th><th>X</th><th>-</th><th>X</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>TIPO</td><td>SÉRIE</td><td colspan="3">DENSIDADE (Gb)</td><td colspan="2">LARGURA</td><td>SEP</td><td>VCC</td><td>ENC</td><td colspan="2">SILÍCIO BASE</td><td>SEP</td><td>QTD DIES</td>
      </tr>
      <tr>
        <td>Flash</td><td>—</td><td colspan="3">—</td><td colspan="2">—</td><td>Traço</td><td>—</td><td>BGA</td><td colspan="2">—</td><td>Traço</td><td>—</td>
      </tr>
    </tbody>
  </table>
</div>`
    },

    /* ── ANATOMY TABLE — eMCP / Combo ─────────────────────── */
    {
      title: 'Anatomy Table — eMCP (Combo NAND+RAM)',
      description: 'Gabarito para chips eMCP que combinam NAND Flash e RAM no mesmo package.',
      html: `
<div class="tbl-wrap" style="margin-bottom:20px;">
  <table class="anatomy-table">
    <thead>
      <tr>
        <th>X</th><th>X</th><th>X</th><th>X</th><th>X</th><th>X</th><th>X</th><th>X</th><th>-</th><th>X</th><th>X</th><th>X</th><th>X</th><th>X</th><th>X</th><th>X</th><th>X</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td colspan="2">CAP NAND</td><td colspan="4">FAMÍLIA</td><td colspan="2">CAP RAM</td><td>SEP</td><td>REV</td><td colspan="2">GEN RAM</td><td colspan="5">DIE / PACKAGE</td>
      </tr>
      <tr>
        <td colspan="2">—</td><td colspan="4">eMCP (Combo)</td><td colspan="2">—</td><td>Traço</td><td>—</td><td colspan="2">—</td><td colspan="5">—</td>
      </tr>
    </tbody>
  </table>
</div>`
    },

    /* ── TABELA MESTRA DE PREFIXOS (por fabricante) ──────── */
    {
      title: 'Tabela Mestra de Prefixos',
      description: 'Tabela de decodificação rápida de prefixos por fabricante. 4 colunas: Prefixo, Categoria, Tecnologia/Geração, Direcionamento.',
      html: `
<h4 id="fab-master">Tabela Mestra de Decodificação — Prefixos Globais FABRICANTE &nbsp;<small style="font-weight:normal;color:#666">(Leitura Rápida na Esteira)</small></h4>
<div class="tbl-wrap">
  <table>
    <thead>
      <tr>
        <th>Prefixo</th>
        <th>Categoria Principal</th>
        <th>Tecnologia / Geração</th>
        <th>Direcionamento (Fluxo)</th>
      </tr>
    </thead>
    <tbody>

      <!-- CATEGORIA A -->
      <tr><td><code>XXX</code></td><td>Categoria</td><td>Geração</td><td>Direcionamento</td></tr>

      <!-- CATEGORIA B -->
      <tr><td><code>XXX</code></td><td>Categoria</td><td>Geração</td><td>Direcionamento</td></tr>
      <!-- prefixo com nota extra: -->
      <tr><td><code>XXX</code> <small>(Ex: XA, XB)</small></td><td>Categoria</td><td>Geração</td><td>Direcionamento</td></tr>
      <!-- prefixo com duas linhas: -->
      <tr><td><code>XXX</code><br><code>YYY</code></td><td>Categoria</td><td>Geração</td><td>Direcionamento</td></tr>

    </tbody>
  </table>
</div>`
    },

  ]
});
