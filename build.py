#!/usr/bin/env python3
"""
WhatTheChip? — Build Script
=======================
Gera o site multi-página a partir dos arquivos de conteúdo e do template.

Uso:
    python3 build.py

Saída: pasta  docs/  com todos os HTMLs prontos para abrir no navegador
       ou publicar no GitHub Pages.

Estrutura:
    _template/
        template.html   ← topbar + sidebar + CSS link + JS link
        style.css       ← design global (edite aqui para mudar o visual)
        script.js       ← busca e scroll-spy
    _content/
        index.html      ← conteúdo da página inicial
        evolucao.html   ← conteúdo da página de evolução
        ...             ← um arquivo por página
    build.py            ← este script
    docs/               ← saída gerada (GitHub Pages serve daqui)
"""

import os
import re
import json
import shutil

# ── Configuração ───────────────────────────────────────────────────────────────

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
TEMPLATE   = os.path.join(BASE_DIR, '_template', 'template.html')
CONTENT_DIR = os.path.join(BASE_DIR, '_content')
OUTPUT_DIR  = os.path.join(BASE_DIR, 'docs')

# Ordem das páginas (define prev/next)
PAGES = [
    {'file': 'index',        'title': 'Apresentação — WhatTheChip?'},
    {'file': 'aprender',     'title': '1.1 O que você vai aprender — WhatTheChip?'},
    {'file': 'o-que-e-chip', 'title': '1.2 O que é um Chip — WhatTheChip?'},
    {'file': 'evolucao',     'title': '1.3 Evolução: do pino à esfera — WhatTheChip?'},
    {'file': 'metodologia',  'title': '1.4 Metodologia de Identificação — WhatTheChip?'},
    {'file': 'tipos',        'title': '1.5 Tipos de Chip — WhatTheChip?'},
    {'file': 'fabricantes',  'title': '2. Identificação por Fabricante — WhatTheChip?'},
    {'file': 'fab-samsung',    'title': '2.1 Samsung — WhatTheChip?'},
    {'file': 'fab-hynix',      'title': '2.2 SK Hynix — WhatTheChip?'},
    {'file': 'fab-micron',     'title': '2.3 Micron — WhatTheChip?'},
    {'file': 'fab-elpida',     'title': '2.4 Elpida Memory — WhatTheChip?'},
    {'file': 'fab-toshiba',    'title': '2.5 Toshiba / Kioxia — WhatTheChip?'},
    {'file': 'fab-sandisk',    'title': '2.6 SanDisk / WD — WhatTheChip?'},
    {'file': 'fab-nanya',      'title': '2.7 Nanya Technology — WhatTheChip?'},
    {'file': 'fab-kingston',   'title': '2.8 Kingston — WhatTheChip?'},
    {'file': 'fab-rayson',     'title': '2.9 Rayson — WhatTheChip?'},
    {'file': 'fab-issi',       'title': '2.10 ISSI — WhatTheChip?'},
    {'file': 'fab-gigadevice', 'title': '2.11 GigaDevice — WhatTheChip?'},
    {'file': 'prefixos',     'title': '3. Tabela Rápida de Prefixos — WhatTheChip?'},
    {'file': 'remarked',     'title': '4. Chips Remarked / Counterfeit — WhatTheChip?'},
    {'file': 'viabilidade',  'title': '5. Hierarquia de Viabilidade — WhatTheChip?'},
    {'file': 'soc',          'title': '6. CPUs / SoCs — WhatTheChip?'},
    {'file': 'encerramento', 'title': 'Encerramento — WhatTheChip?'},
    {'file': 'contato',      'title': 'Contato — WhatTheChip?'},
]

# ── Funções ────────────────────────────────────────────────────────────────────

