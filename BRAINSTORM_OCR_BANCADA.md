# BRAINSTORM_OCR_BANCADA.md — ler o PN pela lente

> Brainstorming (2026-08-27), **não** é plano aprovado. Decisões do dono na
> abertura: captura por **microscópio USB**, reconhecimento **no navegador**
> (offline, custo zero), modo **um chip por vez**.
> Versão navegável: https://claude.ai/code/artifact/60602e0f-f151-498c-af0f-9a372856f9b0

---

## 1. A tese

**O OCR não precisa acertar o PN. Precisa chutar perto o bastante pro banco fechar a conta.**

Quem decide o PN não é o motor de OCR — é o `KnownPart` mais os 266 prefixos da
gramática. O OCR entrega **hipótese**; o banco é o **juiz**.

Isso não é otimismo, é consequência de algo que já existe por outro motivo: a
`_CHIP_VISUAL_COST` do `engine.py`. Ela foi escrita para o **olho humano**
errando marcação a laser (`O↔Q` 0.1, `B↔8` 0.1, `1↔I` 0.1, `S↔5` 0.2). O
conjunto de erro de um OCR na mesma marcação é **o mesmo conjunto**, e não por
coincidência: a causa física é idêntica — traço fino, contraste baixo contra
epóxi preto, cantos arredondados pelo laser. O que apaga a cauda do `Q` pro
operador apaga pro Tesseract.

Ou seja: a função de custo que hoje ordena sugestão de typo é, **sem uma linha de
alteração**, um modelo de erro de OCR calibrado no domínio.

**Consequência de arquitetura:** o OCR nunca escreve direto na caixinha. Ele
propõe → o servidor ranqueia contra o catálogo → o `#pn-input` recebe o vencedor
com as alternativas penduradas. Mesma disciplina do resto do projeto: o portão
fica no fim do caminho.

---

## 2. Evidência — quanto erro o fuzzy atual já perdoa

Simulação sobre os **596 PNs do `seed_known_parts.json`**, usando
`_visual_edit_distance` como juiz. Modelo de erro: 45% confusão visual, 25%
substituição arbitrária, 15% deleção, 15% inserção.

### 2.1 Erros de caractere

| Erros | Top-1 | Top-3 | Fora do top-5 |
|---|---|---|---|
| 1 | 97,7% | 100,0% | 0,0% |
| 2 | 93,3% | 99,3% | 0,0% |
| 3 | 89,9% | 98,5% | 0,8% |
| 4 | 83,6% | 95,5% | 3,0% |

### 2.2 Truncamento (OCR acerta o que leu, mas para cedo)

| Leu | Top-1 | Top-3 | Fora do top-5 |
|---|---|---|---|
| 50% do PN | 29,4% | 61,4% | 19,8% |
| 60% do PN | 38,4% | 68,8% | 15,6% |
| 70% do PN | 42,1% | 73,7% | 11,9% |
| 80% do PN | 63,9% | 95,3% | 0,5% |

> **A métrica a perseguir não é acurácia por caractere — é COMPLETUDE DE LINHA.**
> Um OCR que lê 14 caracteres com 2 erros vale mais que um que lê 10 perfeitos.
> Isso inverte a prioridade de engenharia: enquadramento, foco e segmentação
> vêm ANTES de trocar de motor de reconhecimento.

### 2.3 Onde nenhum OCR salva

**1,3%** dos PNs do seed têm gêmeo a distância visual ≤ 0.5 — indistinguíveis
numa marcação gasta. Esses nunca se resolvem sozinhos. **O Enter do operador é
arquitetura, não cerimônia.**

### 2.4 O que os números NÃO provam (honestidade obrigatória)

