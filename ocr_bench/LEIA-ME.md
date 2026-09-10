# ocr_bench — bancada de medição de OCR (Fase 0)

> **Não faz parte do sistema.** É uma página solta que roda no navegador, fora do
> Django. Não importa nada do projeto, não abre conexão com o banco, não escreve
> em lugar nenhum. Pode apagar a pasta inteira sem consequência.
>
> Existe para responder **uma** pergunta antes de investir em OCR de verdade:
> *qual é o perfil de erro real do Tesseract nos seus chips?*
> Contexto e o porquê: [`../BRAINSTORM_OCR_BANCADA.md`](../BRAINSTORM_OCR_BANCADA.md)

---

## Rodar

```bash
cd ocr_bench
python3 -m http.server 8000
```

Abra **http://localhost:8000/** no Chrome.

> ⚠ **Tem que ser `http://localhost`, não `file://`.** A câmera (`getUserMedia`)
> só abre em contexto seguro. Abrindo o arquivo direto, o resto funciona e a
> câmera não — a página avisa. Carregar foto do disco funciona nos dois casos.

**Primeira abertura precisa de internet:** o Tesseract vem de CDN (~15 MB entre
motor e idioma) e fica no cache do navegador. Da segunda vez em diante roda
offline.

---

## Arquivos

| Arquivo | O que é |
|---|---|
| `index.html` | a bancada inteira — HTML, CSS e JS num arquivo só |
| `corpus.js` | **gerado**, o "juiz": PNs + prefixos de família. Não editar à mão |
| `gerar_corpus.py` | regenera o `corpus.js`. **Só leitura**, não toca em nada |

### Trocar o corpus pelo banco de verdade

O `corpus.js` que veio junto tem os **596 PNs do seed**. O banco tem 6 mil+ —
e a qualidade da medição depende diretamente disso. Assim que der:

```bash
# da RAIZ do repo, com o venv ativo:
source venv/bin/activate
python3 ocr_bench/gerar_corpus.py --from-db        # banco LOCAL
```

Para gerar a partir do banco de produção (continua sendo **só leitura** — nenhum
`INSERT`, `UPDATE` ou `DELETE`):

```bash
export DATABASE_URL="postgresql://…render.com:5432/…"
python3 ocr_bench/gerar_corpus.py --from-db
```

Ele lê `KnownPart` com `review_status='approved'` e confidence em
`confirmed/manual/distributor` — a mesma janela que o `_fuzzy_candidates` usa no
`engine.py`.

---

## Como usar na bancada

1. **Abrir câmera** e escolher o microscópio na lista. (Se os nomes vierem em
   branco, clique em Abrir câmera uma vez para o Chrome pedir permissão — os
   nomes aparecem depois.)
2. **Arrastar a caixa azul (ROI)** por cima da marcação e ajustar largura/altura.
   Só o que está dentro dela vai pro OCR.
3. **Conferir a prévia em preto e branco.** O alvo é: letra preta sólida, fundo
   branco limpo. Os padrões já vêm calibrados (ver §Calibração abaixo) — na maior
   parte dos casos não precisa mexer em nada. A faixa de diagnóstico embaixo da
   prévia diz o que ajustar quando precisa.
4. **Espaço** (ou o botão) para ler.
5. **Conferir o PN de verdade no chip**, digitar no campo e dar **Enter**.
   Se o candidato certo estiver na lista, dá pra clicar nele em vez de digitar.
6. Repetir. **Cem chips reais** já dão uma medição honesta.
7. **Exportar CSV** no fim.

Chip que você mesmo não consegue ler: **Ilegível / pular**. Isso também é dado —
mede quanto do lote está fora do alcance de qualquer OCR.

---

## O que os números querem dizer

| Indicador | Leitura |
|---|---|
| **top-1** | quantas vezes o candidato nº 1 do juiz era o PN certo — é o que decide se o operador só confere e dá Enter |
| **top-3** | quantas vezes o certo apareceu entre os 3 primeiros — se este for alto e o top-1 baixo, a interface resolve (mostrar 3 chips clicáveis) |
| **fora da lista** | o certo nem apareceu. É o número que mata o projeto se for alto |
| **erros/PN** | distância média entre a melhor hipótese crua do OCR e a verdade. **É a medida do MOTOR**, sem a ajuda do juiz |
| **ms por leitura** | acima de ~1500 ms o operador sente, e o OCR passa a atrapalhar em vez de ajudar |

