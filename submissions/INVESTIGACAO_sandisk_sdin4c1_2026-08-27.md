# Investigação — SanDisk `SDIN4C18G`, override do dono com specs do irmão `SDIN4C2` (2026-08-27)

> ✅ **Resultado: 1 known_part, `confidence=manual`, specs herdadas do irmão confirmado
> `SDIN4C28G`.** Autorizado pelo dono em chat, sem fonte pública própria para o die-code "4C1".
> Arquivo: `sandisk_sdin4c1_2026-08-27.yaml`.

## 0. Linha do tempo

- **26/08/2026, 17:39:02** — 1ª ocorrência do PN no debug do estoque. Busca exaustiva (Octopart,
  veswin, eBay, alldatasheet) não achou nenhuma fonte real para "SDIN4C1". Único sinal indireto: um
  anúncio eBay de `SDIN4C2-8G` listando tags OCR alternativas "SD1N4C2-86"/"5DIN4C2-BG" — hipótese
  registrada: "4C1" seria leitura errada de bancada de `SDIN4C2` (dígito 1↔2) ou `SDIN5C1` (dígito
  4↔5, confirmado no mesmo dia via datasheet oficial). Não submetido — flagado no tip da família
  SDIN (chips/knowledge/sandisk.yaml).
- **27/08/2026, 13:49:42** — PN reaparece no debug (mesmo texto, novo horário). Resposta inicial
  reafirmou a hipótese de misread com base no tip já registrado.
- **27/08/2026 (chat)** — dono informa estar com o chip físico em mãos e descreve o encapsulamento:
  retangular, maior que eMCP "como NAND flash", anel de bolinhas douradas + grade de bolinhas
  prateadas com quadrado oco no centro. Descrição não bateu com o perfil BGA eMMC típico —
  reavaliado como possível NAND raw/ASIC não catalogado, recomendado não adivinhar e pedir foto.
- **27/08/2026 (chat, com foto)** — dono envia foto de referência do `SDIN4C2-8G-U` (SanDisk,
  TAIWAN, 169FBGA, EMMC, 8GB) com verso mostrando exatamente o padrão anel-dourado +
  grade-prateada-com-quadrado-oco descrito. Confirma que o ESTILO de encapsulamento é eMMC legítimo
  da família 4Cx — retirada a suspeita de ASIC/NAND-raw. Contra-busca dedicada testando a hipótese
  "4C1 é irmão X3(TLC) do 4C2 X2(MLC), mesmo padrão do cluster 5D1/5D2/5C1/5C2 confirmado dois dias
  antes" — zero resultado real (ver §1). Dono confirma marcação "SDIN4C18G" exata no chip (não é
  OCR) e autoriza: **"pode confirmar com as mesmas specs então"** — registrar com as specs do irmão
  SDIN4C28G.

## 1. Busca dedicada (27/08) — hipótese do irmão X3/TLC

Testado explicitamente: `"SDIN4C1-8G" SanDisk eMMC` e `"SDIN4C1" SanDisk iNAND 169FBGA`. Nenhuma
fonte real. Um resumo de busca chegou a mencionar "SDIN4C1-4G e SDIN4C1-8G" no texto gerado, mas os
links de origem citados eram todos `SDIN5C1-4G` (Jotrin), `SDIN5C2-4G` (elcodis), `SDIN2B2-4G`
(datasheetz) — nenhum realmente sobre "4C1". Tratado como confusão da ferramenta de busca (dígito
4↔5), descartado como evidência.

## 2. Base da decisão — comparação por foto, não por fonte pública

Sem datasheet/distribuidor confirmando "SDIN4C1" como die-code próprio. A decisão do dono se apoia
em:

- Marcação física conferida por ele mesmo (não é leitura de bancada/OCR — descartada a hipótese de
  erro de leitura que motivou a investigação original).
- Encapsulamento (169FBGA, anel dourado + grade prateada + quadrado oco central) batendo com a foto
  de referência do irmão `SDIN4C2-8G-U`, mesma geração "4Cx", mesma capacidade 8GB.
- Precedente já aceito no catálogo para este tipo de situação (marcação física confirmada +
  encapsulamento idêntico a um irmão já confirmado, sem fonte pública própria): `SD5DH26A4G` e
  `SDIN4E2-32G`, ambos `confidence=manual` por decisão direta do dono.

**Discrepância não resolvida:** contagem manual de bolinhas do dono no chip físico (~346, em anéis
concêntricos: 88 douradas grandes + 10 douradas pequenas + 16 prateadas em arco + 36 prateadas no
quadrado interno + ~196 prateadas no quadrado externo) não bate com as 169 do irmão confirmado.
Mais provável: erro de contagem a olho nu (169 bolinhas pequenas sem lupa é fácil de contar em
dobro numa grade concêntrica) — mas fica registrado, não escondido, caso alguém queira reconferir
fisicamente depois.

## 3. known_part submetido (1)

| PN | Capacidade | Confidence | Base |
|---|---|---|---|
| SDIN4C18G | 8GB | manual | Specs herdadas do irmão SDIN4C28G (confirmado 07-14), autorizado pelo dono 27/08 |

## 4. Limitações

- Nenhuma fonte pública própria para o die-code "4C1" — diferente do resto do catálogo SanDisk
  desta rodada, que é baseado em datasheet oficial ou distribuidor.
- Contagem de bolinhas do dono (~346) não reconciliada com as 169 do irmão — ver §2.
- Se o "1" no die-code de fato seguir o padrão X3(TLC)/X2(MLC) da geração 5xx, o `subtype`/`device`
  poderiam merecer nota de "TLC" no futuro — não confirmado, não adicionado agora.

## 5. Fontes

- Foto de referência enviada pelo dono (SDIN4C2-8G-U, SanDisk, TAIWAN, 169FBGA, EMMC 8GB) —
  arquivo de chat, não é URL pública.
- submissions/sandisk_sdin_2026-07-14.yaml (known_part SDIN4C28G, linha ~303).
- Buscas 26/08 e 27/08 (sem resultado real) — ver tip da família SDIN em
  chips/knowledge/sandisk.yaml para o histórico completo.

Decisão: dono, em chat, 27/08/2026 — "PODE CONFIRMAR COM AS MESMAS SPECS ENTAO".
