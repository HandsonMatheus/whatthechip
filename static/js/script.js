
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

      // Close search dropdown on outside click
      document.addEventListener("click", (e) => {
        const wrap = document.getElementById("top-search-input")?.closest(".top-search");
        if (wrap && !wrap.contains(e.target))
          document.getElementById("top-search-results").style.display = "none";
      });

      // Ctrl+K / Escape
      document.addEventListener("keydown", (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
          e.preventDefault();
          document.getElementById("top-search-input")?.focus();
        }
        if (e.key === "Escape")
          document.getElementById("top-search-results").style.display = "none";
      });

      // Search button
      document
        .getElementById("top-search-btn")
        ?.addEventListener("click", () => {
          document
            .getElementById("top-search-input")
            ?.dispatchEvent(new Event("input"));
        });

      // ── Prefix search ──
      const prefixData = [
        { prefix: "KLM...", fab: "Samsung", type: "eMMC" },
        { prefix: "KMQ...", fab: "Samsung", type: "eMCP LPDDR3" },
        { prefix: "KMR...", fab: "Samsung", type: "eMCP LPDDR4" },
        { prefix: "KMV...", fab: "Samsung", type: "eMCP LPDDR4X" },
        { prefix: "KMDH...", fab: "Samsung", type: "uMCP (UFS + LPDDR5)" },
        { prefix: "KMDJ...", fab: "Samsung", type: "uMCP (UFS + LPDDR5)" },
        { prefix: "KLUC...", fab: "Samsung", type: "UFS 2.0" },
        { prefix: "KLUE...", fab: "Samsung", type: "UFS 2.1" },
        { prefix: "KLUF...", fab: "Samsung", type: "UFS 3.0" },
        { prefix: "KLUGG...", fab: "Samsung", type: "UFS 3.1" },
        { prefix: "KLUJ...", fab: "Samsung", type: "UFS 4.0" },
        { prefix: "K3L...", fab: "Samsung", type: "LPDDR5" },
        { prefix: "K3P...", fab: "Samsung", type: "LPDDR5X" },
        { prefix: "K4E...", fab: "Samsung", type: "LPDDR4" },
        { prefix: "K4F...", fab: "Samsung", type: "LPDDR4X" },
        { prefix: "K3QF...", fab: "Samsung", type: "LPDDR3" },
        { prefix: "K3PH...", fab: "Samsung", type: "LPDDR3" },
        { prefix: "K4A...", fab: "Samsung", type: "DDR4 / DDR5" },
        { prefix: "K4AAG...", fab: "Samsung", type: "DDR5" },
        { prefix: "K4B...", fab: "Samsung", type: "DDR3 / DDR3L" },
        { prefix: "K4T...", fab: "Samsung", type: "DDR2" },
        { prefix: "K4H...", fab: "Samsung", type: "DDR1" },
        { prefix: "K4S...", fab: "Samsung", type: "SDRAM (PC-100/133)" },
        { prefix: "K4G...", fab: "Samsung", type: "GDDR5 (GPU vRAM)" },
        { prefix: "K4ZAF...", fab: "Samsung", type: "DDR5 / GDDR6" },
        { prefix: "K9F...", fab: "Samsung", type: "NAND bruto (SLC/MLC/TLC)" },
        { prefix: "K9G...", fab: "Samsung", type: "NAND bruto" },
        { prefix: "K9LCG...", fab: "Samsung", type: "NAND bruto" },
        { prefix: "K5L...", fab: "Samsung", type: "NOR / OneNAND" },
        { prefix: "K5Q...", fab: "Samsung", type: "NOR / OneNAND" },
        { prefix: "K5F...", fab: "Samsung", type: "NOR / OneNAND" },
        {
          prefix: "KAT...",
          fab: "Samsung",
          type: "Aplicação especial / automotivo",
        },
        { prefix: "K4R...", fab: "Samsung", type: "DDR4 server / especial" },
        { prefix: "H26M...", fab: "SK Hynix", type: "eMMC" },
        { prefix: "H9TQ...", fab: "SK Hynix", type: "eMCP" },
        { prefix: "H9HP...", fab: "SK Hynix", type: "eMCP" },
        { prefix: "H9HQ-U...", fab: "SK Hynix", type: "uMCP" },
        { prefix: "H28U...", fab: "SK Hynix", type: "UFS 2.x" },
        { prefix: "H28Y...", fab: "SK Hynix", type: "UFS 3.1+" },
        { prefix: "H54G...", fab: "SK Hynix", type: "LPDDR5X" },
        { prefix: "H9HQ...", fab: "SK Hynix", type: "LPDDR5" },
        { prefix: "H9HB...", fab: "SK Hynix", type: "LPDDR5" },
        { prefix: "H9HC...", fab: "SK Hynix", type: "LPDDR4" },
        { prefix: "H58G...", fab: "SK Hynix", type: "LPDDR4X" },
        { prefix: "HMA...", fab: "SK Hynix", type: "DDR4 (módulo)" },
        { prefix: "H5AN...", fab: "SK Hynix", type: "DDR4 (die)" },
        { prefix: "HMCG...", fab: "SK Hynix", type: "DDR5" },
        { prefix: "HMT...", fab: "SK Hynix", type: "DDR3 / DDR3L (módulo)" },
        { prefix: "H5TQ...", fab: "SK Hynix", type: "DDR3 (die)" },
        { prefix: "H5PS...", fab: "SK Hynix", type: "DDR2" },
        { prefix: "H5DS...", fab: "SK Hynix", type: "DDR2" },
        { prefix: "HY5D...", fab: "Hynix (era Hyundai)", type: "DDR1" },
        {
          prefix: "HY57...",
          fab: "Hyundai / Hynix",
          type: "SDRAM (PC-100/133)",
        },
        { prefix: "MTFC...", fab: "Micron", type: "eMMC" },
        { prefix: "MT52L...", fab: "Micron", type: "LPDDR3" },
        { prefix: "MT53E...", fab: "Micron", type: "LPDDR4" },
        { prefix: "MT53D...", fab: "Micron", type: "LPDDR4X" },
        { prefix: "MT62F...", fab: "Micron", type: "LPDDR5" },
        { prefix: "MT8ATF...", fab: "Micron", type: "DDR4" },
        { prefix: "MT16ATF...", fab: "Micron", type: "DDR4" },
        { prefix: "MT40A...", fab: "Micron", type: "DDR4" },
        { prefix: "MT60B...", fab: "Micron", type: "DDR5" },
        { prefix: "MT41J...", fab: "Micron", type: "DDR3" },
        { prefix: "MT8JTF...", fab: "Micron", type: "DDR3 / DDR3L" },
        { prefix: "MT16KTF...", fab: "Micron", type: "DDR3 / DDR3L" },
        { prefix: "MT47H...", fab: "Micron", type: "DDR2" },
        { prefix: "MT46V...", fab: "Micron", type: "DDR1" },
        { prefix: "MT48LC...", fab: "Micron", type: "SDRAM" },
        { prefix: "MT29F...", fab: "Micron", type: "NAND bruto" },
        { prefix: "EDF...", fab: "Elpida", type: "LPDDR2 / 3" },
        { prefix: "EDJ...", fab: "Elpida", type: "LPDDR2 / 3" },
        { prefix: "EDL...", fab: "Elpida", type: "LPDDR2 / 3" },
        { prefix: "J4...", fab: "Elpida", type: "DDR3" },
        { prefix: "B4...", fab: "Elpida", type: "DDR3" },
        { prefix: "EBB...", fab: "Elpida", type: "DDR2" },
        { prefix: "EBAG...", fab: "Elpida", type: "DDR2" },
        { prefix: "EB...", fab: "Elpida", type: "DDR1" },
        { prefix: "EBE...", fab: "Elpida", type: "DDR1" },
        { prefix: "THGBM...", fab: "Toshiba / Kioxia", type: "eMMC" },
        { prefix: "THGBF...", fab: "Toshiba / Kioxia", type: "eMMC" },
        { prefix: "THGBMJG...", fab: "Toshiba / Kioxia", type: "eMMC" },
        { prefix: "TYBB", fab: "Toshiba / Kioxia", type: "eMCP LPDDR2" },
        { prefix: "TYBC", fab: "Toshiba / Kioxia", type: "eMCP LPDDR2" },
        { prefix: "TYBD", fab: "Toshiba / Kioxia", type: "eMCP LPDDR3" },
        { prefix: "TYBE", fab: "Toshiba / Kioxia", type: "eMCP LPDDR3" },
        { prefix: "TYBF", fab: "Toshiba / Kioxia", type: "eMCP LPDDR4" },
        { prefix: "TYCO", fab: "Toshiba / Kioxia", type: "eMCP LPDDR4X" },
        { prefix: "TYDO", fab: "Toshiba / Kioxia", type: "eMCP LPDDR5" },
        { prefix: "THGJF...", fab: "Toshiba / Kioxia", type: "UFS" },
        { prefix: "THGUF...", fab: "Toshiba / Kioxia", type: "UFS" },
        { prefix: "TH58...", fab: "Toshiba / Kioxia", type: "NAND" },
        { prefix: "SDIN...", fab: "SanDisk / WD", type: "eMMC" },
        { prefix: "SDMAG...", fab: "SanDisk / WD", type: "eMMC" },
        { prefix: "SD7D...", fab: "SanDisk / WD", type: "eMCP (antigo)" },
        { prefix: "SDEM...", fab: "SanDisk / WD", type: "eMCP" },
        { prefix: "SDAD...", fab: "SanDisk / WD", type: "eMCP" },
        { prefix: "SDHQB...", fab: "SanDisk / WD", type: "UFS" },
        { prefix: "NT5DS...", fab: "Nanya", type: "DDR1" },
        { prefix: "NT5TU...", fab: "Nanya", type: "DDR2" },
        { prefix: "NT5C...", fab: "Nanya", type: "DDR3 / DDR3L" },
        { prefix: "NT5CB...", fab: "Nanya", type: "DDR3 / DDR3L" },
        { prefix: "NT5CC...", fab: "Nanya", type: "DDR3 / DDR3L" },
        { prefix: "NT5AD...", fab: "Nanya", type: "DDR4" },
        { prefix: "NT5AN...", fab: "Nanya", type: "DDR4" },
        { prefix: "NT5W...", fab: "Nanya", type: "DDR5" },
        { prefix: "NT6CL...", fab: "Nanya", type: "LPDDR3" },
        { prefix: "NT6AN...", fab: "Nanya", type: "LPDDR4" },
        { prefix: "NT6AH...", fab: "Nanya", type: "LPDDR4X" },
        { prefix: "NT6AC...", fab: "Nanya", type: "LPDDR5" },
        { prefix: "KVR...", fab: "Kingston", type: "DDR (die varia por lote)" },
        { prefix: "KSM...", fab: "Kingston", type: "DDR server (die varia)" },
        { prefix: "HX...", fab: "Kingston (HyperX)", type: "DDR (die varia)" },
        { prefix: "RS1GD3...", fab: "Rayson", type: "DDR3" },
        { prefix: "RS2GD3...", fab: "Rayson", type: "DDR3" },
        { prefix: "RS1GD4...", fab: "Rayson", type: "DDR4" },
        { prefix: "RS2GD4...", fab: "Rayson", type: "DDR4" },
        { prefix: "IS43...", fab: "ISSI", type: "DDR3" },
        { prefix: "IS46...", fab: "ISSI", type: "DDR3" },
        { prefix: "IS61...", fab: "ISSI", type: "SRAM" },
        { prefix: "IS62...", fab: "ISSI", type: "SRAM" },
        { prefix: "GD25...", fab: "GigaDevice", type: "NOR Flash SPI" },
        { prefix: "GD5F...", fab: "GigaDevice", type: "SPI NAND" },
        { prefix: "GD32...", fab: "GigaDevice", type: "MCU ARM" },
      ];

      const searchInput = document.getElementById("top-search-input");
      const searchResults = document.getElementById("top-search-results");
      const searchEmpty = document.getElementById("top-search-empty");

      function normalize(s) {
        return s.toLowerCase().replace(/\./g, "");
      }

      searchInput.addEventListener("input", () => {
        const q = searchInput.value.trim();
        searchResults.querySelectorAll(".sr-item").forEach((el) => el.remove());
        searchEmpty.style.display = "none";

        if (!q) {
          searchResults.style.display = "none";
          return;
        }

        const qn = normalize(q);
        const matches = prefixData.filter(
          (d) =>
            normalize(d.prefix).startsWith(qn) ||
            normalize(d.prefix).includes(qn),
        );

        searchResults.style.display = "block";
        if (matches.length === 0) {
          searchEmpty.style.display = "block";
          return;
        }

        matches.slice(0, 12).forEach((d) => {
          const cleanPrefix = d.prefix.replace(/\.+$/, "").replace(/[^A-Za-z0-9]/g, "");
          const page = fabToPage(d.fab);
          const a = document.createElement("a");
          a.className = "sr-item";
          a.href = "/" + page + "/#highlight-" + cleanPrefix;
          a.innerHTML = `<span class="sr-prefix">${d.prefix}</span><span class="sr-fab">${d.fab}</span><span class="sr-type">${d.type}</span>`;
          a.addEventListener("click", () => {
            searchResults.style.display = "none";
          });
          searchResults.insertBefore(a, searchEmpty);
        });
      });

      searchInput.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
          searchResults.style.display = "none";
          searchInput.blur();
        }
      });


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

  // ── CHIP TYPE BLOCK — toggle colapsável ─────────────────
  function wtcToggle(id) {
    var el   = document.getElementById(id);
    var c    = el.querySelector('.chip-block-content');
    var p    = el.querySelector('.chip-block-preview');
    var btn  = el.querySelector('.btn-print');
    var open = c.style.display !== 'none';
    c.style.display = open ? 'none'  : 'block';
    p.style.display = open ? ''      : 'none';
    btn.textContent = open ? '▼ Aprender mais' : '▲ Recolher';
  }
