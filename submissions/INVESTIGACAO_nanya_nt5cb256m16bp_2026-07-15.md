# Investigação — Nanya `NT5CB256M16BP` (debug ao vivo do estoque) + gap 256M16/4Gb, 2026-07-15

> ✅ **Resultado: 3 known_parts submetidos, todos `confirmed`.** Densidade 4Gb (via `256M×16`) já
> estava mapeada no dossiê da rodada `NT5CB` anterior mas sem nenhum known_part real — coberto agora.
> ⚠️ **PN exato da bancada (`NT5CB256M16BP`, sem sufixo) provavelmente NÃO resolve** com o known_part
> submetido — mesma ressalva de sufixo já documentada na rodada `NT6CL`. Ver §2.

## 0. O gatilho

Debug do estoque, PN `NT5CB256M16BP`: 100% em branco (`known:false`), com `fuzzy_suggestions`:
`NT5CB256M16DP`, `NT5CB256M16`, `NT5CC256M16EP`. `NT5CB` continua sem `ChipFamily` (backlog já
sinalizado na rodada 2, decisão pendente do dono — não recriei sozinho, ver §4).

## 1. `NT5CB256M16BP` — organização já mapeada, densidade 4Gb

Aritmética: 256M × 16bit = 4096Mbit = **4Gb** — mesma densidade do bucket `NT5CB2*` (220 resultados)
já identificado no dossiê `INVESTIGACAO_nanya_nt5cb64m16fp_2026-07-15.md` §2, mas que **não tinha
nenhum known_part submetido ainda** (a rodada 2 só cobriu 64M16/1Gb e 512M8/4Gb).

## 2. ⚠️ PN exato sem sufixo — não achei fonte pra forma base

Diferente do caso `NT5CB64M16FP` (rodada 2), onde a forma BASE (sem sufixo) era uma entrada própria no
Alldatasheet, aqui **não achei `NT5CB256M16BP` (sem sufixo) indexado em nenhuma fonte aberta
diretamente**. O índice do próprio Alldatasheet pro bucket `256M16` só tem die letters C/D/E (34+40+59
= 133, bate exato) — **sem bucket "B"**. Achei a die letter "B" em fontes de distribuidor (Octopart,
Win Source) só com sufixo: `NT5CB256M16BP-DI` / `-CG`. Abri a página do Octopart diretamente (não
resumo de busca) — ficha estruturada real: "DDR3 Dram, 256MX16, 0.225NS, Cmos, PBGA96", 1.5V nominal
(confirma DDR3, não DDR3L), TFBGA96, Taiwan, datasheet IHS de 135 páginas.

Submeti `NT5CB256M16BP-DI` (com sufixo) — mas **`normalize_pn` remove só `-`, não as letras do
sufixo**: `NT5CB256M16BP` (PN da bancada) normaliza diferente de `NT5CB256M16BPDI`. Testei em sandbox
(§3, passo 7): mesmo depois de aprovar, `classify("NT5CB256M16BP")` continua sem match exato. **Resolve
o chip físico SE a marcação tiver o "-DI" (ou similar) legível** — mesma ressalva já documentada na
rodada `NT6CL` pro `NT6CL512M4GN-CG`.

## 3. known_parts submetidos (3) + validação em sandbox

| PN | Densidade | Rentabilidade (sandbox, pós-aprovação) | Fonte |
|---|---|---|---|
| NT5CB256M16BP-DI | 4Gb | RENTÁVEL | Octopart (ficha dedicada) |
| NT5CB256M16CN-DIA | 4Gb | RENTÁVEL | Alldatasheet |
| NT5CB256M16CP | 4Gb | RENTÁVEL | Alldatasheet |
| NT5CB256M16BP-CG | 4Gb | RENTÁVEL | Octopart (ficha dedicada, addendum §3b) |

1. `classify("NT5CB256M16BP")` ANTES → `known_exact=None, chip_type=None` — reproduz o debug em
   branco (confirma: `NT5CB` sem família = zero reconhecimento).
2. `submit_known_parts` dry-run + `--commit` → 3 gravados como `submitted`.
3. Aprovação simulada + `classify()` → os 3 saem `known_exact=True`, `chip_type=DDR3`,
   `dram_density='4Gb por die [✓]'`, `profitable=RENTÁVEL`.
4. `classify("NT5CB256M16BP")` DE NOVO (PN exato, sem sufixo) → **continua `known_exact=None`** —
   confirma a ressalva do §2 na prática.

## 3b. Addendum (18:06) — novo debug `NT5CB256M16BPDG`, "-DG" não encontrado

