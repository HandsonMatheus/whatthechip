# Enviar chips IC para Macau — o que a DHL está pedindo, e o que eu encontrei

> **Data:** 19/08/2026 · **atualizado em 20/08/2026** com o que já foi
> implementado (§5) · **Fontes verificadas** (links no fim) · ⚠ **Não sou
> advogado nem despachante.** O que está aqui é pesquisa em fonte oficial, para
> você levar ao seu despachante — não é parecer jurídico.

---

## Resumo em três linhas

1. **A parte boa está confirmada:** circuito integrado (HS 8542) **não precisa
   de licença prévia de importação em Macau**. Isso vem da lista que a própria
   Macau notificou à OMC — não é interpretação.
2. **Mas a citação que o Gemini te deu está incompleta**: o Despacho 209/2021
   foi **alterado depois** (188/2022, 208/2022, **110/2023**). Citar só o de
   2021 numa fatura comercial é o tipo de coisa que um conferente detecta.
3. **E há um risco maior, que ninguém levantou:** o texto que o sistema usava na
   declaração — **“PCB CHIPS FOR DISPOSAL”** — declara a carga como **resíduo**.
   Desde **1/1/2025** resíduo eletrônico, mesmo não perigoso, exige
   consentimento prévio entre países (Basileia). É bem provável que **seja essa
   frase que está travando a DHL**, não a licença de importação.

---

## 1. Licença de importação em Macau: confirmado que NÃO precisa

O regime é a **Lei n.º 7/2003** (Lei do Comércio Externo), alterada pela **Lei
n.º 3/2016**. Quem precisa de licença prévia é só o que está na **Tabela B do
Anexo II**, fixada pelo **Despacho do Chefe do Executivo n.º 209/2021** e
alterada depois.

**A Tabela B tem cinco famílias** (segundo a notificação oficial de Macau à
OMC):

1. animais vivos, carne, produtos de origem animal, peixe, crustáceos,
   moluscos, vegetais, plantas vivas, sementes e fertilizantes;
2. **veículos**;
3. **aparelhos de telecomunicação e radiocomunicação**;
4. armas, munições e explosivos;
5. substâncias perigosas da Classe 7 (radioativas) e geradores de radiação
   ionizante.

O suplemento do **Despacho n.º 110/2023** acrescentou **compostos químicos**
(posições HS 2806–2939).

**Circuito integrado (HS 8542) não está em nenhuma delas.** Fora da Tabela B, o
importador só entrega a **declaração alfandegária de importação** no posto
aduaneiro, no dia da retirada.

⚠ **Um cuidado real:** a família 3 é *aparelho de telecomunicação e
radiocomunicação*. Chip solto de memória não é aparelho — mas se algum dia você
mandar **módulo/placa com rádio** (Wi-Fi, BT, celular), aí muda de figura.

---

## 2. O problema que eu acho que é o verdadeiro: a palavra “DISPOSAL”

Até 20/08/2026 o seu documento de embarque declarava:

> `PCB CHIPS FOR DISPOSAL`

*(já corrigido — veja §5; o diagnóstico abaixo fica registrado porque é o
motivo da mudança.)*

Isso, em linguagem aduaneira, **não descreve mercadoria — descreve resíduo para
descarte.** E a régua mudou:

- Em **1º de janeiro de 2025** entraram em vigor as emendas de e-waste da
  **Convenção de Basileia**. Criou-se a entrada **Y49 — “equipamento elétrico e
  eletrônico usado e em fim de vida”**, e **e-waste NÃO perigoso passou a exigir
  o procedimento de Consentimento Prévio Informado (PIC)** — que antes era só
  para resíduo perigoso.
- PIC é procedimento **entre Estados**: notificação e consentimento formal do
  país importador *antes* do embarque. Não é papel que se resolve na fatura.

Ou seja: declarando “for disposal”, você está declarando exatamente a categoria
que hoje precisa de autorização estatal prévia — e não tem.

**Mas os seus chips provavelmente não são resíduo.** Eles são recuperados,
classificados por tipo e capacidade, **testados, precificados e VENDIDOS a um
comprador que os reaproveita**. Sob Basileia, equipamento usado destinado a
**reuso direto**, comprovado, fica fora do regime de resíduo — e o ônus da prova
é do embarcador (registro de teste/funcionalidade, embalagem adequada, e uma
fatura que mostre venda para reuso, não descarte).