- ~~São 596 PNs do seed, não os 6 mil+ do banco vivo — extrapolando, top-1 na casa
  dos 80.~~ **ERRADO, medido em 2026-08-27 contra os 8.601 PNs reais do banco:**

  | | 596 (seed) | **8.601 (banco)** |
  |---|---|---|
  | 1 erro | 97,1% | **98,8%** |
  | 2 erros | 91,9% | **94,8%** |
  | 3 erros | 91,4% | **93,6%** |

  O top-1 **subiu** com 14× mais PNs. A razão: o seed é enviesado — 357 dos 596
  são Samsung, um aglomerado de variantes quase idênticas (`K4B4G16…`), que é o
  pior caso possível para desempate. O banco inteiro é mais diverso, então um PN
  aleatório tem MENOS vizinhos próximos, não mais. A regra de UI (mostrar vencedor
  + 2 alternativas) continua valendo, mas por segurança, não por necessidade.
- O modelo de erro é **sintético, não medido na bancada**. Ele diz que a ponte
  aguenta *se* o Tesseract entregar esse perfil. Se der salada em epóxi preto,
  nada disso vale. É o que a Fase 0 existe pra descobrir.

---

## 3. O mecanismo

```
── NO NAVEGADOR (offline, custo zero) ──────┊── NO DJANGO (só texto atravessa) ──
                                            ┊
  Microscópio ──8 frames──> Canvas ──> OCR local ──N hipóteses──> O JUIZ
   luz rasante              cinza·contraste  whitelist    ┊    known_parts
   UVC                      ·limiar          A-Z0-9-      ┊    266 prefixos
                                            ┊             ┊    _visual_edit_distance
                                            ┊                        │
                                            ┊    leu: KMQ31OOO6M-B421│
                                            ┊    KMQ310006M-B421  0.3 ✓
                                            ┊    KMQ310006N-B421  1.0
                                            ┊    KMQ310006B-B421  1.0
                                            ┊                        │
  Operador confere <──↵── #pn-input <───vencedor + alternativas ──────┘
   pn-ready → HTMX          preenchido      ┊
```

**A imagem nunca sai da bancada** — o que atravessa é uma lista curta de strings.
É isso que mantém custo zero, latência abaixo da percepção e modo offline viável.

---

## 4. As cinco decisões que valem discussão

### 4.1 Mandar treliça, não string
O Tesseract sabe mais do que devolve: tem confiança **por caractere** e
alternativas por posição. Mandar uma string joga o sinal fora. Mande as **N
melhores hipóteses** e deixe o juiz pontuar todas — quando o motor está em
dúvida entre `O` e `0`, o banco desempata de graça.

### 4.2 Votação entre frames — o superpoder do microscópio
O microscópio está **parado**; celular na mão não tem isso. Pegue 8 frames do
mesmo chip e vote posição por posição. Ruído de sensor é aleatório, a letra não
é. Ganho de acurácia mais barato do projeto: nenhum modelo novo, nenhuma
dependência, só um laço e um contador.

### 4.3 Qual das linhas é o PN? A gramática responde
O chip tem 3–4 linhas gravadas (part number, date code, lot code, logo). Não
precisa de heurística: **a linha que casa um dos 266 prefixos é o PN**.
Discriminador brutal e já pago.

### 4.3b Leitura parcial — e uma mudança candidata no `engine.py`

O `_prefix_candidates` do engine casa por `startswith`: cobre o PN **truncado no
fim** (o operador parou de digitar), que é o erro de quem digita. O erro de quem
**fotografa** é outro: dedo, sujeira ou o quadro comendo o **começo**. Aconteceu
na 1ª sessão real — `NT5CC512M8EN-EK` lido como `5CC512M8EN-`, e o juiz devolvia
NADA com o PN no banco (não é prefixo, e a diferença de comprimento estoura a
janela de ±3 do fuzzy).

A bancada passou a alinhar por **janela** (semi-global): a leitura casa inteira
em qualquer posição do candidato; pular o começo e o fim sai de graça, e o que
ficou fora entra no score a 0,35/caractere. Medido sobre os 8.601:

| Leitura parcial | top-1 | top-3 | fora |
|---|---|---|---|
| faltam 2-3 do começo | **99,3%** | 99,3% | 0% |
| faltam 2 de cada ponta | 76,0% | 92,0% | 0% |

