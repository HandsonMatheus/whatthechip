# CLAUDE OPUS 4 — SANDISK iNAND CHIP DEEP RESEARCH PROMPT
## WhatTheChip Database Expansion — Tier 1 Sources Only

> **Como usar:** cole este prompt inteiro no Claude Opus 4 com extended thinking
> ativado (maximum thinking budget). O modelo deve usar o raciocínio extendido
> para planejar a pesquisa antes de executar. Espere 5–15 minutos.
>
> **Nota:** "Claude Opus 4.8" não existe — use `claude-opus-4-6` (Claude Opus 4).
> No modo max, ative **extended thinking** com budget máximo (≥10.000 tokens de
> pensamento). Se usar a interface claude.ai, selecione Opus 4 + "Extended Thinking".

---

## ROLE & CONTEXT

You are performing exhaustive Tier 1 research for **WhatTheChip (WTC)**, a Django-based chip classification database used by electronics recycling operators in Paraguay. Operators scan part numbers laser-printed on recycled chips; WTC returns chip type, capacity, interface, and profitability classification in real time.

**Why accuracy is critical:** wrong chip_type or capacity sends chips to the wrong recycling bin. Misclassification = financial loss. You must only return specs you can verify from a reliable source — do NOT guess or infer.

**Your job:** find SanDisk iNAND embedded chip part numbers (eMMC, eMCP, UFS) with confirmed specifications that are **NOT yet in the WTC database**. Return results as a CSV.

---

## WHAT ALREADY EXISTS — EXCLUDE THESE 28 PNs

These are already confirmed in the WTC database. Do **NOT** include them in your output:

```
SDIN7DU28G       (eMMC 4.41, 8GB)
SDIN9DW416G      (eMMC 5.0, 16GB)
SDIN9DW432G      (eMMC 5.0, 32GB)
SDADB48K16G      (eMCP, 16GB NAND + LPDDR3 2GB RAM)
SD7DP28C4G       (eMMC 5.1, 4GB)
SD7DP28C8G       (eMMC 5.1, 8GB)
SD7DP24C4G       (eMMC 5.1, 4GB)
SD7DP24F4G       (eMMC 5.1, 4GB)
SDIN8DE28G       (eMMC 4.51, 8GB)
SDIN8DE28GA      (eMMC 4.51, 8GB, automotive)
SDIN8DE24GI      (eMMC 4.51, 4GB, industrial)
SDIN8DE24G       (eMMC 4.51, 4GB)
SDIN8DE216G      (eMMC 4.51, 16GB)
SDIN5C28G        (eMMC 4.41, 8GB)
SDIN5C28GL       (eMMC 4.41, 8GB, lead-free)
SDIN5C216GL      (eMMC 4.41, 16GB)
SDIN5C232GL      (eMMC 4.41, 32GB)
SDIN5C264GL      (eMMC 4.41, 64GB)
SDINADF416G      (eMMC 5.1, 16GB)
SDINADF432G      (eMMC 5.1, 32GB)
SDINADF464G      (eMMC 5.1, 64GB)
SDINADF4128G     (eMMC 5.1, 128GB)
SDINADF416GH     (eMMC 5.1, 16GB, H-suffix variant)
SDINADF432GH     (eMMC 5.1, 32GB, H-suffix variant)
SDINADF464GH     (eMMC 5.1, 64GB, H-suffix variant)
SDINADF4128GH    (eMMC 5.1, 128GB, H-suffix variant)
SD5DH24C4G       (eMMC 4.3/4.4, 4GB)
SD5DH24A4G       (eMMC 4.3/4.4, 4GB)
```

---

## SOURCE HIERARCHY (NON-NEGOTIABLE)

Every chip you report MUST have a source. The source determines the `confidence` field:

### Tier 1 → `confidence = "confirmed"`
These are authoritative. Use these whenever possible:
- **westerndigital.com** — official product pages, product briefs, datasheet PDFs (document numbers: `80-XX-XXXXX`)
- **sandisk.com** — (often redirects to westerndigital.com)
- **Mouser Electronics** (mouser.com, mouser.in) — product listing with full spec table (not just a title)
- **DigiKey** (digikey.com) — product listing with full spec table
- **Avnet** (avnet.com) — product listing with full spec table
- **Arrow Electronics** (arrow.com) — product listing with full spec table