Você já tem a prova toda dentro do sistema: classificação por PN, categoria WTC,
quantidade, preço unitário e o comprador. O que falta é **o papel dizer isso**.

⚠ Isto é decisão sua e do seu despachante, não minha: se a carga é venda para
reuso, a descrição tem que dizer venda para reuso. Se de fato for descarte, aí o
caminho é o PIC, e é outro processo.

---

## 3. O terceiro ângulo: controle de exportação americano

É provavelmente por aqui que a DHL fica arisca com “IC chips → Macau”:

- **Macau é tratada junto com a China** nos controles americanos de computação
  avançada. Em 2026 o BIS reconfirmou que a exigência de licença para *advanced
  computing items* alcança entidades sediadas no Grupo D:5 **e em Macau**.
- **Mas o alvo são os ECCN 3A090 e 4A090** — processadores de alto desempenho
  (IA/computação). **Memória comum recuperada** (eMMC, LPDDR, DDR, NAND de
  celular) **não é 3A090**; costuma cair em EAR99 ou 3A991.
- E há a pergunta anterior a tudo: EAR alcança carga de **origem paraguaia**
  apenas se houver conteúdo/tecnologia americana acima do *de minimis*.

**O que isso significa na prática:** a declaração de uso final que o Gemini
sugeriu faz sentido — mas ela só vale se você **puder sustentar** a
classificação. Peça ao seu despachante a determinação de ECCN por escrito, uma
vez, e reuse.

---

## 4. O que anexar à DHL

**(a) A base legal de Macau** — cite as três coisas, não só uma:

> Under Macao SAR external trade law (Law No. 7/2003, as amended by Law
> No. 3/2016), prior import licensing applies only to goods listed in Table B of
> Annex II, as set by Chief Executive's Decision No. 209/2021 and its subsequent
> amendments (Decisions No. 188/2022, No. 208/2022 and No. 110/2023). Electronic
> integrated circuits (HS heading 8542) are **not** listed in Table B and are
> therefore **not subject to prior import licensing**; a standard import
> declaration is filed with Macao Customs upon arrival.

**(b) A descrição da mercadoria** — trocar a palavra que declara resíduo. Uma
formulação que descreve o que a carga é de fato:

> Recovered electronic integrated circuits (memory ICs), tested and graded,
> sold for reuse. Not waste; not for disposal or recycling.

**(c) Uma declaração de uso final**, se o questionamento for de controle de
tecnologia:

> The goods are commodity memory integrated circuits recovered from end-of-life
> consumer devices. They are not advanced computing items (ECCN 3A090 / 4A090)
> and are intended exclusively for legitimate civil commercial reuse.

⚠ **(a)** eu verifiquei em fonte oficial. **(b)** e **(c)** são rascunhos que
dependem de fatos seus — o despachante assina, não eu.

---

## 5. O que já mudou no sistema (feito em 20/08/2026)

Você mandou mexer — *"mude absolutamente tudo o que achar necessário, e adicione
a ele o anexo das leis também, cite tudo SEM ECONOMIZAR PALAVRAS, para NÃO ficar
brechas"*. O documento do gerente deixou de ser relatório e virou **documento de
despacho**:

| antes | agora |
|---|---|
| descrição `PCB CHIPS FOR DISPOSAL` | `RECOVERED ELECTRONIC INTEGRATED CIRCUITS (MEMORY ICs) — TESTED AND GRADED, SOLD FOR REUSE. NOT WASTE.` |
| sem código HS | **HS 8542** na caixa de declaração |
| sem base legal | **anexo regulatório** com as três declarações, em EN · 繁體中文 · ES |
| valor declarado aleatório 200–290 USD | **valor real da venda** |
| tabela de tipo × capacidade + preços | **uma tabela só: categoria WTC × quantidade** |
| câmbio impresso | fora do papel (segue no dado) |
| preço por categoria, unitário e total | **fora, para todo mundo — admin inclusive** |
| — | faixa de **transportadora · rastreio · data de envio** |

**O anexo, em três declarações** (cada uma nos três idiomas, sem resumir):

