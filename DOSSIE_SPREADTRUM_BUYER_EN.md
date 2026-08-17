# Spreadtrum / UNISOC SoC Lot — Technical Dossier

**Prepared for the buyer · 17 August 2026**
Seller: eMiner (Paraguay) · Prepared by WhatTheChip classification

> **Purpose of this document.** These parts are **not memory**. They are mobile-phone
> system-on-chips, and they price and move differently from LPDDR / eMMC / eMCP. This dossier
> explains exactly what is in the lot, what each part does, what we can prove, and — just as
> importantly — **what we cannot prove**. Everything below is sourced; where a claim rests on a
> single weak source, it says so.

---

## 1. What these parts are, in one paragraph

Every part in this lot is a **Spreadtrum baseband + application processor SoC** — the single chip
that runs Android *and* talks to the cellular network. In the Chinese repair trade these are the
parts a counter would call **CPU** or **基带 (baseband)**; for this brand the two words point at the
same package, because the application processor and the baseband modem are integrated on one die.

**They contain no memory.** Every part here exposes an external **LPDDR + eMMC** interface. The RAM
and storage sat in a separate eMCP package next to the SoC on the board, and that eMCP carries a
*different* manufacturer's brand (Samsung, SK Hynix, Micron). If you are looking for memory, it is
not in this lot.

**Segment and era:** entry-level Android, **2014–2018**. These chips powered the low-cost phone
market in India, Africa, Latin America and Southeast Asia — Samsung Galaxy J series, Nokia C series,
Alcatel 1, Micromax, Wiko, ZTE Blade, Tecno / Infinix, Huawei MediaPad tablets.

---

## 2. Who made them

| | |
|---|---|
| Company | **Spreadtrum Communications** (展讯通信), Shanghai, founded April 2001 |
| Ownership | Acquired by **Tsinghua Unigroup**, completed 23 Dec 2013 |
| Merger | Absorbed **RDA Microelectronics**, completed July 2014 |
| Rebrand | Relaunched as **UNISOC** (紫光展锐) on **13 June 2018** |
| Business model | **Fabless** — designs SoCs, baseband, RF transceivers and PMICs. **Never manufactured memory.** |

**What the "SPREADTRUM" laser marking tells you — and what it doesn't.** The corporate brand changed
in June 2018, so "SPREADTRUM" top-marking points to production under the older brand. But this is
**not a reliable date stamp**: SC9832E and SC9863A are still listed as current UNISOC products, so the
same part number can exist with either marking. The lot code on the package is a better date signal
than the logo.

---

## 3. What is in the lot — part by part

Seven distinct strings were read off the packages. **Five are confirmed products. One does not
exist. One could not be confirmed.** All confirmed parts are 28 nm, 3G or LTE Cat 4 — the
lowest-cost tier of their era.

| Part number | CPU | GPU | Process | Modem | Announced | Status |
|---|---|---|---|---|---|---|
| **SC7727S** | **2×** Cortex-A7 @ 1.2 GHz | Mali-400 | 28 nm | 3G HSPA+ 21.1 Mbps | 2014 | ✅ confirmed |
| **SC7727SE** | **4×** Cortex-A7 @ 1.2 GHz | not published | 28 nm | 3G WCDMA/HSPA(+) | **Mar 2016** | ✅ confirmed (manufacturer PR) |
| **SC7731C** | 4× Cortex-A7 @ 1.2 GHz | Mali-400 | 28 nm | 3G HSPA+ 21 Mbps, dual-SIM | 2014 | ✅ confirmed |
| **SC9830I** | 4× Cortex-A7 @ 1.5 GHz | Mali-400 | 28 nm | **LTE Cat 4** 5-mode, VoLTE | **Nov 2016** | ✅ confirmed (manufacturer PR) |
| **SC9832E** | **4× Cortex-A53** @ 1.4 GHz (64-bit) | **Mali-T820 MP1** | 28 nm HPC+ | **LTE Cat 4** 5-mode, VoLTE / ViLTE / VoWiFi | **Jun 2018** | ✅ confirmed (UNISOC official) |
| ~~SC98301~~ | — | — | — | — | — | ❌ **Not a real part number** — see §5.1 |
| ~~SC7715T~~ | — | — | — | — | — | ⚠️ **Could not confirm this part exists** — see §5.2 |

### Notable per-part detail

**SC7727S vs SC7727SE — two letters, double the cores.** The `S` is **dual-core**; the `SE` is
**quad-core** and was the first Spreadtrum chip with an **integrated PMIC** in the baseband. These
are different silicon, not a cosmetic suffix, and they are not interchangeable in repair. Its
platform partners were the SR3532S RF transceiver and the SC2331S 3-in-1 connectivity chip.
*Source: Spreadtrum press release, 22 March 2016 (Samsung Galaxy J1 2016 / SM-J120H).*