### Tier 2 → `confidence = "distributor"`
Acceptable when Tier 1 is unavailable:
- **Octopart.com** — when the listing clearly aggregates from Tier 1 distributors with spec data
- **FindChips.com** — same condition as Octopart
- **Any B2B distributor with traceable identity** (not anonymous)

### Tier 3 → `confidence = "skip"` (include row but flag it)
These are unreliable for specs. Still include the row so we can manually investigate, but set confidence = "skip":
- Alibaba, AliExpress, eBay, Jotrin, Censtry, Win Source, Veswin, Grandado, IC-Components, OMO, Chinahao
- serviceemmc.com, martview.net, gsmforum.ro (phone repair sites — useful as LEADS but NOT as spec sources)
- Any PDF without a confirmed Western Digital document number
- Any page that looks AI-generated or replicates specs without a traceable original

**RULE:** Repair sites (serviceemmc.com etc.) are useful to discover WHICH chip families exist in which phones, but they are NOT sources for specifications. Use them only as leads to then verify via Tier 1.

---

## CHIP FAMILIES TO RESEARCH — FULL PRIORITY LIST

Research each family by searching for it on Tier 1 sources. For each family, find ALL available SKUs/PNs (different capacities, suffixes, variants). **Be exhaustive within each family.**

### PRIORITY 1 — High recycling volume, partially or fully missing from DB

**1. SDIN7DP2** (eMMC 4.51, BGA153, 11.5×13mm)
- Official SanDisk datasheet exists: document# 80-36-03494
- Try: westerndigital.com search for "SDIN7DP2", Mouser for "SDIN7DP2"
- Expected variants: -4G, -8G, -16G, -32G
- ⚠️ CONFIRMED standalone eMMC (BGA153 = zero RAM pins). Some Tier 3 sites mislabel it as "eMCP LPDDR2" — this is WRONG. Do not repeat this error.

**2. SDIN7DP4** (eMMC 4.51, higher capacity/density variant)
- Different die from SDIN7DP2 (likely X3 MLC or higher density)
- Known to appear in HTC ONE MAX
- Search: Mouser, DigiKey, westerndigital.com for "SDIN7DP4"

**3. SDIN7DU — missing capacities** (eMMC 4.41, 12×16mm)
- We have 8GB only (SDIN7DU28G). Need: 4GB, 16GB, 32GB variants
- Search: "SDIN7DU2" on Mouser, DigiKey, Avnet
- Also check: SDIN7DU4 (X3 variant if it exists)

**4. SDIN8DE1** (eMMC 4.51, smaller package variant)
- Different suffix from SDIN8DE2 (which we have)
- Known to appear in Huawei phones (Honor 4X)
- Search: "SDIN8DE1" on Mouser, DigiKey, westerndigital.com

**5. SDIN8DE4** (eMMC 4.51, 12×16mm BGA221 variant)
- Different package from SDIN8DE2 (BGA153)
- Known to appear in HTC One E8
- Search: "SDIN8DE4" on Mouser, DigiKey

**6. SDIN9DS2** (eMMC 5.0, smaller package)
- Different package from SDIN9DW4 (which we have in 16G/32G)
- Known to appear in HTC Desire 630 (HTC D630N)
- Search: "SDIN9DS2" on Mouser, DigiKey, westerndigital.com

**7. SDIN9DW4 — missing capacities** (eMMC 5.0, 12×16mm)
- We have 16GB and 32GB. Need: 4GB, 8GB, 64GB variants
- Same family as SDIN9DW416G and SDIN9DW432G already in DB
- Search: "SDIN9DW4" on Mouser, DigiKey, Octopart

---

### PRIORITY 2 — Legacy families (older eMMC, still found in recycling)

**8. SDIN5D2** (X2 MLC NAND, 11.5×13mm, eMMC 4.41)
- Smaller form factor than SDIN5C2 (which we have)
- Different package dimensions
- Search: "SDIN5D2" on Mouser, DigiKey, westerndigital.com

