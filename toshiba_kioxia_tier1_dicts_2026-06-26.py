# -*- coding: utf-8 -*-
"""TOSHIBA / KIOXIA — TIER 1 (2026-06-26). 39 PNs novos confirmados em product briefs Kioxia.
Formato pronto para colar na lista de fix_known_parts.py (secao Toshiba/Kioxia).
ATENCAO brand_name: ver DISCREPANCIAS no sumario (.md) — o banco usa Brand 'Toshiba' para
todos os THGBM; criar Brand 'Kioxia' OU remapear para 'Toshiba' antes de rodar fix_known_parts.
"""

TOSHIBA_KIOXIA_TIER1 = [

    # ========================= UFS (chip_type='UFS') =========================
    # ── THGJFPT0E18BAIP ──────────────────────────────────────────────────────
    # Kioxia UFS UFS 3.1. 128GB Package (dims na nota).
    # Fonte Tier 1 (www.kioxia.com): UFS Product Brief Rev.3.0, tabela 'Consumer Grade': THGJFPT0E18BAIP 128GB UFS 3.1.
    {
        "pn": "THGJFPT0E18BAIP",
        "create": True,
        "create_defaults": {
            "brand_name": "Kioxia",
            "chip_type":  "UFS",
            "subtype":    "UFS Kioxia",
            "confidence": "confirmed",
        },
        "fields": {
            "interface": "UFS 3.1",
            "capacity":  "128GB",
        },
        "reason": (
            "Kioxia UFS UFS 3.1 128GB. Tier 1 (www.kioxia.com): UFS Product Brief Rev.3.0, tabela 'Consumer Grade': THGJFPT0E18BAIP 128GB UFS 3.1. URL: https://www.kioxia.com/content/dam/kioxia/shared/business/memory/mlc-nand/asset/productbrief/KIOXIA_UFS_Product_Brief.pdf."
        ),
    },

    # ── THGJFPT1E28BAIP ──────────────────────────────────────────────────────
    # Kioxia UFS UFS 3.1. 256GB Package (dims na nota).
    # Fonte Tier 1 (www.kioxia.com): UFS Product Brief Rev.3.0: THGJFPT1E28BAIP 256GB UFS 3.1.
    {
        "pn": "THGJFPT1E28BAIP",
        "create": True,
        "create_defaults": {
            "brand_name": "Kioxia",
            "chip_type":  "UFS",
            "subtype":    "UFS Kioxia",
            "confidence": "confirmed",
        },
        "fields": {
            "interface": "UFS 3.1",
            "capacity":  "256GB",
        },
        "reason": (
            "Kioxia UFS UFS 3.1 256GB. Tier 1 (www.kioxia.com): UFS Product Brief Rev.3.0: THGJFPT1E28BAIP 256GB UFS 3.1. URL: https://www.kioxia.com/content/dam/kioxia/shared/business/memory/mlc-nand/asset/productbrief/KIOXIA_UFS_Product_Brief.pdf."
        ),
    },

    # ── THGJFPT2E48BAIP ──────────────────────────────────────────────────────
    # Kioxia UFS UFS 3.1. 512GB Package (dims na nota).
    # Fonte Tier 1 (www.kioxia.com): UFS Product Brief Rev.3.0: THGJFPT2E48BAIP 512GB UFS 3.1.
    {
        "pn": "THGJFPT2E48BAIP",
        "create": True,
        "create_defaults": {
            "brand_name": "Kioxia",
            "chip_type":  "UFS",
            "subtype":    "UFS Kioxia",
            "confidence": "confirmed",
        },
        "fields": {
            "interface": "UFS 3.1",
            "capacity":  "512GB",
        },
        "reason": (
            "Kioxia UFS UFS 3.1 512GB. Tier 1 (www.kioxia.com): UFS Product Brief Rev.3.0: THGJFPT2E48BAIP 512GB UFS 3.1. URL: https://www.kioxia.com/content/dam/kioxia/shared/business/memory/mlc-nand/asset/productbrief/KIOXIA_UFS_Product_Brief.pdf."
        ),
    },

    # ── THGJFMT1E45BATV ──────────────────────────────────────────────────────
    # Kioxia UFS UFS 4.0. 256GB Package (dims na nota).
    # Fonte Tier 1 (www.kioxia.com): UFS Product Brief Rev.3.0: THGJFMT1E45BATV 256GB UFS 4.0.
    {
        "pn": "THGJFMT1E45BATV",
        "create": True,
        "create_defaults": {
            "brand_name": "Kioxia",
            "chip_type":  "UFS",
            "subtype":    "UFS Kioxia",
            "confidence": "confirmed",
        },
        "fields": {
            "interface": "UFS 4.0",
            "capacity":  "256GB",
        },
        "reason": (
            "Kioxia UFS UFS 4.0 256GB. Tier 1 (www.kioxia.com): UFS Product Brief Rev.3.0: THGJFMT1E45BATV 256GB UFS 4.0. URL: https://www.kioxia.com/content/dam/kioxia/shared/business/memory/mlc-nand/asset/productbrief/KIOXIA_UFS_Product_Brief.pdf."
        ),
    },

    # ── THGJFMT2E46BATV ──────────────────────────────────────────────────────
    # Kioxia UFS UFS 4.0. 512GB Package (dims na nota).
    # Fonte Tier 1 (www.kioxia.com): UFS Product Brief Rev.3.0: THGJFMT2E46BATV 512GB UFS 4.0.
    {
        "pn": "THGJFMT2E46BATV",
        "create": True,
        "create_defaults": {
            "brand_name": "Kioxia",
            "chip_type":  "UFS",
            "subtype":    "UFS Kioxia",
            "confidence": "confirmed",
        },
        "fields": {
            "interface": "UFS 4.0",
            "capacity":  "512GB",
        },
        "reason": (
            "Kioxia UFS UFS 4.0 512GB. Tier 1 (www.kioxia.com): UFS Product Brief Rev.3.0: THGJFMT2E46BATV 512GB UFS 4.0. URL: https://www.kioxia.com/content/dam/kioxia/shared/business/memory/mlc-nand/asset/productbrief/KIOXIA_UFS_Product_Brief.pdf."
        ),
    },

    # ── THGJFMT3E86BATZ ──────────────────────────────────────────────────────
    # Kioxia UFS UFS 4.0. 1TB Package (dims na nota).
    # Fonte Tier 1 (www.kioxia.com): UFS Product Brief Rev.3.0: THGJFMT3E86BATZ 1TB UFS 4.0.
    {
        "pn": "THGJFMT3E86BATZ",
        "create": True,
        "create_defaults": {
            "brand_name": "Kioxia",
            "chip_type":  "UFS",
            "subtype":    "UFS Kioxia",
            "confidence": "confirmed",
        },
        "fields": {
            "interface": "UFS 4.0",
            "capacity":  "1TB",
        },
        "reason": (
            "Kioxia UFS UFS 4.0 1TB. Tier 1 (www.kioxia.com): UFS Product Brief Rev.3.0: THGJFMT3E86BATZ 1TB UFS 4.0. URL: https://www.kioxia.com/content/dam/kioxia/shared/business/memory/mlc-nand/asset/productbrief/KIOXIA_UFS_Product_Brief.pdf."
        ),
    },

    # ── THGJFRT1E45BATV ──────────────────────────────────────────────────────
    # Kioxia UFS UFS 4.1. 256GB Package (dims na nota).
    # Fonte Tier 1 (www.kioxia.com): UFS Product Brief Rev.3.0: THGJFRT1E45BATV 256GB UFS 4.1.
    {
        "pn": "THGJFRT1E45BATV",
        "create": True,
        "create_defaults": {
            "brand_name": "Kioxia",
            "chip_type":  "UFS",
            "subtype":    "UFS Kioxia",
            "confidence": "confirmed",
        },
        "fields": {
            "interface": "UFS 4.1",
            "capacity":  "256GB",
        },
        "reason": (
            "Kioxia UFS UFS 4.1 256GB. Tier 1 (www.kioxia.com): UFS Product Brief Rev.3.0: THGJFRT1E45BATV 256GB UFS 4.1. URL: https://www.kioxia.com/content/dam/kioxia/shared/business/memory/mlc-nand/asset/productbrief/KIOXIA_UFS_Product_Brief.pdf."
        ),
    },

    # ── THGJFRT2E48BATV ──────────────────────────────────────────────────────
    # Kioxia UFS UFS 4.1. 512GB Package (dims na nota).
    # Fonte Tier 1 (www.kioxia.com): UFS Product Brief Rev.3.0: THGJFRT2E48BATV 512GB UFS 4.1.
    {
        "pn": "THGJFRT2E48BATV",
        "create": True,
        "create_defaults": {
            "brand_name": "Kioxia",
            "chip_type":  "UFS",
            "subtype":    "UFS Kioxia",
            "confidence": "confirmed",
        },
        "fields": {
            "interface": "UFS 4.1",
            "capacity":  "512GB",
        },
        "reason": (
            "Kioxia UFS UFS 4.1 512GB. Tier 1 (www.kioxia.com): UFS Product Brief Rev.3.0: THGJFRT2E48BATV 512GB UFS 4.1. URL: https://www.kioxia.com/content/dam/kioxia/shared/business/memory/mlc-nand/asset/productbrief/KIOXIA_UFS_Product_Brief.pdf."
        ),
    },

    # ── THGJFRT3E88BATW ──────────────────────────────────────────────────────
    # Kioxia UFS UFS 4.1. 1TB Package (dims na nota).
    # Fonte Tier 1 (www.kioxia.com): UFS Product Brief Rev.3.0: THGJFRT3E88BATW 1TB UFS 4.1.
    {
        "pn": "THGJFRT3E88BATW",
        "create": True,
        "create_defaults": {
            "brand_name": "Kioxia",
            "chip_type":  "UFS",
            "subtype":    "UFS Kioxia",
            "confidence": "confirmed",
        },
        "fields": {
            "interface": "UFS 4.1",
            "capacity":  "1TB",
        },
        "reason": (
            "Kioxia UFS UFS 4.1 1TB. Tier 1 (www.kioxia.com): UFS Product Brief Rev.3.0: THGJFRT3E88BATW 1TB UFS 4.1. URL: https://www.kioxia.com/content/dam/kioxia/shared/business/memory/mlc-nand/asset/productbrief/KIOXIA_UFS_Product_Brief.pdf."
        ),
    },

    # ── THGAF8G8T23BAIL ──────────────────────────────────────────────────────
    # Kioxia UFS UFS 2.1. 32GB Package (dims na nota).
    # Fonte Tier 1 (americas.kioxia.com): UFS Product Brief Rev.2.0: THGAF8G8T23BAIL 32GB UFS 2.1.
    {
        "pn": "THGAF8G8T23BAIL",
        "create": True,
        "create_defaults": {
            "brand_name": "Kioxia",
            "chip_type":  "UFS",
            "subtype":    "UFS Kioxia",
            "confidence": "confirmed",
        },
        "fields": {
            "interface": "UFS 2.1",
            "capacity":  "32GB",
        },
        "reason": (
            "Kioxia UFS UFS 2.1 32GB. Tier 1 (americas.kioxia.com): UFS Product Brief Rev.2.0: THGAF8G8T23BAIL 32GB UFS 2.1. URL: https://americas.kioxia.com/content/dam/kioxia/en-us/business/application/iot/asset/KIOXIA_UFS_Product_Brief.pdf."
        ),
    },

    # ── THGAF8G9T43BAIR ──────────────────────────────────────────────────────
    # Kioxia UFS UFS 2.1. 64GB Package (dims na nota).
    # Fonte Tier 1 (americas.kioxia.com): UFS Product Brief Rev.2.0: THGAF8G9T43BAIR 64GB UFS 2.1.
    {
        "pn": "THGAF8G9T43BAIR",
        "create": True,
        "create_defaults": {
            "brand_name": "Kioxia",
            "chip_type":  "UFS",
            "subtype":    "UFS Kioxia",
            "confidence": "confirmed",
        },
        "fields": {
            "interface": "UFS 2.1",
            "capacity":  "64GB",
        },
        "reason": (
            "Kioxia UFS UFS 2.1 64GB. Tier 1 (americas.kioxia.com): UFS Product Brief Rev.2.0: THGAF8G9T43BAIR 64GB UFS 2.1. URL: https://americas.kioxia.com/content/dam/kioxia/en-us/business/application/iot/asset/KIOXIA_UFS_Product_Brief.pdf."
        ),
    },

    # ── THGJFAT0T44BAIL ──────────────────────────────────────────────────────
    # Kioxia UFS UFS 3.1. 128GB Package (dims na nota).
    # Fonte Tier 1 (americas.kioxia.com): UFS Product Brief Rev.2.0: THGJFAT0T44BAIL 128GB UFS 3.1.
    {
        "pn": "THGJFAT0T44BAIL",
        "create": True,
        "create_defaults": {
            "brand_name": "Kioxia",
            "chip_type":  "UFS",
            "subtype":    "UFS Kioxia",
            "confidence": "confirmed",
        },
        "fields": {
            "interface": "UFS 3.1",
            "capacity":  "128GB",
        },
        "reason": (
            "Kioxia UFS UFS 3.1 128GB. Tier 1 (americas.kioxia.com): UFS Product Brief Rev.2.0: THGJFAT0T44BAIL 128GB UFS 3.1. URL: https://americas.kioxia.com/content/dam/kioxia/en-us/business/application/iot/asset/KIOXIA_UFS_Product_Brief.pdf."
        ),
    },

    # ── THGJFAT1T84BAIR ──────────────────────────────────────────────────────
    # Kioxia UFS UFS 3.1. 256GB Package (dims na nota).
    # Fonte Tier 1 (americas.kioxia.com): UFS Product Brief Rev.2.0: THGJFAT1T84BAIR 256GB UFS 3.1.
    {
        "pn": "THGJFAT1T84BAIR",
        "create": True,
        "create_defaults": {
            "brand_name": "Kioxia",
            "chip_type":  "UFS",
            "subtype":    "UFS Kioxia",
            "confidence": "confirmed",
        },
        "fields": {
            "interface": "UFS 3.1",
            "capacity":  "256GB",
        },
        "reason": (
            "Kioxia UFS UFS 3.1 256GB. Tier 1 (americas.kioxia.com): UFS Product Brief Rev.2.0: THGJFAT1T84BAIR 256GB UFS 3.1. URL: https://americas.kioxia.com/content/dam/kioxia/en-us/business/application/iot/asset/KIOXIA_UFS_Product_Brief.pdf."
        ),
    },

    # ── THGJFGT1E45BAIP ──────────────────────────────────────────────────────
    # Kioxia UFS UFS 3.1. 256GB Package (dims na nota).
    # Fonte Tier 1 (americas.kioxia.com): UFS Product Brief Rev.2.0: THGJFGT1E45BAIP 256GB UFS 3.1.
    {
        "pn": "THGJFGT1E45BAIP",
        "create": True,
        "create_defaults": {
            "brand_name": "Kioxia",
            "chip_type":  "UFS",
            "subtype":    "UFS Kioxia",
            "confidence": "confirmed",
        },
        "fields": {
            "interface": "UFS 3.1",
            "capacity":  "256GB",
        },
        "reason": (
            "Kioxia UFS UFS 3.1 256GB. Tier 1 (americas.kioxia.com): UFS Product Brief Rev.2.0: THGJFGT1E45BAIP 256GB UFS 3.1. URL: https://americas.kioxia.com/content/dam/kioxia/en-us/business/application/iot/asset/KIOXIA_UFS_Product_Brief.pdf."
        ),
    },

    # ── THGJFAT2T84BAIR ──────────────────────────────────────────────────────
    # Kioxia UFS UFS 3.1. 512GB Package (dims na nota).
    # Fonte Tier 1 (americas.kioxia.com): UFS Product Brief Rev.2.0: THGJFAT2T84BAIR 512GB UFS 3.1.
    {
        "pn": "THGJFAT2T84BAIR",
        "create": True,
        "create_defaults": {
            "brand_name": "Kioxia",
            "chip_type":  "UFS",
            "subtype":    "UFS Kioxia",
            "confidence": "confirmed",
        },
        "fields": {
            "interface": "UFS 3.1",
            "capacity":  "512GB",
        },
        "reason": (
            "Kioxia UFS UFS 3.1 512GB. Tier 1 (americas.kioxia.com): UFS Product Brief Rev.2.0: THGJFAT2T84BAIR 512GB UFS 3.1. URL: https://americas.kioxia.com/content/dam/kioxia/en-us/business/application/iot/asset/KIOXIA_UFS_Product_Brief.pdf."
        ),
    },

    # ── THGJFGT2T85BAIU ──────────────────────────────────────────────────────
    # Kioxia UFS UFS 3.1. 512GB Package (dims na nota).
    # Fonte Tier 1 (americas.kioxia.com): UFS Product Brief Rev.2.0: THGJFGT2T85BAIU 512GB UFS 3.1.
    {
        "pn": "THGJFGT2T85BAIU",
        "create": True,
        "create_defaults": {
            "brand_name": "Kioxia",
            "chip_type":  "UFS",
            "subtype":    "UFS Kioxia",
            "confidence": "confirmed",
        },
        "fields": {
            "interface": "UFS 3.1",
            "capacity":  "512GB",
        },
        "reason": (
            "Kioxia UFS UFS 3.1 512GB. Tier 1 (americas.kioxia.com): UFS Product Brief Rev.2.0: THGJFGT2T85BAIU 512GB UFS 3.1. URL: https://americas.kioxia.com/content/dam/kioxia/en-us/business/application/iot/asset/KIOXIA_UFS_Product_Brief.pdf."
        ),
    },

    # ── THGJFHT3TB4BAIG ──────────────────────────────────────────────────────
    # Kioxia UFS UFS 3.1. 1TB Package (dims na nota).
    # Fonte Tier 1 (americas.kioxia.com): UFS Product Brief Rev.2.0: THGJFHT3TB4BAIG 1TB UFS 3.1.
    {
        "pn": "THGJFHT3TB4BAIG",
        "create": True,
        "create_defaults": {
            "brand_name": "Kioxia",
            "chip_type":  "UFS",
            "subtype":    "UFS Kioxia",
            "confidence": "confirmed",
        },
        "fields": {
            "interface": "UFS 3.1",
            "capacity":  "1TB",
        },
        "reason": (
            "Kioxia UFS UFS 3.1 1TB. Tier 1 (americas.kioxia.com): UFS Product Brief Rev.2.0: THGJFHT3TB4BAIG 1TB UFS 3.1. URL: https://americas.kioxia.com/content/dam/kioxia/en-us/business/application/iot/asset/KIOXIA_UFS_Product_Brief.pdf."
        ),
    },

    # ── THGJFJT0E25BAIP ──────────────────────────────────────────────────────
    # Kioxia UFS UFS 4.0. 128GB Package (dims na nota).
    # Fonte Tier 1 (americas.kioxia.com): UFS Product Brief Rev.2.0: THGJFJT0E25BAIP 128GB UFS 4.0.
    {
        "pn": "THGJFJT0E25BAIP",
        "create": True,
        "create_defaults": {
            "brand_name": "Kioxia",
            "chip_type":  "UFS",
            "subtype":    "UFS Kioxia",
            "confidence": "confirmed",
        },
        "fields": {
            "interface": "UFS 4.0",
            "capacity":  "128GB",
        },
        "reason": (
            "Kioxia UFS UFS 4.0 128GB. Tier 1 (americas.kioxia.com): UFS Product Brief Rev.2.0: THGJFJT0E25BAIP 128GB UFS 4.0. URL: https://americas.kioxia.com/content/dam/kioxia/en-us/business/application/iot/asset/KIOXIA_UFS_Product_Brief.pdf."
        ),
    },

    # ── THGJFJT1E45BATP ──────────────────────────────────────────────────────
    # Kioxia UFS UFS 4.0. 256GB Package (dims na nota).
    # Fonte Tier 1 (americas.kioxia.com): UFS Product Brief Rev.2.0: THGJFJT1E45BATP 256GB UFS 4.0.
    {
        "pn": "THGJFJT1E45BATP",
        "create": True,
        "create_defaults": {
            "brand_name": "Kioxia",
            "chip_type":  "UFS",
            "subtype":    "UFS Kioxia",
            "confidence": "confirmed",
        },
        "fields": {
            "interface": "UFS 4.0",
            "capacity":  "256GB",
        },
        "reason": (
            "Kioxia UFS UFS 4.0 256GB. Tier 1 (americas.kioxia.com): UFS Product Brief Rev.2.0: THGJFJT1E45BATP 256GB UFS 4.0. URL: https://americas.kioxia.com/content/dam/kioxia/en-us/business/application/iot/asset/KIOXIA_UFS_Product_Brief.pdf."
        ),
    },

    # ── THGJFJT2T85BAT0 ──────────────────────────────────────────────────────
    # Kioxia UFS UFS 4.0. 512GB Package (dims na nota).
    # Fonte Tier 1 (americas.kioxia.com): UFS Product Brief Rev.2.0: THGJFJT2T85BAT0 512GB UFS 4.0.
    {
        "pn": "THGJFJT2T85BAT0",
        "create": True,
        "create_defaults": {
            "brand_name": "Kioxia",
            "chip_type":  "UFS",
            "subtype":    "UFS Kioxia",
            "confidence": "confirmed",
        },
        "fields": {
            "interface": "UFS 4.0",
            "capacity":  "512GB",
        },
        "reason": (
            "Kioxia UFS UFS 4.0 512GB. Tier 1 (americas.kioxia.com): UFS Product Brief Rev.2.0: THGJFJT2T85BAT0 512GB UFS 4.0. URL: https://americas.kioxia.com/content/dam/kioxia/en-us/business/application/iot/asset/KIOXIA_UFS_Product_Brief.pdf."
        ),
    },

    # ── THGAF9G7L1LBAB7 ──────────────────────────────────────────────────────
    # Kioxia UFS UFS 2.1. 16GB Package (dims na nota).
    # Fonte Tier 1 (americas.kioxia.com): Automotive Product Brief Rev.2.0: THGAF9G7L1LBAB7 16GB UFS 2.1 (Auto Grade 2).
    {
        "pn": "THGAF9G7L1LBAB7",
        "create": True,
        "create_defaults": {
            "brand_name": "Kioxia",
            "chip_type":  "UFS",
            "subtype":    "UFS Kioxia",
            "confidence": "confirmed",
        },
        "fields": {
            "interface": "UFS 2.1",
            "capacity":  "16GB",
        },
        "reason": (
            "Kioxia UFS UFS 2.1 16GB. Tier 1 (americas.kioxia.com): Automotive Product Brief Rev.2.0: THGAF9G7L1LBAB7 16GB UFS 2.1 (Auto Grade 2). URL: https://americas.kioxia.com/content/dam/kioxia/shared/business/memory/automotive/asset/productbrief/KIOXIA_Automotive_Solutions_Product_Brief.pdf."
        ),
    },

    # ── THGAFBG8T13BAB7 ──────────────────────────────────────────────────────
    # Kioxia UFS UFS 2.1. 32GB Package (dims na nota).
    # Fonte Tier 1 (americas.kioxia.com): Automotive Product Brief Rev.2.0: THGAFBG8T13BAB7 32GB UFS 2.1 (Auto Grade 2).
    {
        "pn": "THGAFBG8T13BAB7",
        "create": True,
        "create_defaults": {
            "brand_name": "Kioxia",
            "chip_type":  "UFS",
            "subtype":    "UFS Kioxia",
            "confidence": "confirmed",
        },
        "fields": {
            "interface": "UFS 2.1",
            "capacity":  "32GB",
        },
        "reason": (
            "Kioxia UFS UFS 2.1 32GB. Tier 1 (americas.kioxia.com): Automotive Product Brief Rev.2.0: THGAFBG8T13BAB7 32GB UFS 2.1 (Auto Grade 2). URL: https://americas.kioxia.com/content/dam/kioxia/shared/business/memory/automotive/asset/productbrief/KIOXIA_Automotive_Solutions_Product_Brief.pdf."
        ),
    },

    # ── THGAFEG8T13BAB7 ──────────────────────────────────────────────────────
    # Kioxia UFS UFS 2.1. 32GB Package (dims na nota).
    # Fonte Tier 1 (americas.kioxia.com): Automotive Product Brief Rev.2.0: THGAFEG8T13BAB7 32GB UFS 2.1 (Auto Grade 2).
    {
        "pn": "THGAFEG8T13BAB7",
        "create": True,
        "create_defaults": {
            "brand_name": "Kioxia",
            "chip_type":  "UFS",
            "subtype":    "UFS Kioxia",
            "confidence": "confirmed",
        },
        "fields": {
            "interface": "UFS 2.1",
            "capacity":  "32GB",
        },
        "reason": (
            "Kioxia UFS UFS 2.1 32GB. Tier 1 (americas.kioxia.com): Automotive Product Brief Rev.2.0: THGAFEG8T13BAB7 32GB UFS 2.1 (Auto Grade 2). URL: https://americas.kioxia.com/content/dam/kioxia/shared/business/memory/automotive/asset/productbrief/KIOXIA_Automotive_Solutions_Product_Brief.pdf."
        ),
    },

    # ── THGAFBG9T23BAB8 ──────────────────────────────────────────────────────
    # Kioxia UFS UFS 2.1. 64GB Package (dims na nota).
    # Fonte Tier 1 (americas.kioxia.com): Automotive Product Brief Rev.2.0: THGAFBG9T23BAB8 64GB UFS 2.1 (Auto Grade 2).
    {
        "pn": "THGAFBG9T23BAB8",
        "create": True,
        "create_defaults": {
            "brand_name": "Kioxia",
            "chip_type":  "UFS",
            "subtype":    "UFS Kioxia",
            "confidence": "confirmed",
        },
        "fields": {
            "interface": "UFS 2.1",
            "capacity":  "64GB",
        },
        "reason": (
            "Kioxia UFS UFS 2.1 64GB. Tier 1 (americas.kioxia.com): Automotive Product Brief Rev.2.0: THGAFBG9T23BAB8 64GB UFS 2.1 (Auto Grade 2). URL: https://americas.kioxia.com/content/dam/kioxia/shared/business/memory/automotive/asset/productbrief/KIOXIA_Automotive_Solutions_Product_Brief.pdf."
        ),
    },

    # ── THGAFEG9T23BAB8 ──────────────────────────────────────────────────────
    # Kioxia UFS UFS 2.1. 64GB Package (dims na nota).
    # Fonte Tier 1 (americas.kioxia.com): Automotive Product Brief Rev.2.0: THGAFEG9T23BAB8 64GB UFS 2.1 (Auto Grade 2).
    {
        "pn": "THGAFEG9T23BAB8",
        "create": True,
        "create_defaults": {
            "brand_name": "Kioxia",
            "chip_type":  "UFS",
            "subtype":    "UFS Kioxia",
            "confidence": "confirmed",
        },
        "fields": {
            "interface": "UFS 2.1",
            "capacity":  "64GB",
        },
        "reason": (
            "Kioxia UFS UFS 2.1 64GB. Tier 1 (americas.kioxia.com): Automotive Product Brief Rev.2.0: THGAFEG9T23BAB8 64GB UFS 2.1 (Auto Grade 2). URL: https://americas.kioxia.com/content/dam/kioxia/shared/business/memory/automotive/asset/productbrief/KIOXIA_Automotive_Solutions_Product_Brief.pdf."
        ),
    },

    # ── THGAFBT0T43BAB8 ──────────────────────────────────────────────────────
    # Kioxia UFS UFS 2.1. 128GB Package (dims na nota).
    # Fonte Tier 1 (americas.kioxia.com): Automotive Product Brief Rev.2.0: THGAFBT0T43BAB8 128GB UFS 2.1 (Auto Grade 2).
    {
        "pn": "THGAFBT0T43BAB8",
        "create": True,
        "create_defaults": {
            "brand_name": "Kioxia",
            "chip_type":  "UFS",
            "subtype":    "UFS Kioxia",
            "confidence": "confirmed",
        },
        "fields": {
            "interface": "UFS 2.1",
            "capacity":  "128GB",
        },
        "reason": (
            "Kioxia UFS UFS 2.1 128GB. Tier 1 (americas.kioxia.com): Automotive Product Brief Rev.2.0: THGAFBT0T43BAB8 128GB UFS 2.1 (Auto Grade 2). URL: https://americas.kioxia.com/content/dam/kioxia/shared/business/memory/automotive/asset/productbrief/KIOXIA_Automotive_Solutions_Product_Brief.pdf."
        ),
    },

    # ── THGAFET0T43BAB8 ──────────────────────────────────────────────────────
    # Kioxia UFS UFS 2.1. 128GB Package (dims na nota).
    # Fonte Tier 1 (americas.kioxia.com): Automotive Product Brief Rev.2.0: THGAFET0T43BAB8 128GB UFS 2.1 (Auto Grade 2).
    {
        "pn": "THGAFET0T43BAB8",
        "create": True,
        "create_defaults": {
            "brand_name": "Kioxia",
            "chip_type":  "UFS",
            "subtype":    "UFS Kioxia",
            "confidence": "confirmed",
        },
        "fields": {
            "interface": "UFS 2.1",
            "capacity":  "128GB",
        },
        "reason": (
            "Kioxia UFS UFS 2.1 128GB. Tier 1 (americas.kioxia.com): Automotive Product Brief Rev.2.0: THGAFET0T43BAB8 128GB UFS 2.1 (Auto Grade 2). URL: https://americas.kioxia.com/content/dam/kioxia/shared/business/memory/automotive/asset/productbrief/KIOXIA_Automotive_Solutions_Product_Brief.pdf."
        ),
    },

    # ── THGAFBT1T83BAB5 ──────────────────────────────────────────────────────
    # Kioxia UFS UFS 2.1. 256GB Package (dims na nota).
    # Fonte Tier 1 (americas.kioxia.com): Automotive Product Brief Rev.2.0: THGAFBT1T83BAB5 256GB UFS 2.1 (Auto Grade 2).
    {
        "pn": "THGAFBT1T83BAB5",
        "create": True,
        "create_defaults": {
            "brand_name": "Kioxia",
            "chip_type":  "UFS",
            "subtype":    "UFS Kioxia",
            "confidence": "confirmed",
        },
        "fields": {
            "interface": "UFS 2.1",
            "capacity":  "256GB",
        },
        "reason": (
            "Kioxia UFS UFS 2.1 256GB. Tier 1 (americas.kioxia.com): Automotive Product Brief Rev.2.0: THGAFBT1T83BAB5 256GB UFS 2.1 (Auto Grade 2). URL: https://americas.kioxia.com/content/dam/kioxia/shared/business/memory/automotive/asset/productbrief/KIOXIA_Automotive_Solutions_Product_Brief.pdf."
        ),
    },

    # ── THGAFET1T83BAB5 ──────────────────────────────────────────────────────
    # Kioxia UFS UFS 2.1. 256GB Package (dims na nota).
    # Fonte Tier 1 (americas.kioxia.com): Automotive Product Brief Rev.2.0: THGAFET1T83BAB5 256GB UFS 2.1 (Auto Grade 2).
    {
        "pn": "THGAFET1T83BAB5",
        "create": True,
        "create_defaults": {
            "brand_name": "Kioxia",
            "chip_type":  "UFS",
            "subtype":    "UFS Kioxia",
            "confidence": "confirmed",
        },
        "fields": {
            "interface": "UFS 2.1",
            "capacity":  "256GB",
        },
        "reason": (
            "Kioxia UFS UFS 2.1 256GB. Tier 1 (americas.kioxia.com): Automotive Product Brief Rev.2.0: THGAFET1T83BAB5 256GB UFS 2.1 (Auto Grade 2). URL: https://americas.kioxia.com/content/dam/kioxia/shared/business/memory/automotive/asset/productbrief/KIOXIA_Automotive_Solutions_Product_Brief.pdf."
        ),
    },

    # ======================== eMMC (chip_type='eMMC') ========================
    # ── THGAMVG7T13BAIL ──────────────────────────────────────────────────────
    # Kioxia eMMC eMMC 5.1. 16GB Package BGA-153.
    # Fonte Tier 1 (americas.kioxia.com): e-MMC Product Brief Rev.2.0, 'Consumer Grade': THGAMVG7T13BAIL 16GB eMMC 5.1 BiCS FLASH.
    {
        "pn": "THGAMVG7T13BAIL",
        "create": True,
        "create_defaults": {
            "brand_name": "Kioxia",
            "chip_type":  "eMMC",
            "subtype":    "eMMC Kioxia",
            "confidence": "confirmed",
        },
        "fields": {
            "interface": "eMMC 5.1",
            "capacity":  "16GB",
        },
        "reason": (
            "Kioxia eMMC eMMC 5.1 16GB. Tier 1 (americas.kioxia.com): e-MMC Product Brief Rev.2.0, 'Consumer Grade': THGAMVG7T13BAIL 16GB eMMC 5.1 BiCS FLASH. URL: https://americas.kioxia.com/content/dam/kioxia/en-us/business/application/iot/asset/KIOXIA_e-MMC_Product_Brief.pdf."
        ),
    },

    # ── THGAMVG8T13BAIL ──────────────────────────────────────────────────────
    # Kioxia eMMC eMMC 5.1. 32GB Package BGA-153.
    # Fonte Tier 1 (americas.kioxia.com): e-MMC Product Brief Rev.2.0: THGAMVG8T13BAIL 32GB eMMC 5.1 BiCS FLASH.
    {
        "pn": "THGAMVG8T13BAIL",
        "create": True,
        "create_defaults": {
            "brand_name": "Kioxia",
            "chip_type":  "eMMC",
            "subtype":    "eMMC Kioxia",
            "confidence": "confirmed",
        },
        "fields": {
            "interface": "eMMC 5.1",
            "capacity":  "32GB",
        },
        "reason": (
            "Kioxia eMMC eMMC 5.1 32GB. Tier 1 (americas.kioxia.com): e-MMC Product Brief Rev.2.0: THGAMVG8T13BAIL 32GB eMMC 5.1 BiCS FLASH. URL: https://americas.kioxia.com/content/dam/kioxia/en-us/business/application/iot/asset/KIOXIA_e-MMC_Product_Brief.pdf."
        ),
    },

    # ── THGAMVG9T23BAIL ──────────────────────────────────────────────────────
    # Kioxia eMMC eMMC 5.1. 64GB Package BGA-153.
    # Fonte Tier 1 (americas.kioxia.com): e-MMC Product Brief Rev.2.0: THGAMVG9T23BAIL 64GB eMMC 5.1 BiCS FLASH.
    {
        "pn": "THGAMVG9T23BAIL",
        "create": True,
        "create_defaults": {
            "brand_name": "Kioxia",
            "chip_type":  "eMMC",
            "subtype":    "eMMC Kioxia",
            "confidence": "confirmed",
        },
        "fields": {
            "interface": "eMMC 5.1",
            "capacity":  "64GB",
        },
        "reason": (
            "Kioxia eMMC eMMC 5.1 64GB. Tier 1 (americas.kioxia.com): e-MMC Product Brief Rev.2.0: THGAMVG9T23BAIL 64GB eMMC 5.1 BiCS FLASH. URL: https://americas.kioxia.com/content/dam/kioxia/en-us/business/application/iot/asset/KIOXIA_e-MMC_Product_Brief.pdf."
        ),
    },

    # ── THGAMVT0T43BAIR ──────────────────────────────────────────────────────
    # Kioxia eMMC eMMC 5.1. 128GB Package BGA-153.
    # Fonte Tier 1 (americas.kioxia.com): e-MMC Product Brief Rev.2.0: THGAMVT0T43BAIR 128GB eMMC 5.1 BiCS FLASH.
    {
        "pn": "THGAMVT0T43BAIR",
        "create": True,
        "create_defaults": {
            "brand_name": "Kioxia",
            "chip_type":  "eMMC",
            "subtype":    "eMMC Kioxia",
            "confidence": "confirmed",
        },
        "fields": {
            "interface": "eMMC 5.1",
            "capacity":  "128GB",
        },
        "reason": (
            "Kioxia eMMC eMMC 5.1 128GB. Tier 1 (americas.kioxia.com): e-MMC Product Brief Rev.2.0: THGAMVT0T43BAIR 128GB eMMC 5.1 BiCS FLASH. URL: https://americas.kioxia.com/content/dam/kioxia/en-us/business/application/iot/asset/KIOXIA_e-MMC_Product_Brief.pdf."
        ),
    },

    # ── THGAMSG9T24BAIL ──────────────────────────────────────────────────────
    # Kioxia eMMC eMMC 5.1. 64GB Package BGA-153.
    # Fonte Tier 1 (americas.kioxia.com): e-MMC Product Brief Rev.2.0: THGAMSG9T24BAIL 64GB eMMC 5.1 BiCS FLASH.
    {
        "pn": "THGAMSG9T24BAIL",
        "create": True,
        "create_defaults": {
            "brand_name": "Kioxia",
            "chip_type":  "eMMC",
            "subtype":    "eMMC Kioxia",
            "confidence": "confirmed",
        },
        "fields": {
            "interface": "eMMC 5.1",
            "capacity":  "64GB",
        },
        "reason": (
            "Kioxia eMMC eMMC 5.1 64GB. Tier 1 (americas.kioxia.com): e-MMC Product Brief Rev.2.0: THGAMSG9T24BAIL 64GB eMMC 5.1 BiCS FLASH. URL: https://americas.kioxia.com/content/dam/kioxia/en-us/business/application/iot/asset/KIOXIA_e-MMC_Product_Brief.pdf."
        ),
    },

    # ── THGAMST0T24BAIL ──────────────────────────────────────────────────────
    # Kioxia eMMC eMMC 5.1. 128GB Package BGA-153.
    # Fonte Tier 1 (americas.kioxia.com): e-MMC Product Brief Rev.2.0: THGAMST0T24BAIL 128GB eMMC 5.1 BiCS FLASH.
    {
        "pn": "THGAMST0T24BAIL",
        "create": True,
        "create_defaults": {
            "brand_name": "Kioxia",
            "chip_type":  "eMMC",
            "subtype":    "eMMC Kioxia",
            "confidence": "confirmed",
        },
        "fields": {
            "interface": "eMMC 5.1",
            "capacity":  "128GB",
        },
        "reason": (
            "Kioxia eMMC eMMC 5.1 128GB. Tier 1 (americas.kioxia.com): e-MMC Product Brief Rev.2.0: THGAMST0T24BAIL 128GB eMMC 5.1 BiCS FLASH. URL: https://americas.kioxia.com/content/dam/kioxia/en-us/business/application/iot/asset/KIOXIA_e-MMC_Product_Brief.pdf."
        ),
    },

    # ── THGBMJG6C1LBAB7 ──────────────────────────────────────────────────────
    # Kioxia eMMC eMMC 5.1. 8GB Package BGA-153.
    # Fonte Tier 1 (americas.kioxia.com): Automotive Product Brief Rev.2.0, 'Automotive e-MMC': THGBMJG6C1LBAB7 8GB eMMC 5.1.
    {
        "pn": "THGBMJG6C1LBAB7",
        "create": True,
        "create_defaults": {
            "brand_name": "Kioxia",
            "chip_type":  "eMMC",
            "subtype":    "eMMC Kioxia",
            "confidence": "confirmed",
        },
        "fields": {
            "interface": "eMMC 5.1",
            "capacity":  "8GB",
        },
        "reason": (
            "Kioxia eMMC eMMC 5.1 8GB. Tier 1 (americas.kioxia.com): Automotive Product Brief Rev.2.0, 'Automotive e-MMC': THGBMJG6C1LBAB7 8GB eMMC 5.1. URL: https://americas.kioxia.com/content/dam/kioxia/shared/business/memory/automotive/asset/productbrief/KIOXIA_Automotive_Solutions_Product_Brief.pdf."
        ),
    },

    # ── THGBMJG7C2LBAB8 ──────────────────────────────────────────────────────
    # Kioxia eMMC eMMC 5.1. 16GB Package BGA-153.
    # Fonte Tier 1 (americas.kioxia.com): Automotive Product Brief Rev.2.0: THGBMJG7C2LBAB8 16GB eMMC 5.1.
    {
        "pn": "THGBMJG7C2LBAB8",
        "create": True,
        "create_defaults": {
            "brand_name": "Kioxia",
            "chip_type":  "eMMC",
            "subtype":    "eMMC Kioxia",
            "confidence": "confirmed",
        },
        "fields": {
            "interface": "eMMC 5.1",
            "capacity":  "16GB",
        },
        "reason": (
            "Kioxia eMMC eMMC 5.1 16GB. Tier 1 (americas.kioxia.com): Automotive Product Brief Rev.2.0: THGBMJG7C2LBAB8 16GB eMMC 5.1. URL: https://americas.kioxia.com/content/dam/kioxia/shared/business/memory/automotive/asset/productbrief/KIOXIA_Automotive_Solutions_Product_Brief.pdf."
        ),
    },

    # ── THGBMJG8C4LBAB8 ──────────────────────────────────────────────────────
    # Kioxia eMMC eMMC 5.1. 32GB Package BGA-153.
    # Fonte Tier 1 (americas.kioxia.com): Automotive Product Brief Rev.2.0: THGBMJG8C4LBAB8 32GB eMMC 5.1.
    {
        "pn": "THGBMJG8C4LBAB8",
        "create": True,
        "create_defaults": {
            "brand_name": "Kioxia",
            "chip_type":  "eMMC",
            "subtype":    "eMMC Kioxia",
            "confidence": "confirmed",
        },
        "fields": {
            "interface": "eMMC 5.1",
            "capacity":  "32GB",
        },
        "reason": (
            "Kioxia eMMC eMMC 5.1 32GB. Tier 1 (americas.kioxia.com): Automotive Product Brief Rev.2.0: THGBMJG8C4LBAB8 32GB eMMC 5.1. URL: https://americas.kioxia.com/content/dam/kioxia/shared/business/memory/automotive/asset/productbrief/KIOXIA_Automotive_Solutions_Product_Brief.pdf."
        ),
    },

    # ── THGBMJG9C8LBAB8 ──────────────────────────────────────────────────────
    # Kioxia eMMC eMMC 5.1. 64GB Package BGA-153.
    # Fonte Tier 1 (americas.kioxia.com): Automotive Product Brief Rev.2.0: THGBMJG9C8LBAB8 64GB eMMC 5.1.
    {
        "pn": "THGBMJG9C8LBAB8",
        "create": True,
        "create_defaults": {
            "brand_name": "Kioxia",
            "chip_type":  "eMMC",
            "subtype":    "eMMC Kioxia",
            "confidence": "confirmed",
        },
        "fields": {
            "interface": "eMMC 5.1",
            "capacity":  "64GB",
        },
        "reason": (
            "Kioxia eMMC eMMC 5.1 64GB. Tier 1 (americas.kioxia.com): Automotive Product Brief Rev.2.0: THGBMJG9C8LBAB8 64GB eMMC 5.1. URL: https://americas.kioxia.com/content/dam/kioxia/shared/business/memory/automotive/asset/productbrief/KIOXIA_Automotive_Solutions_Product_Brief.pdf."
        ),
    },

]