**SC9830I** — quad Cortex-A7 @ 1.5 GHz, 5-mode TDD-LTE / LTE-FDD / WCDMA / HSPA(+) / GSM-GPRS with
VoLTE. Promoted by Spreadtrum for Huawei's 7" LTE tablets (MediaPad T1 / T2 7.0).
*Source: Spreadtrum press release, 21 November 2016.*

**SC9832E** — the newest and technically strongest part in the lot. The only **64-bit ARMv8** part
here (Cortex-A53), the only one with a **Midgard-generation GPU** (Mali-T820 MP1 @ 680 MHz), LPDDR2/3
+ **eMMC 5.1**, and **the only one UNISOC still lists as a current product**. Announced 20 June 2018
in New Delhi as *"the world's most integrated quad-core LTE chip platform"* — a 3-chip solution
(AP + RF **SR3595D** + PMIC **SC2721G**) claiming a 10% PCB area reduction.
*Source: unisoc.com official product page + launch coverage.*

**SC7731C** — quad Cortex-A7, WCDMA (not TD-SCDMA), dual-SIM, LPDDR/2/3 + eMMC 4.5. Very widely
deployed in entry Android: Lava, Micromax, verykool, Plum, ZTE Blade L7, Huawei MediaPad T1 7.0.

---

## 4. How to read the marking

```
┌──────────────────────────┐
│   [logo box]            ®│   line 1 — Spreadtrum logo
│   SPREADTRUM®            │   line 2 — brand name
│   SC7727SE               │   line 3 — THE PART NUMBER
│   1791031                │   line 4 — lot / date / traceability code
│   ...                    │   line 5 — additional factory code
└──────────────────────────┘
```

**Line 3 is the only line that identifies the part.** Lines 4–5 are factory lot codes and are not
decodable without the manufacturer's internal tables — they should never be quoted as a part number.

⚠️ On recovered parts this marking is often at the edge of legibility: dark package, low-contrast
laser. That is the direct cause of the character-confusion problem in §5.1.

---

## 5. Two corrections we are making proactively

We would rather flag these ourselves than have you find them.

### 5.1 `SC98301` does not exist — the real part is `SC9830I`

The character after `9830` is the **letter I**, not the **digit 1**. Spreadtrum's own press release
of 21 November 2016 writes it `SC9830i`. This is a well-known confusion in this family, and it runs
three ways:

- `SC9830I` — correct, per the manufacturer
- `SC98301` — broker-catalogue spelling. DigiPart carries **both** pages, they list each other as
  "similar part", and **the same suppliers appear on both with near-identical quantities** — it is
  one stock catalogued under two spellings
- `SC9830l` (lowercase L) — how GSMArena records the chipset of the Huawei MediaPad T2 7.0

The same noise produces other phantom part numbers in this family: `SC9830TW`, `SC9863A1`. Sellers of
recovered chips sometimes list every reading in the title — e.g. *"5C9832E SC9B32E SC983ZE SC9832E
BGA IC Chip"* (S↔5, 8↔B, 2↔Z).

> ⚠️ Note the trap in the other direction: **`SC9853I` and `SC9820A` are legitimate part numbers**, so
> "I means 1" is not a rule that can be applied blindly either. Only a whitelist of known parts is safe.

### 5.2 `SC7715T` could not be confirmed as a real part

A targeted search returns only the base `SC7715`. It appears in no specification database, no broker
listing, and no BGA reballing stencil — **unlike `SC7715A`, which appears in all three.** Two
possibilities, neither verified: it is an `SC7715A` with a worn `A` misread as `T`, or the `T` is a
lot marking that bled into the part-number line.

**We are re-photographing these units under raking light before including them in any offer.** They
are excluded from the counts until confirmed.

---

## 6. What we can prove, and what we cannot

Being explicit about this is deliberate — it lets you price risk instead of guessing at it.

### ✅ Confirmed against manufacturer sources
- Part identity, core count, clock, GPU, process node, modem generation for the five confirmed parts
- Manufacturer identity, corporate history, rebrand date
- That none of these parts contain memory
- That real repair demand exists for this family: dedicated BGA reballing stencils are sold for it
  (Amaoe SU3 and U-SCU2 cover SC9832E, SC9863A, SC7731C, SC7715A, SC7727S)

### ❌ Not available from any public source — for **any** part in this family
- **Package dimensions, ball count, ball pitch, mechanical drawings.** Spreadtrum never published open
  datasheets for these parts; alldatasheet returns "No Data" for the entire SC9830 series. Figures
  circulating in broker catalogues ("869 pins", "454 pins", "BGAQFN") are auto-generated catalogue
  fields, copied between unrelated part numbers, and we will not quote them. **If you need package
  data, we will measure physical samples and send you the measurements and photographs.**