**9. SDIN5D1** (X3 MLC NAND, 11.5×13mm, eMMC 4.41)
- X3 (3-bit MLC) version of SDIN5D series
- Search: "SDIN5D1" on Mouser, DigiKey

**10. SDIN5C1** (X3 MLC NAND, 12×16mm, eMMC 4.41)
- X3 version of SDIN5C family (SDIN5C2 is X2, which we have)
- Search: "SDIN5C1" on Mouser, DigiKey, westerndigital.com

**11. SDIN4C2 / SDIN4C4** (legacy eMMC, pre-4.41)
- Very old generation (early Samsung Galaxy era, 2010–2012)
- Known PN lead: SDIN4C2-8G
- Search: "SDIN4C" on Mouser, DigiKey, Octopart

---

### PRIORITY 3 — UFS families (important for high-end phone recycling)

**12. SDINBDG4** (UFS 2.1, 11.5×13mm)
- Known to appear in Samsung Galaxy M20 (M205F)
- Expected capacities: 32GB, 64GB, 128GB
- Search: "SDINBDG4" on westerndigital.com, Mouser, DigiKey

**13. SDINBDD4** (UFS 2.1)
- Known to appear in Huawei Nova 2s (RNE-L21)
- Search: "SDINBDD4" on westerndigital.com, Mouser, DigiKey

**14. SDINBDA4** (UFS 2.1, high capacity)
- Known to appear in Huawei Honor 8X
- Expected: 128GB, 256GB
- Search: "SDINBDA4" on westerndigital.com, Mouser, DigiKey

**15. iNAND 8350 / iNAND 9350** (UFS 3.0/3.1)
- Newer SanDisk UFS product lines
- Search westerndigital.com for "iNAND 8350", "iNAND 9350"
- Find the actual PN prefix(es) and list all SKUs

**16. SDMAG / SDINFDK** (newer UFS or eMMC families)
- Search westerndigital.com for these prefixes
- If found, list all SKUs with specs

---

### PRIORITY 4 — eMCP families (phone chips with RAM+NAND)

**17. SDADB48K — missing capacities** (eMCP LPDDR3)
- We have SDADB48K16G (16GB NAND + LPDDR3 2GB). Need: 8GB, 32GB variants
- Search: "SDADB48K" on Mouser, DigiKey, westerndigital.com
- For each PN: confirm BOTH NAND capacity AND RAM capacity + RAM type

**18. SDADEP / SDADE series** (eMCP, likely LPDDR4)
- Newer eMCP generation after SDADB
- Search westerndigital.com, Mouser, DigiKey for "SDADE"
- For each PN: confirm chip_type = eMCP, subtype = LPDDR4 (or LPDDR4X), NAND cap, RAM cap

**19. SDADF4AP and SDADF family** (eMCP)
- Known lead: SDADF4AP-16G (appears in Huawei DRA-LX2)
- Search: "SDADF" on Mouser, DigiKey, westerndigital.com

**20. SDADL2BP and SDADL family** (eMCP)
- Known lead: SDADL2BP-32G (appears in Huawei FIG-LA1)
- Search: "SDADL" on Mouser, DigiKey, westerndigital.com

**21. Other SDAD* prefixes** (any eMCP families not listed above)
- Search westerndigital.com for full SDAD product family catalog
- List any eMCP families not covered above

---

### PRIORITY 5 — Newer SD7-prefix / iNAND-branded eMMC

**22. SD7DP26A** (eMMC variant)
- Known lead: SD7DP26A-4G
- Search Tier 1 for this family; determine eMMC version

**23. SD7DP41E** (eMMC variant, higher capacity)
- Known lead: SD7DP41E-16G
- Search Tier 1 for this family

**24. iNAND 7350 family** (eMMC 5.1, if distinct from iNAND 7232)
- Search westerndigital.com for "iNAND 7350" or "iNAND 7232"
- Find PN prefix and all SKUs