1. **Natureza da mercadoria — não é resíduo.** Recuperado, identificado por part
   number, testado, classificado, vendido sob fatura comercial para reuso direto.
   Não é resíduo, não é sucata, não viaja para descarte/reciclagem/recuperação —
   logo, fora das entradas **Y49** e **A1181** de Basileia (versão em vigor desde
   1/1/2025) e sem notificação PIC aplicável. A tabela de categoria e quantidade,
   com a fatura, **é** a prova de reuso — e o ônus dessa prova é seu, embarcador.
2. **Licenciamento de importação em Macau.** Lei n.º 7/2003, alterada pela Lei
   n.º 3/2016; Tabela B do Anexo II fixada pelo Despacho n.º 209/2021 e alterada
   pelos **188/2022, 208/2022 e 110/2023**; HS 8542 não consta; declaração
   alfandegária normal na chegada.
3. **Controle de exportação e uso final.** Não é 3A090 / 4A090; memória
   recuperada de aparelho de consumo, destinada a reuso civil comercial.

O papel fecha com **"Declared by the shipper"** e o nome da empresa: é declaração
do embarcador, não parecer jurídico.

### Três coisas que ficam na sua mão (não são decisão de código)

⚠ **1. O idioma. As línguas oficiais de Macau são chinês e PORTUGUÊS, não
espanhol.** Você pediu espanhol e eu fiz espanhol — só que quem lê do outro lado
lê português. Se o despachante preferir, trocar (ou somar um quarto) é mecânico:
é editar `_L` e `_ANEXO` em `vendas/pdf.py`. Me diz e eu faço.

⚠ **2. O valor declarado agora é o valor real da venda.** Antes era um número
entre 200 e 290 USD. Isso muda o que o papel afirma — mas o número antigo não
comprava nada: **Macau é porto franco**, não há tarifa sobre mercadoria geral, e
valor declarado que não bate com a fatura é problema aduaneiro por si só. Se você
quiser voltar atrás, é uma linha (`services.declared_value_usd`) — mas eu não
recomendo, e a decisão é sua.

⚠ **3. O texto do anexo é legal, com o seu nome.** Mostre ao despachante antes do
próximo embarque. Se ele mudar uma palavra, eu mudo no código com teste — o que
não dá é o papel dizer uma coisa e o despachante achar que diz outra.

## Fontes

- [Lei n.º 7/2003 — Lei do Comércio Externo de Macau (PDF oficial, Boletim Oficial)](https://images.bo.dsaj.gov.mo/bo/i/2003/25/lei-7-2003.pdf)
- [Lei n.º 7/2003 na base da OMC (import licensing)](https://www.importlicensing.wto.org/sites/default/files/members/88/Lei%20No.7_2003%20-%20Regula%C3%A7%C3%A3o%20das%20atividades%20de%20com%C3%A9rcio%20exterior_23.06.2003.pdf)
- [Despacho do Chefe do Executivo n.º 209/2021 — notificação de Macau à OMC, com as famílias da Tabela B](https://lic-public.wto.org/en/legislations/973)
- [Despacho n.º 110/2023 — suplemento à Tabela B (compostos químicos)](https://lic-public.wto.org/en/legislations/3021)
- [Portal do Governo de Macau — apresentação de declaração alfandegária (cita 209/2021, 188/2022, 208/2022, 110/2023)](https://www.gov.mo/pt/servicos/ps-1452/)
- [Portal do Governo de Macau — licença de importação (DSEDT)](https://www.gov.mo/en/services/ps-1320/)
- [Serviço de Declaração Alfandegária Electrónica (DSEDT)](https://www.dsedt.gov.mo/edi/pt_PT/index.jsp)
- [Emendas de e-waste da Convenção de Basileia em vigor desde 1/1/2025 (entrada Y49, PIC para e-waste não perigoso)](https://www.slrconsulting.com/us/insights/basel-convention-weee-amendments-2025/)
- [BIS reconfirma licença para *advanced computing items* a entidades do D:5 e de Macau (ECCN 3A090/4A090)](https://sanctionsnews.bakermckenzie.com/bis-clarifies-that-license-requirements-for-advanced-computing-items-to-country-group-d5-and-macau-headquartered-entities-remain-in-force-despite-ai-diffusion-rule-non-enforcement/)
- [Serviços de Alfândega de Macau](https://www.customs.gov.mo/)
