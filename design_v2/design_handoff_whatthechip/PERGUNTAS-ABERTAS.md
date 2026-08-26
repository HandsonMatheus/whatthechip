# Guia de backend — perguntas abertas

Salvo em 17/08/2026. Responder e eu escrevo o spec.

## Por que precisa de guia (resumo do diagnóstico)
Lendo só o HTML, o agente de backend pega o formato dos dados e o caminho felizinho. Ele vai errar em:
- **Sigilo** — o protótipo mascara no cliente (é demo). Em produção o endpoint tem que *omitir* o campo, não esconder no template.
- **Máquinas de estado** — a trilha de estágios mostra que existem estados, não quem transiciona, o que é irreversível, o que dispara notificação.
- **Regras invisíveis** — geração de `LOT/SO/INV/C-###`, ¥ canônico → US$ derivado, pagamento só em US$, acerto de câmbio, idempotência.
- **Fixture vs real** — `venda-data.js` e `parceiro-data.js` parecem API; são mocks.
- **Validações/erros** — só existem no HTML onde eu desenhei o estado.

O `README.md` deste diretório cobre design + matriz de papéis, mas está defasado: aponta para `screens/`, e os protótipos vivos são os de `ui_kits/whatthechip/`.

## Perguntas

1. **Conectar o repo Django?** Com o repo em mão o spec cita models/views/urls reais em vez de inventar nomes.
2. **Estado atual do backend:** greenfield · triagem/estoque já rodam · quase tudo, falta Vendas.
3. **Conteúdo do guia** (marcar o que o agente precisa): modelo de dados · contrato de endpoints · máquinas de estado e transições · matriz de permissões server-side · regras de validação · dinheiro/câmbio/pagamentos · eventos e notificações · geração de códigos canônicos · fixtures de seed · i18n 4 idiomas.
4. **Formato:** um SPEC.md único · specs por módulo + índice · spec + tarefas em ordem.
5. **Transporte:** HTMX devolvendo HTML parcial · JSON API · os dois.
6. **Protótipos canônicos para o build:** painel · estoque · triagem · venda (detalhe) · vendas-lista · parceiro (catálogo/compras/lote) · notificações · avisos · login + landing.
7. **Meus mocks de dados** (`venda-data.js`, `parceiro-data.js`): modelar por eles · só ilustrativos · reescrever como fixtures.
8. **Idioma do guia:** pt-BR · inglês.
9. **Restrições:** o que o agente já tem ou não pode mudar (ex: models de tenancy existem e não mexer, Postgres no Render, sem Celery).
