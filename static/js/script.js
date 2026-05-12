
      // ── Mapa fab → slug de página (Django: /slug/) ────────────
      function fabToPage(fab) {
        var map = {
          'Samsung':             'fab-samsung',
          'SK Hynix':            'fab-hynix',
          'Hynix (era Hyundai)': 'fab-hynix',
          'Hyundai / Hynix':     'fab-hynix',
          'Micron':              'fab-micron',
          'Elpida':              'fab-elpida',
          'Toshiba / Kioxia':    'fab-toshiba',
          'SanDisk / WD':        'fab-sandisk',
          'Nanya':               'fab-nanya',
          'Kingston':            'fab-kingston',
          'Kingston (HyperX)':   'fab-kingston',
          'Rayson':              'fab-rayson',
          'ISSI':                'fab-issi',
          'GigaDevice':          'fab-gigadevice',
        };
        return map[fab] || 'prefixos';
      }

      // ── Highlight de linha ao chegar via busca ─────────────────
      // Detecta #highlight-K4H na URL, varre os <code> da página,
      // rola até a linha correspondente e pisca ela.
      (function () {
        var hash = window.location.hash;
        if (!hash.startsWith('#highlight-')) return;
        var target = hash.replace('#highlight-', '').toLowerCase();

        function tryHighlight() {
          var codes = document.querySelectorAll('table code');
          for (var i = 0; i < codes.length; i++) {
            var text = codes[i].textContent.trim().replace(/[^A-Za-z0-9]/g, '').toLowerCase();
            if (text.startsWith(target) || target.startsWith(text)) {
              var row = codes[i].closest('tr');
              if (!row) continue;
              history.replaceState(null, '', window.location.pathname);
              setTimeout(function(r) {
                return function() {
                  r.scrollIntoView({ behavior: 'smooth', block: 'center' });
                  r.classList.add('row-highlight');
                  setTimeout(function() { r.classList.remove('row-highlight'); }, 2400);
                };
              }(row), 320);
              return true;
            }
          }
          return false;
        }

        if (!tryHighlight()) {
          document.addEventListener('DOMContentLoaded', tryHighlight);
        }
      })();

      // TOC scroll spy
      const tocLinks = document.querySelectorAll("#toc a");
      const observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              const id = entry.target.id;
              tocLinks.forEach((l) =>
                l.classList.toggle(
                  "active",
                  l.getAttribute("href") === "#" + id,
                ),
              );
            }
          });
        },
        { rootMargin: "-5% 0px -85% 0px" },
      );
      document.querySelectorAll("[id]").forEach((el) => observer.observe(el));



  // ── Chip-type badges por fabricante ──────────────────────────
  (function() {
    var ALL_TYPES = [
      'eMMC', 'eMCP', 'uMCP', 'UFS', 'LPDDR', 'DDR', 'GDDR',
      'NAND Flash', 'NOR Flash', 'SRAM', 'CPU / SoC'
    ];

    var FAB_TYPES = {
      'fab-samsung':    ['eMMC', 'eMCP', 'uMCP', 'UFS', 'LPDDR', 'DDR', 'GDDR', 'NAND Flash', 'NOR Flash'],
      'fab-hynix':      ['eMMC', 'eMCP', 'uMCP', 'UFS', 'LPDDR', 'DDR', 'GDDR', 'NAND Flash'],
      'fab-micron':     ['LPDDR', 'DDR', 'GDDR', 'NAND Flash'],
      'fab-elpida':     ['LPDDR', 'DDR', 'GDDR'],
      'fab-toshiba':    ['eMMC', 'UFS', 'NAND Flash'],
      'fab-sandisk':    ['eMMC', 'UFS', 'NAND Flash'],
      'fab-nanya':      ['DDR'],
      'fab-kingston':   ['DDR'],
      'fab-rayson':     ['eMMC', 'NOR Flash'],
      'fab-issi':       ['SRAM', 'NOR Flash', 'DDR'],
      'fab-gigadevice': ['eMMC', 'NOR Flash'],
    };

    // Detecta slug da página atual (funciona em Django /fab-samsung/ e estático /fab-samsung.html)
    var slug = window.location.pathname
      .replace(/^\/|\/$/g, '')
      .replace(/\.html$/, '') || 'index';

    var produced = FAB_TYPES[slug];
    if (!produced) return; // não é página de fabricante

    var typesEl = document.querySelector('.fab-types');
    if (!typesEl) return;

    // Cria grade de badges
    var badges = document.createElement('div');
    badges.className = 'chip-badges';
    ALL_TYPES.forEach(function(t) {
      var span = document.createElement('span');
      span.className = 'chip-badge ' + (produced.indexOf(t) >= 0 ? 'on' : 'off');
      span.textContent = t;
      badges.appendChild(span);
    });

    // Insere os badges antes do fab-types e esconde o fab-types
    typesEl.parentNode.insertBefore(badges, typesEl);
    typesEl.style.display = 'none';
  })();

  // ── CHIP TYPE BLOCK — toggle via event delegation ────────
  document.addEventListener('click', function (e) {
    var trigger = e.target.closest('.chip-block-header, .chip-block-expand');
    if (!trigger) return;
    var block = trigger.closest('.chip-block');
    if (!block) return;
    var lbl  = block.querySelector('.chip-block-expand-label');
    var open = block.classList.contains('is-open');
    block.classList.toggle('is-open', !open);
    if (lbl) lbl.textContent = open ? 'EXPANDIR' : 'RECOLHER';
  });