### Referência medida contra o banco real (8.601 PNs, 2026-08-27)

| Erros no que o OCR leu | top-1 | top-3 | fora da lista |
|---|---|---|---|
| 1 erro | 98,8% | 100% | 0,0% |
| 2 erros | 94,8% | 100% | 0,0% |
| 3 erros | 93,6% | 99,6% | 0,0% |

**Se a bancada der 2 erros por PN, o caminho está de pé.** Se der 5 ou 6, o
problema é óptico (luz, foco, enquadramento) e não adianta trocar de motor.

### Leitura parcial — o dedo tapando o começo do PN

O juiz alinha por **janela**: a leitura precisa casar inteira, mas pode sentar em
qualquer posição do PN — pular o começo e o fim do candidato é de graça, e o que
ficou de fora entra no score a 0,35 por caractere. Medido:

| Leitura parcial | top-1 | top-3 | fora da lista |
|---|---|---|---|
| faltam 2 do começo | **99,3%** | 99,3% | 0% |
| faltam 3 do começo | **99,3%** | 99,3% | 0% |
| faltam 2 de cada ponta | 76,0% | 92,0% | 0% |
| faltam 3 do começo + 2 do fim | 74,0% | 90,7% | 0% |

> **Se tiver que escolher o que enquadrar, enquadre o FIM do PN.** Perder o começo
> é quase de graça — o miolo é único o bastante. Perder o fim custa caro porque é
> lá que as variantes se separam (`NT5CC512M8EN-**DI**` × `NT5CC512M8EN-**EK**`),
> e nesse caso o sistema empata os dois de propósito: a informação não está na
> imagem, então quem decide é o operador. Note que **fora da lista é 0% nos quatro
> casos** — o certo sempre aparece, é só escolher.

Candidato achado assim vem com badge `JANELA`.

### ⚠ Código FBGA é caso especial da Micron — não é guia

Dos 8.601 PNs, **6.624 têm código FBGA e TODOS são Micron**. Nenhuma das outras
onze marcas (Samsung, SK Hynix, Toshiba-Kioxia, SanDisk, Nanya, Kingston,
PieceMakers, Foresee, Rayson, ESMT, GigaDevice) tem um só. O catálogo parece
"77% FBGA" porque a Micron entrou por importação em massa de CSV — não porque a
bancada veja isso.

E mesmo na Micron, com 1 erro de OCR:

| | top-1 | fora da lista |
|---|---|---|
| Código FBGA (5 chars) | 59,5% | **26,0%** |
| PN completo | 98,8% | 0,0% |

Cinco caracteres não têm redundância: **99,3% dos códigos FBGA têm vizinho a
distância visual ≤1.0** (média de 17,3 vizinhos). Se o candidato vier com badge
`FBGA` e score acima de zero, **confira com atenção redobrada**.

### O painel "pares que o OCR confunde"

Conta cada substituição `lido→certo`. Par marcado com **✦** ainda **não** está na
`_CHIP_VISUAL_COST` do `engine.py` — é candidato a entrar, e isso melhora as
sugestões fuzzy **de todo o sistema**, não só do OCR. É o subproduto mais barato
desta bancada.

---

## Duas coisas para saber

**A luz importa mais que o motor — e isso já foi medido aqui, não é teoria.** Marcação a laser em epóxi preto é relevo, não
tinta — quase não tem contraste de cor, só de sombra. O LED anelar do microscópio
ilumina de frente e **apaga** a marcação. Um LED de lado, quase rasante, faz o
sulco projetar sombra e o texto saltar. Vale testar isso antes de mexer em
qualquer ajuste da tela.

**Guardar o recorte.** O checkbox no fim baixa a imagem do ROI nomeada com o PN
confirmado a cada amostra. Cada uma é um par `imagem ↔ PN certo` rotulado por
humano — a semente do dataset da Fase 3. Guardar é barato; regerar depois, não.

---

## Git

Esta pasta **não deveria ir pro repositório** — o `corpus.js` é gerado e pode
carregar PNs do banco de produção. Sugestão de linha no `.gitignore`:

```
# bancada de medição de OCR (local, descartável)
ocr_bench/
```

*(não mexi no seu `.gitignore` — a linha fica aqui para você decidir)*