**25. iNAND Ultra LS / iNAND MC EU511** (consumer/automotive eMMC)
- Search westerndigital.com for these product line names
- Find PN prefix(es) and all SKUs

---

## REQUIRED OUTPUT FORMAT

Return a single CSV block. Use comma as delimiter. Enclose values in double quotes if they contain commas. Use empty string (nothing between commas) for N/A fields — do NOT write "N/A" or "null".

```
pn_raw,pn_normalized,chip_type,subtype,capacity,emcp_nand,emcp_ram,interface,package,confidence,source_url,source_tier,source_doc,notes
```

**Field definitions:**

| Field | Description | Example values |
|---|---|---|
| `pn_raw` | Exact PN as found on source (with hyphens/spaces) | `SDIN7DP2-4G` |
| `pn_normalized` | All non-alphanumeric stripped, uppercase | `SDIN7DP24G` |
| `chip_type` | One of: `eMMC` / `eMCP` / `UFS` | `eMMC` |
| `subtype` | For eMCP ONLY: LPDDR generation (e.g., `LPDDR3`, `LPDDR4`). For eMMC/UFS: leave empty | `LPDDR3` |
| `capacity` | For eMMC/UFS standalone: total capacity with unit (e.g., `4GB`, `16GB`). For eMCP: leave EMPTY | `8GB` |
| `emcp_nand` | For eMCP ONLY: NAND capacity (e.g., `16GB`). Otherwise: empty | `16GB` |
| `emcp_ram` | For eMCP ONLY: RAM in strict format `LPDDR{n} {x}GB` — type BEFORE number. Otherwise: empty | `LPDDR3 2GB` |
| `interface` | eMMC version (`eMMC 4.41`, `eMMC 4.51`, `eMMC 5.0`, `eMMC 5.1`) or UFS (`UFS 2.0`, `UFS 2.1`, `UFS 3.0`, `UFS 3.1`) | `eMMC 4.51` |
| `package` | Physical package if stated (e.g., `BGA153`, `BGA162`, `BGA221`, `BGA169`). Otherwise: empty | `BGA153` |
| `confidence` | `confirmed` (Tier 1) / `distributor` (Tier 2) / `skip` (Tier 3 only) | `confirmed` |
| `source_url` | Full URL — not shortened, not a search page | `https://www.mouser.com/ProductDetail/...` |
| `source_tier` | `1` / `2` / `3` matching confidence | `1` |
| `source_doc` | Western Digital document number if from official PDF (format: `80-XX-XXXXX`) | `80-36-03494` |
| `notes` | Status qualifiers, known phone associations, warnings | `NRND as of 2024` |

---

## PN NORMALIZATION RULE

To compute `pn_normalized` from `pn_raw`:
1. Remove ALL characters that are NOT A–Z or 0–9
2. Convert to uppercase

Examples:
- `SDIN7DP2-4G` → `SDIN7DP24G`
- `SDIN5C2-8GL` → `SDIN5C28GL`
- `SDINADF4-16G-H` → `SDINADF416GH`
- `SDADB4-8K-16G` → `SDADB48K16G`
- `SDIN7DU2-8G` → `SDIN7DU28G`

---

## CRITICAL WARNINGS — READ BEFORE STARTING

1. **BGA153 = standalone eMMC (zero RAM).** If a chip ships in a BGA153 package, it CANNOT be eMCP. Some Tier 3 resellers falsely label BGA153 chips as "eMCP LPDDR2" — this is a known labeling error in the recycling market. Do not replicate it.

2. **eMCP requires TWO confirmed capacity values:** NAND capacity (storage) AND RAM capacity + RAM type. If only NAND is confirmed, treat as eMMC until RAM is verified.

3. **`emcp_ram` format is STRICT:** always TYPE then CAPACITY: `"LPDDR3 2GB"`, `"LPDDR4 3GB"`, `"LPDDR4X 4GB"`. NEVER write `"2GB LPDDR3"` — this will break the WTC engine.

4. **SanDisk capacity naming uses GB in the suffix:** `-4G` = 4GB, `-8G` = 8GB, `-16G` = 16GB. This is direct GB, not Gbit. Confirm with the spec table anyway.