Chegou outro debug ao vivo pro MESMO die "B" (`NT5CB256M16BPDG`, 4 min depois do anterior). Os
`fuzzy_suggestions` do próprio engine já apontaram `NT5CB256M16BP-DI` (o que acabei de submeter) como
candidato mais próximo. **Busquei "-DG" especificamente (2 formulações de query) e não achei nenhuma
fonte** — nem Alldatasheet (índice completo do die "B" continua "No Data"), nem distribuidoras. O que
apareceu de forma repetida e consistente (5+ distribuidoras) foi uma TERCEIRA variante real do mesmo
die "B": **`NT5CB256M16BP-CG`** — abri a página do Octopart diretamente (não resumo): "DDR3 Dram,
256MX16, 0.255NS, Cmos, PBGA96", 1.5V, nota do distribuidor "DDR3-1333 256Mx16 (4Gb)". Adicionei ao
mesmo arquivo de submissão (4º known_part).

**Não afirmo que "-DG" é erro de leitura de "-CG" ou "-DI"** — isso seria eu adivinhando o que não
posso confirmar à distância. Só relato o que encontrei: dois sufixos reais (`-DI`, `-CG`) da die "B",
zero evidência de `-DG`. Validado em sandbox: `classify("NT5CB256M16BPDG")` (a string exata do 2º
debug) continua sem match mesmo após aprovar os 4 known_parts — nenhum deles resolve esse PN
específico, só fortalecem a cobertura da die "B" ao redor dele.

**✅ Confirmado pelo dono (mesmo dia): é "-CG" mesmo, não "-DG"** — leitura inicial do operador
corrigida. `NT5CB256M16BP-CG` deixa de ser "vizinho próximo sem certeza" e passa a ser o PN exato do
2º debug, resolvido. Nota do known_part atualizada no arquivo de submissão. A disciplina de não
inventar o "-DG" (mesmo com dois vizinhos muito próximos já confirmados) foi o que permitiu identificar
o "-CG" certo em vez de errar pro lado mais óbvio ("-DI", que era o primeiro fuzzy_suggestion).

## 4. Backlog (repetido da rodada 2, ainda pendente)

- **`ChipFamily` type-only pra `NT5CB`**: resolveria o "100% invisível" pra QUALQUER PN `NT5CB` futuro
  sem known_part (mesmo benefício que a família `NT5TU` deu de graça pro DDR2). Continuo sinalizando,
  não decidindo sozinho — é a mesma decisão que já estava pendente, não a reabri por conta própria.
- Se o dono confirmar que a marcação física do chip do debug NÃO tem "-DI"/"-CG" visível, sinalizar de
  volta — aí considero um known_part pra forma sem sufixo (sem inventar sem fonte própria).

## 5. Comandos para o dono

```bash
python manage.py shell < precheck_nt5cb256.py
python manage.py submit_known_parts submissions/nanya_nt5cb_256m16_2026-07-15.yaml
python manage.py submit_known_parts submissions/nanya_nt5cb_256m16_2026-07-15.yaml --commit
# aprovar em /admin/chips/knownpart/
python manage.py guard_catalog
```

`precheck_nt5cb256.py`:
```bash
cat > precheck_nt5cb256.py << 'EOF'
from chips.models import KnownPart
from chips.normalize import normalize_pn
candidates = ["NT5CB256M16BP-DI", "NT5CB256M16CN-DIA", "NT5CB256M16CP", "NT5CB256M16BP-CG"]
norms = {normalize_pn(c): c for c in candidates}
existing = KnownPart.objects.filter(part_number_norm__in=list(norms.keys())).values_list(
    'part_number_norm', 'part_number', 'review_status', 'confidence')
if not existing:
    print("Nenhuma colisao - os 3 PNs sao genuinamente novos no banco.")
for norm, raw, status, conf in existing:
    print(f"{norms[norm]!r} colide com {raw!r} (status={status}, confidence={conf})")
EOF
python manage.py shell < precheck_nt5cb256.py
```

## 6. Fontes

- https://octopart.com/nt5cb256m16bp-di-nanya-25738479 (ficha estruturada, aberta diretamente)
- https://www.alldatasheet.com/datasheet-pdf/pdf/1145570/NANYA/NT5CB256M16CN-DIA.html
- https://www.alldatasheet.com/datasheet-pdf/pdf/1145482/NANYA/NT5CB256M16CP.html
- https://www.alldatasheet.com/view.jsp?Searchword=NT5CB256M16&sField=2 (133 resultados, sem die "B")