**Assimetria que vale como regra de bancada: perder o começo é quase de graça,
perder o fim custa caro** — é no sufixo que as variantes se separam (`-DI` × `-EK`),
e aí o empate é honesto: a informação não está na imagem. Se o operador tiver que
escolher o que enquadrar, que enquadre o **fim** do PN.

> 🔧 **Candidato a mudança no `engine.py`** (não feito — é código, precisa do dono):
> trocar/complementar `_prefix_candidates` por alinhamento de janela beneficiaria
> também a **busca digitada**, não só o OCR — hoje quem digita a partir do meio do
> PN não acha nada. Custo controlado por índice de trigramas (sem ele são 3,5 s
> para 12 hipóteses; com ele, 361 ms).

### 4.4 O ganho está na LUZ, não no motor
Laser em epóxi preto é **relevo**, não tinta — quase sem contraste de cor, só de
sombra. O LED anelar do microscópio ilumina de frente e **apaga a marcação**.
Luz rasante (quase paralela à superfície) faz o sulco projetar sombra e o texto
saltar. **Antes de trocar de OCR, mate o anel e ponha um LED de lado.**

### 4.5 Deixe o banco julgar a rotação
O chip cai em qualquer ângulo. Em vez de detectar o pino 1: rode a imagem em 0°,
90°, 180°, 270°, rode OCR nas quatro e mande as quatro pro juiz. Três voltam como
lixo que não casa prefixo nenhum; uma casa. Custa 4× de CPU local (grátis) e
elimina uma classe inteira de bug.

### 4.6 ~~ATALHO — comece pelo FBGA~~ → **RETRATADO (2026-08-27)**

> Eu recomendei começar pelo FBGA: "5 caracteres é outra ordem de grandeza mais
> fácil que 14". **Errado por dois motivos independentes, e os dois são meus.**

**Motivo 1 — o FBGA é EXCLUSIVO da Micron.** Não é uma propriedade dos chips, é
uma convenção de marcação de UM fabricante. Contado no banco:

| | PNs | com `fbga_code` |
|---|---|---|
| Micron | 6.631 | **6.624** |
| Samsung, SK Hynix, Toshiba-Kioxia, SanDisk, Nanya, Kingston, PieceMakers, Foresee, Rayson, ESMT, GigaDevice | 1.970 | **0** |

Eu escrevi "77% do catálogo tem FBGA" como se fosse um número guia. É verdade
aritmética e mentira operacional: o catálogo é 77% Micron porque a Micron entrou
por **importação em massa de CSV** (`import_micron_catalog`), não porque a
bancada veja 77% de chips Micron. Para as outras onze marcas o FBGA simplesmente
**não existe** — o operador lê o PN completo ou não lê nada.

**Motivo 2 — mesmo na Micron, 5 caracteres são frágeis.** Medido com 1 erro de OCR:

| | top-1 | fora da lista |
|---|---|---|
| Código FBGA (5 chars) | **59,5%** | **26,0%** |
| PN completo (10-20 chars) | **98,8%** | 0,0% |

A causa é redundância. Um PN de 14 caracteres com um erro ainda tem 13 corretos
restringindo o casamento; um código de 5 perdeu 20% da informação — e o espaço é
denso: **99,3% dos códigos FBGA têm ao menos um vizinho a distância visual ≤ 1.0**,
com média de 17,3 vizinhos.

**Conclusão:** o FBGA é um caso especial da Micron, ótimo lido **perfeito**
(lookup exato, instantâneo) e de alta variância quando não. O pipeline se desenha
em cima do **PN completo**, que é o que todas as marcas têm.

> ⚠ O motivo 2 só apareceu porque a bancada tinha um bug: portei o lookup EXATO
> de FBGA e esqueci o fuzzy (`_fuzzy_fbga_candidates`, que existe no
> `engine.py`). Sem ele a recuperação era **0,8%** — um erro no código perdia o
> PN inteiro, porque o código tem 5 caracteres e os PNs têm 10-20, então nenhuma
> outra etapa alcança o registro. Corrigido; os 59,5% já são com o fuzzy.

---

## 5. Onde isso quebra