5. **Do not infer specs.** If a PN is listed but the source does not explicitly state capacity and interface, set `confidence = "skip"` and note what's missing in `notes`.

6. **Suffixes matter.** `SDIN8DE2-8G` and `SDIN8DE2-8GA` are different SKUs (the `A` = automotive). List them as separate rows if you find them.

7. **The WD/SanDisk iNAND naming changed over time.** Older chips use `SDIN*` prefix; newer ones use `SD*` prefix (e.g., `SD7DP`, `SD5DH`). Search both conventions.

8. **serviceemmc.com / gsmforum.ro are LEADS, not sources.** If you see a PN on a repair site, use it as a search lead to find a Tier 1 source. Do NOT cite the repair site as the source.

---

## RESEARCH STRATEGY (PLAN BEFORE YOU ACT)

Before starting any searches, use extended thinking to:
1. List all 25 families above in priority order
2. Plan exactly what search queries to run for each
3. Identify which families are most likely to have Tier 1 presence

Then execute in this order:

**Step 1 — Western Digital official site**
- Start at: https://www.westerndigital.com/solutions/embedded-flash-storage
- Look for: iNAND product family pages, datasheet/product brief PDFs
- Search for each family prefix on the WD site
- PDF datasheets contain all SKU tables — these are gold

**Step 2 — Mouser Electronics**
- Go to: https://www.mouser.com/c/?keywords=iNAND+SanDisk or search by manufacturer "SanDisk"
- Filter by: Memory > Flash > eMMC or eMCP or UFS
- For each result, click through to confirm chip_type, capacity, interface from the full spec table — NOT just the title

**Step 3 — DigiKey**
- Go to: https://www.digikey.com/ and search "SanDisk eMMC" or "iNAND"
- Repeat the same verification: click through to spec table

**Step 4 — Avnet / Arrow**
- Search for SanDisk embedded flash at avnet.com and arrow.com
- These may have SKUs not listed at Mouser/DigiKey

**Step 5 — Octopart cross-check**
- For any PN you've found in Steps 1–4, search Octopart to verify it's real
- For families where Tier 1 was unavailable, check if Octopart aggregates them

**Step 6 — Research Log**
- For each family, note: found / not found / only Tier 3 / ambiguous
- Flag any PN where you're uncertain about chip_type or specs

---

## EXAMPLE VALID CSV ROW (for reference — do NOT include this in output)

```
pn_raw,pn_normalized,chip_type,subtype,capacity,emcp_nand,emcp_ram,interface,package,confidence,source_url,source_tier,source_doc,notes
SDIN7DP2-4G,SDIN7DP24G,eMMC,,4GB,,,eMMC 4.51,BGA153,confirmed,https://www.mouser.com/ProductDetail/SanDisk/SDIN7DP2-4G,1,80-36-03494,
```

---

## EXAMPLE INVALID ROWS (do NOT do this)

```
# WRONG: emcp_ram type after capacity
...,LPDDR4,,NAND 32GB,4GB LPDDR4,...

# WRONG: citing repair site as source  
...,distributor,https://www.serviceemmc.com/chip/SDIN8DE1-8G,...

# WRONG: guessing interface
...,eMMC 5.1,,,confirmed,...  ← only if you actually confirmed 5.1 in source
```

---

## FINAL OUTPUT STRUCTURE

Return in exactly this order:

1. **`[CSV DATA]`** — the full CSV block, header row first, one chip per row
2. **`[RESEARCH LOG]`** — for each of the 25 families above:
   - Status: `FOUND N PNs` / `NOT FOUND` / `TIER 3 ONLY` / `PARTIAL`
   - Source(s) used
   - Any ambiguities
3. **`[MANUAL INVESTIGATION NEEDED]`** — list of PNs/families where you couldn't confirm with Tier 1, with your best lead for the human researcher to follow up

---

*Prompt prepared by WhatTheChip (WTC) — eMiner Paraguay — 2026-06-26*
*For import into: `chips/management/commands/fix_known_parts.py`*
*Contact: eminerparaguay@gmail.com*
