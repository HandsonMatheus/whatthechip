# Investigação — Nanya `NT5AD` (DDR4) e `NT5PA` (DDR3L notebook), 2026-07-15

> ✅ **Resultado: 6 known_parts `NT5AD` submetidos, todos `confirmed`.** Cluster inteiro (2 densidades ×
> 3 organizações) coberto. **`NT5PA`: ZERO PN encontrado após busca exaustiva — ver §3, sinalizado ao
> dono, nada submetido.** Arquivo: `nanya_nt5ad_2026-07-15.yaml`. Validado ponta-a-ponta em sandbox
> local (migrate→load_brands→submit dry-run→commit→aprovar→reclassify) — ver §4.

## 0. O gatilho

Prioridade 1 do dono após revisar o `NANYA.md`: as famílias `NT5AD` (DDR4) e `NT5PA` (DDR3L notebook)
tinham PN-âncora só no golden de teste, nenhum `known_part` real no catálogo — todo PN dessas duas
famílias cai em INDETERMINADO na prática (a gramática Nanya não decodifica capacidade).

## 1. Metodologia

Busca ampla (site-wide, não PN a PN) por cluster inteiro, depois abertura direta de cada fonte candidata
(nunca só o resumo da busca) — `nanya.com.tw`, Octopart (categorização própria), Alldatasheet (indexa o
datasheet oficial). Cruzei cada capacidade encontrada com a fórmula profundidade×largura÷8 já documentada
como hipótese no `NANYA.md` §2.

## 2. `NT5AD` (DDR4) — 6 known_parts, cluster 2×3 completo

A fórmula **profundidade(M) × largura(bits) ÷ 8 = bytes** se confirmou em TODAS as fontes abertas
diretamente (Octopart categorização própria, IHS, Verical, Rutronik, Alldatasheet/datasheet oficial) —
zero exceção em 8+ PNs distintos checados. Isso eleva a hipótese do `NANYA.md` de "não confirmada" para
"confirmada em DDR4, múltiplas fontes independentes" (o `.md` pode ser atualizado numa próxima rodada, não
mexi nele hoje).

| PN | Organização | `density_gbit` | `interface` | Fonte principal (aberta diretamente) |
|---|---|---|---|---|
| NT5AD256M16D4-HR | 256M×16 | 4Gb | x16 | Octopart (categorização própria) + Verical + Rutronik + IHS, todas na mesma página |
| NT5AD512M8D3-HRI | 512M×8 | 4Gb | x8 | Alldatasheet (indexa datasheet oficial nanya.com) |
| NT5AD1024M4D3-HRNA | 1024M×4 | 4Gb | x4 | Alldatasheet (indexa datasheet oficial nanya.com) |
| NT5AD512M16A3-GZI | 512M×16 | 8Gb | x16 | Alldatasheet |
| NT5AD1024M8C3-HR | 1024M×8 | 8Gb | x8 | Octopart (categorização própria: "1GX8") + IHS ("1Gx8 (8Gb)") |
| NT5AD2048M4A3 | 2048M×4 | 8Gb | x4 | Alldatasheet; corroborado por NT5AD2048M4C3-JR na página oficial nanya.com.tw |

Todos `confidence: confirmed` — cada um com pelo menos 1 fonte Tier-1/2 aberta diretamente, a maioria com
2+ fontes independentes concordando na mesma página. Notas completas com a aritmética no arquivo de
submissão.

**Não incluí no lote** (fora do escopo de hoje, achados de relance): as variantes E-die/H-die (`NT5AD…E3`,
`NT5AD…E4`, `NT5AD…H3`) que apareceram nas buscas mas não abri fonte direta — mesma capacidade que as
variantes já confirmadas pelo M-code (die é revisão de processo, não capacidade), mas não submeto sem
abrir a fonte. Backlog pra próxima rodada se o dono quiser mais cobertura de sufixo.

## 3. `NT5PA` — NÃO encontrado, sinalizando ao dono (não inventei nada)

Busca exaustiva (6 formulações de query: nome direto, +datasheet, +distribuidores específicos,
site:nanya.com.tw, variantes de dígito "NT5PB"/"NT5PC", nome solto) — **zero resultado real** para
`NT5PA` em qualquer fonte (nanya.com.tw, Octopart, Alldatasheet, Arrow, Verical, LCSC, brokerforum,
datasheetcatalog). Todas as buscas por "Nanya DDR3L notebook/low-voltage" retornam consistentemente
`NT5CB` (DDR3 1.5V) e `NT5CC` (DDR3L 1.35V) — nunca `NT5PA`.

Isso é diferente de "família nova sem known_part ainda" — é **nenhuma evidência de que o prefixo existe**.
Hipóteses, sem forma de decidir sozinho:
1. `NT5PA` é real mas raro/OEM (contrato específico, nunca chegou a distribuidor público) — meu acesso de
   busca não alcança.
2. Foi confundido com outra coisa ao criar a família no yaml (ex.: um PN de MÓDULO como `NT8GC64B8HB0NS-DI`
   visto na busca — mas isso é nomenclatura de módulo SODIMM, não de chip, prefixo totalmente diferente).