| Severidade | Risco | Nota |
|---|---|---|
| **Maior incerteza** | Tesseract nunca viu fonte de laser industrial | Treinado em texto impresso/digitalizado. Marcação a laser tem traço irregular, espaçamento apertado, caracteres parcialmente formados. **Ninguém sabe o resultado sem medir na bancada, com os chips reais.** Toda estimativa deste doc depende disso. |
| **Comum** | Marcação rasa ou gasta | Dessoldagem, solvente, anos de operação. Se o operador precisa girar o chip contra a luz, o OCR também falha. O sistema tem que **desistir rápido e em silêncio** — OCR que demora 3s pra falhar é pior que nenhum. |
| **Estrutural** | Profundidade de campo × lote de chip grande | Microscópio USB serve bem pra memória de 10–15 mm. O lote de **lógica programável/SoC de 35–70 mm** ou reduz ampliação (perde a resolução que faz o OCR funcionar) ou exige varredura+costura. Decidir cedo se chip grande entra na Fase 1. |
| **Silencioso** | O erro que passa pela conferência | Com 90% de acerto o operador **para de conferir de verdade** na 3ª hora — vira Enter automático, e aí os 10% viram estoque errado (pior que hoje, porque hoje o erro é dele e ele sabe). Mitigação: (a) mostrar o **recorte da imagem** ao lado do PN proposto — conferir vira comparação visual, não leitura; (b) **não preencher** quando a margem entre 1º e 2º for apertada — mostrar os dois e obrigar a escolha. |
| **Vira feature** | Chip remarcado (falsificação) | O OCR lê o PN falso, mas a fonte regravada quase nunca bate com a do fabricante e a centralização muda. Ruído hoje, **detector depois** — sinal de "conferir na mão" que nenhum concorrente tem. |

---

## 6. O ativo escondido: cada Enter é um dado rotulado

Quando o operador confirma ou corrige, ele produz um par **imagem ↔ PN certo**,
rotulado por um humano com o chip na mão. Caro de comprar; centenas por dia de
graça.

Mesmo espírito do `SearchLog`/`UnknownChip` que já existem — só que com a imagem
junto. É o que transforma OCR genérico em modelo **próprio**: em alguns meses de
bancada dá pra treinar um reconhecedor específico de marcação a laser de chip.

Para a ambição de "Google dos chips" esse é o **fosso** — mais que a contagem de
known_parts. O catálogo se copia se vazar; o dataset de leitura óptica de
bancada, não.

> **Desenhar o modelo de captura já na Fase 0, mesmo sem usar.** Guardar o
> recorte é barato; regenerar dez mil confirmações jogadas fora, não.

---

## 7. Caminho — quatro fases, blast radius zero

### FASE 0 — bancada de medição (nenhuma escrita no banco)
Página isolada, **fora** do fluxo de estoque. Captura pelo microscópio,
pré-processa, roda OCR, **mostra o que leu** e o operador digita o certo ao lado.
Nada toca `KnownPart`, nada toca lote. Cem chips reais bastam.

Responde a única pergunta que importa antes de investir: **qual o perfil de erro
real do Tesseract nos seus chips?** 2 erros por PN → o resto se sustenta. 6 erros
→ o caminho é outro, descoberto por um dia de trabalho e não por um mês.

**Entrega:** tabela de erro real + decisão de seguir ou parar.

> ✅ **CONSTRUÍDA — [`ocr_bench/`](ocr_bench/) (2026-08-27).** Página solta, fora do
> Django, roda com `cd ocr_bench && python3 -m http.server 8000`. Tem câmera com
> ROI arrastável, pré-processo ao vivo (escala/contraste/Otsu/inverter/realce),
> Tesseract 5 com whitelist `A-Z0-9-`, o juiz portado do `engine.py` e o registro
> de amostras com export CSV. Instruções em `ocr_bench/LEIA-ME.md`.
>
> **Medido no port JS contra o corpus real** (596 PNs do seed): distância visual
> confere 5/5 com os exemplos do `FUZZY.md`; recuperação 97,1% / 91,9% / 91,4%
> top-1 para 1/2/3 erros (top-3 ≥ 98,8%) — bate com a simulação em Python do §2.
> FBGA resolve (`JW699` → `MT29C4G48MAZAPAKD5EIT`, score 0) e **95% dos PNs casam
> um prefixo da gramática**, que é o que permite descartar as linhas de date/lot
> code. Julgamento em **2,6 ms** com 596 PNs (~236 ms extrapolado p/ os 6 mil do
> banco) — a versão ingênua levava 2 s e teria inviabilizado a bancada.