- **LTE band lists per SoC.** Bands are determined by the companion RF transceiver and by handset
  certification, not by the SoC. Only "5-mode / full-band" is published.
- **PoP vs discrete memory.** No source documents package-on-package for any part in this family. The
  one board we could verify (Samsung SM-J100H, an SC7727S phone) used a **discrete** eMCP placed
  separately on the PCB.

---

## 7. Condition, and what we still need to agree

These are **pulled parts** (拆机) — desoldered from boards. That has consequences we should settle
explicitly rather than leave to assumption.

**Reballing is required, not optional.** Once desoldered, residual solder is uneven and oxidised; a
pulled BGA cannot be soldered to a new board without reballing to restore planarity. The relevant
risk factors are ball coplanarity, moisture-induced popcorning, cumulative reflow stress (industry
practice caps reflow cycles at ~3), and pad damage.

**Open points — we would like your position on each:**

1. **Do you want them reballed (植球) or as-pulled?** This changes cost, lead time and who carries the
   yield risk.
2. **What grading scheme do you use?** We are prepared to sort to A/B/C, but we want your definition,
   not ours.
3. **What testing do you require, and does it change your price?** Meaningful functional testing of an
   SoC requires mounting on a donor board and booting it — there is no trivial bench test. If you
   require tested units, we need to agree on method and on who bears the cost of failures.
4. **Priced per piece, per part number, or as one closed lot?** Our parts are already segregated by
   part number, which we understand is a value factor.
5. **Which part numbers do you actually want?** We suspect the LTE parts (SC9830I, SC9832E) and the
   3G parts (SC7727S/SE, SC7731C) are different propositions for you, and the SC9832E — 64-bit, 2018,
   still a current UNISOC product — may be the strongest single item.
6. **Do you also buy the companion chips?** Boards of this generation also carry Spreadtrum
   **SR3xxx RF transceivers** and **SC27xx PMICs**. If those are of interest, tell us and we will
   inventory them separately.

**Quantities:** we hold several hundred units across these part numbers. **A per-part-number count is
being completed and will follow this document** — we would rather send you an accurate count than a
fast one.

---

## 8. Import classification — flagging it early

We are raising this ourselves so it does not surprise either side. This is factual background, **not
legal advice**; both parties should confirm with their own customs broker.

- China has banned **all solid-waste imports since 1 January 2021**, and e-waste was already
  prohibited before that under the "seventh category" (废七类). Scrap boards do not enter legally.
- **Used electromechanical products (旧机电产品) are a separate regime**, and the definition explicitly
  includes *"parts and components"*. It has three tiers — prohibited, restricted (import licence), and
  automatic licence — and may require pre-shipment inspection.
- **The dividing line is classification, and it is not the exporter's choice to make.** Loose
  recovered ICs destined for reuse fall under a different heading than scrap.
- Since **1 January 2025**, Basel Convention amendments subject **all** transboundary movements of
  e-waste — including non-hazardous — to the **prior informed consent (PIC)** procedure; entry B1110,
  which previously allowed uncontrolled movement, was deleted.

**We would like to align on the intended customs classification and required documentation before
shipping anything.** If you have a preferred broker or an established procedure for pulled ICs, we
will work to it.

---

## 9. Summary

| | |
|---|---|
| **What this is** | Entry-level Android SoCs (application processor + integrated baseband), Spreadtrum brand, 2014–2018, 28 nm |
| **What it is not** | Memory. No DRAM, no NAND, no eMMC, no eMCP in this lot |
| **Confirmed part numbers** | SC7727S · SC7727SE · SC7731C · SC9830I · SC9832E |
| **Corrections we made** | `SC98301` → `SC9830I` (not a real PN) · `SC7715T` withheld pending re-verification |
| **Strongest single item** | **SC9832E** — 64-bit Cortex-A53, Mali-T820, LTE Cat 4, 2018, still a current UNISOC product |
| **Condition** | Pulled (拆机), sorted by part number. Reballing status, grading and testing to be agreed |
| **Open** | Per-PN counts (in progress) · grading definition · test requirement · customs classification |

---

*Prepared from manufacturer press releases (Spreadtrum / UNISOC via PR Newswire and GlobeNewswire),
unisoc.com product pages, Linux kernel device-tree bindings authored by UNISOC engineers, TechInsights
die analysis, and Chinese technical press (C114, icsmart, EET-China, 16rd). Broker-catalogue data was
deliberately excluded as unreliable. Where a figure could not be confirmed against two independent
sources, this document says so rather than filling the gap.*