3. O papel "DDR3L de notebook" já está coberto por `NT5CC` (que É 1.35V e amplamente documentado em uso
   notebook) — `NT5PA` pode ter sido redundante desde o início.

**Não criei nem editei nada em `nanya.yaml`** — só pesquiso/populo a minha marca pelos dois canais
formais; decidir se a família fica, é investigada de novo com outro acesso, ou é removida é do dono.

## 4. Validação em sandbox local (ponta-a-ponta)

Rodei fora do repo rastreado (script não versionado), contra SQLite via `core.settings_test` — DB
descartável, sem tocar prod nem o Postgres local do dono:

1. `load_brands --brand nanya --commit --skip-known-parts` — OK (reproduziu o mesmo aviso já documentado
   no `NANYA.md`: as 3 famílias sem fonte de densidade).
2. `classify()` nos 6 PNs ANTES de qualquer known_part → `known_exact=False`, `profitable=INDETERMINADO`
   em todos — confirma a regra de ouro #6 do `NANYA.md` na prática.
3. `submit_known_parts` dry-run → portão aceitou os 6.
4. `submit_known_parts --commit` → gravou os 6 como `submitted` (oculto).
5. `classify()` com os 6 ainda `submitted` → continuam `known_exact=False` — confirma que o gate
   `_USABLE &= approved` está funcionando (não vaza pro engine antes da aprovação).
6. Aprovei manualmente no banco de teste (simulando o admin) → `classify()` de novo: todos
   `known_exact=True`, `dram_density` correto (`"4Gb por die [✓]"` / `"8Gb por die [✓]"`),
   **`profitable=RENTÁVEL`** nos 6.

**Observação (não é bug meu pra corrigir, é do engine — reportando):** o campo `interface` que gravei no
known_part (`x16`/`x8`/`x4`) NÃO aparece no resultado de `classify()` (veio vazio) mesmo depois de
aprovado — o merge known+família parece não repassar o `interface` do known_part quando o da família está
vazio (as 3 famílias Nanya têm `interface: ''`). O dado está salvo certo no banco (confirmei via
`KnownPart.objects.get(...)` antes de reclassificar), só não chega no output. Não mexi em `engine.py` —
sinalizando pro dono decidir se vale investigar.

## 5. Comandos para o dono

```bash
# 1) precheck read-only (pega colisão de formatação ou cobertura já approved por outro canal
#    invisível — o seed local não tem nenhum NT5AD, mas o banco de prod pode ter avançado):
python manage.py shell < precheck_nt5ad.py

# 2) submissão (dry-run = portão, depois grava):
python manage.py submit_known_parts submissions/nanya_nt5ad_2026-07-15.yaml
python manage.py submit_known_parts submissions/nanya_nt5ad_2026-07-15.yaml --commit

# 3) aprovar em /admin/chips/knownpart/ (filtro review_status → Submetido)
# 4) depois: python manage.py guard_catalog
```

`precheck_nt5ad.py` (heredoc com delimitador quoted, nunca `shell -c "..."` com `!r`):

```bash
cat > precheck_nt5ad.py << 'EOF'
from chips.models import KnownPart
from chips.normalize import normalize_pn
candidates = [
    "NT5AD256M16D4-HR", "NT5AD512M8D3-HRI", "NT5AD1024M4D3-HRNA",
    "NT5AD512M16A3-GZI", "NT5AD1024M8C3-HR", "NT5AD2048M4A3",
]
norms = {normalize_pn(c): c for c in candidates}
existing = KnownPart.objects.filter(part_number_norm__in=list(norms.keys())).values_list(
    'part_number_norm', 'part_number', 'review_status', 'confidence')
if not existing:
    print("Nenhuma colisão — os 6 PNs sao genuinamente novos no banco.")
for norm, raw, status, conf in existing:
    print(f"{norms[norm]!r} colide com {raw!r} (status={status}, confidence={conf})")
EOF
python manage.py shell < precheck_nt5ad.py
```

## 6. Fontes completas

- https://octopart.com/nt5ad256m16d4-hr-nanya-96079452 (NT5AD256M16D4-HR — categorização própria + Verical/Rutronik/IHS)
- https://www.alldatasheet.com/datasheet-pdf/pdf/1145460/NANYA/NT5AD512M8D3-HRI.html
- https://www.alldatasheet.com/datasheet-pdf/pdf/1145464/NANYA/NT5AD1024M4D3-HRNA.html
- https://www.alldatasheet.com/datasheet-pdf/pdf/1145489/NANYA/NT5AD512M16A3-GZI.html
- https://octopart.com/part/nanya/NT5AD1024M8C3-HR (categorização própria + IHS)
- https://www.alldatasheet.com/datasheet-pdf/pdf/1145456/NANYA/NT5AD2048M4A3.html
- https://www.nanya.com/tw/Product/4467/NT5AD2048M4C3-JR (página oficial, PN irmão do NT5AD2048M4A3)
- https://www.nanya.com/tw/Product/4596/NT5AD256M16E4-JR (página oficial, cluster NT5AD)

Arquivos internos consultados: `chips/knowledge/nanya.yaml`, `NANYA.md`, `chips/tests.py`
(`_NANYA_GOLDEN`), `chips/knowledge/schema.py` (`KnownPartSpec`).