### FASE 1 — a caixinha se preenche
Endpoint novo `/chips/ocr_resolve/`: recebe hipóteses de texto, devolve ranking,
reusando `_combined_suggestions` — **sem tocar no `classify()`**.

O front reusa o caminho que o `mic.js` já abriu — e vale registrar como ele
funciona de fato, porque é o contrato: o `mic.js` **não** dispara `pn-ready`.
Ele preenche `input.value`, dispara `input`+`change` (linhas 201-203) e então
**clica o CTA** apontado por `data-mic-cta` (linhas 232-240) — o
`est-decode-btn`, que é quem chama `htmx.trigger(pnInput,'pn-ready')`
(estoque.html:1528); há fallback por `KeyboardEvent` Enter (linha 246).

Ou seja o padrão de entrada assistida já está desenhado e testado: **preencher +
acionar o CTA existente**. O OCR vira o terceiro emissor, ao lado de teclado e
voz, sem inventar caminho novo. O `#ocr-status` já está no template esperando
(estoque.html:1226).

Zero mudança no fluxo do operador. O Enter continua sendo dele, `PendingEntry`
continua igual, e desligar é remover um `<script>`.

**Entrega:** o PN chega digitado · fallback = digitar como hoje.

### FASE 2 — votação, rotação e a gramática como juiz
Só depois da Fase 1 rodando na bancada: multi-frame, quatro orientações, seleção
de linha por prefixo, treliça em vez de string única. Cada um é **medível
isoladamente** contra a tabela da Fase 0 — dá pra saber quanto cada um comprou.

**Entrega:** ganho de acurácia medido, um mecanismo por vez.

### FASE 3 — o loop de aprendizado
Guardar o par imagem↔PN confirmado desde a Fase 0; com volume, treinar o
reconhecedor próprio. Só faz sentido depois que a operação gera dado sozinha — e
não custa nada se começar a guardar cedo.

**Entrega:** modelo próprio de marcação a laser.

---

## 8. O que eu não sei — a Fase 0 responde

1. **Qual o perfil de erro do Tesseract nos seus chips?** Tudo aqui depende disso
   e não dá pra estimar de fora. Primeira medição.
2. **Quanto do tempo do operador é digitação?** 200 chips/hora × 14 caracteres →
   ganho óbvio. Se o gargalo é pegar o chip e olhar contra a luz, o OCR economiza
   pouco e o dinheiro está em outro lugar.
3. **Que fração do lote é Micron com código FBGA?** Muda a ordem das fases: se
   for grande, começa por 5 caracteres em vez de 14.
4. **O microscópio aparece como webcam comum no Chrome?** A maioria dos USB é UVC
   e aparece — mas alguns entregam resolução baixa demais. Decide se dá pra usar
   `getUserMedia` direto.
5. **Chip grande do lote de lógica programável entra na Fase 1 ou fica de fora?**
   É a decisão que mais muda o escopo — melhor tomada antes de escrever código.

---

## 9. Fontes lidas

`CLAUDE.md` · `FUZZY.md` · `chips/engine.py` (`_visual_edit_distance`,
`_combined_suggestions`, `_prefix_candidates`, camada 2 FBGA) ·
`estoque/templates/estoque/estoque.html` (a bancada, `#pn-input`, `pn-ready`,
`#ocr-status`) · `static/js/mic.js` (precedente de entrada assistida) ·
`static/wtc/tokens/colors.css` · `chips/knowledge/*.yaml` (266 prefixos) ·
`seed_known_parts.json` (596 PNs).