def extract_prefix_data():
    """Lê _content/prefixos.html e extrai os dados da tabela como JSON.
    Chamado a cada build — garante que o buscador da página inicial
    sempre reflita os prefixos mais recentes da tabela."""
    path = os.path.join(CONTENT_DIR, 'prefixos.html')
    with open(path, 'r', encoding='utf-8') as f:
        html = f.read()
    rows = re.findall(
        r'<tr>\s*<td><code>(.*?)</code></td>\s*<td>(.*?)</td>\s*<td>(.*?)</td>\s*</tr>',
        html, re.DOTALL
    )
    data = []
    for prefix, fab, tipo in rows:
        data.append({
            'prefix': re.sub(r'<[^>]+>', '', prefix).strip(),
            'fab':    re.sub(r'<[^>]+>', '', fab).strip(),
            'tipo':   re.sub(r'<[^>]+>', '', tipo).strip(),
        })
    return json.dumps(data, ensure_ascii=False)


def make_pagination(index):
    """Gera bloco de navegação anterior / próxima página."""
    parts = []
    parts.append('<div class="page-nav">')
    if index > 0:
        prev = PAGES[index - 1]
        parts.append(
            f'<a class="page-nav-btn prev" href="{prev["file"]}.html">'
            f'← {prev["title"].split(" — ")[0]}</a>'
        )
    else:
        parts.append('<span></span>')

    if index < len(PAGES) - 1:
        nxt = PAGES[index + 1]
        parts.append(
            f'<a class="page-nav-btn next" href="{nxt["file"]}.html">'
            f'{nxt["title"].split(" — ")[0]} →</a>'
        )
    else:
        parts.append('<span></span>')

    parts.append('</div>')
    return '\n'.join(parts)


def build():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Copia style.css e script.js para a pasta site/
    for asset in ['style.css', 'script.js']:
        src = os.path.join(BASE_DIR, '_template', asset)
        dst = os.path.join(OUTPUT_DIR, asset)
        if os.path.exists(src):
            shutil.copy2(src, dst)
            print(f'  Copiado: {asset}')

    # Copia imagens do diretório pai para docs/
    image_exts = {'.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp', '.avif'}
    parent_dir = os.path.dirname(BASE_DIR)
    for fname in os.listdir(parent_dir):
        if os.path.splitext(fname)[1].lower() in image_exts:
            src = os.path.join(parent_dir, fname)
            dst = os.path.join(OUTPUT_DIR, fname)
            shutil.copy2(src, dst)
            print(f'  Copiado: {fname}')

    # Lê o template
    with open(TEMPLATE, 'r', encoding='utf-8') as f:
        template = f.read()

    # Extrai dados de prefixos para o buscador da página inicial
    prefix_data = extract_prefix_data()
    print(f'  Prefixos indexados: {prefix_data.count("prefix")} entradas')

    for i, page in enumerate(PAGES):
        page_file = page['file']
        content_path = os.path.join(CONTENT_DIR, f'{page_file}.html')

        if not os.path.exists(content_path):
            print(f'  AVISO: {content_path} não encontrado, pulando.')
            continue

        with open(content_path, 'r', encoding='utf-8') as f:
            raw_content = f.read()

        # Remove a linha de comentário com TITLE se existir
        raw_content = re.sub(r'^<!-- TITLE:.*?-->\n?', '', raw_content, flags=re.MULTILINE)

        # Injeta dados de prefixos no buscador (apenas na index)
        raw_content = raw_content.replace('{{PREFIX_DATA}}', prefix_data)
        raw_content = raw_content.replace('{{PREFIX_COUNT}}', str(prefix_data.count('"prefix"')))

        # Monta o HTML final
        pagination = make_pagination(i)
        html = template
        html = html.replace('{{TITLE}}',      page['title'])
        html = html.replace('{{PAGE_ID}}',    page_file)
        html = html.replace('{{CONTENT}}',    raw_content)
        html = html.replace('{{PAGINATION}}', pagination)

        out_path = os.path.join(OUTPUT_DIR, f'{page_file}.html')
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(html)

        size_kb = os.path.getsize(out_path) // 1024
        print(f'  Gerado: {page_file}.html ({size_kb} KB)')

    print(f'\nBuild completo! Abra docs/index.html no navegador.')
    print(f'Pasta: {OUTPUT_DIR}')


if __name__ == '__main__':
    build()
