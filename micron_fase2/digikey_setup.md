# DigiKey API v4 — setup + fixtures (Fase 0, sonda 4)

> Decisão D3 = **criar conta DigiKey dev agora**. Fonte estruturada e sancionada do TOTAL/
> densidade (campo paramétrico **Memory Size**) e do formato (**Memory Format** = "FLASH, RAM"
> revela MCP), pros PNs que o catálogo Micron não cobre (o abreviado automotivo e o cluster do
> estoque `MT29…7D7`). O **segredo fica com você** (regra de ouro #1): você registra o app e roda
> o fetch; eu construo o parser sobre as respostas reais que você me mandar.

## 1. Criar a conta e o app (≈10 min, gratuito)

1. `developer.digikey.com` → **Register / Sign in** (conta DigiKey normal serve).
2. **My Organizations** → cria uma organização (nome livre, ex.: "eMiner").
3. **My Apps → Create App**. Assine o **Product Information V4** (marque o produto na lista de APIs).
   - OAuth: **Client Credentials (2-legged)** — é o fluxo pra dados públicos de produto.
   - Callback/redirect: pode pôr `https://localhost` (não usamos no 2-legged).
4. Copie **Client ID** e **Client Secret**.
5. Comece pelo **Sandbox** (host `sandbox-api.digikey.com`) pra validar o fluxo; depois troque pro
   **Production** (`api.digikey.com`) — mesmo código, só muda o host. (Sandbox pode devolver dado
   fake; a validação de SHAPE serve; os valores reais vêm do Production.)

## 2. Segredos (nunca commitar)

No `.env` local (já gitignored):
```
DIGIKEY_CLIENT_ID=xxxxxxxx
DIGIKEY_CLIENT_SECRET=xxxxxxxx
```
`.env` nunca vai pro git (regra de ouro #9). Eu não preciso das chaves — só das respostas JSON.

## 3. Endpoints (v4, confirmados 2026-07-15)

- Token (2-legged): `POST https://api.digikey.com/v1/oauth2/token`
  body `grant_type=client_credentials&client_id=…&client_secret=…` → `{access_token, expires_in…}`.
- **ProductDetails (o que queremos):**
  `GET https://api.digikey.com/products/v4/search/{productNumber}/productdetails`
  headers: `X-DIGIKEY-Client-Id: <client_id>`, `Authorization: Bearer <access_token>`,
  `accept: application/json`.
- Campos que importam na resposta: `Product.Parameters[]` com `ParameterText`∈{**Memory Size**,
  **Memory Format**, **Format**}, `Product.Description`, `Product.ManufacturerProductNumber`,
  `Product.Category`. **Memory Size** = TOTAL (ex.: "280Gbit") → vai só em `notes`, nunca em
  `capacity` de MCP. **Memory Format**="FLASH, RAM" confirma que é MCP (cross-check de tipo).
- Limites (confirmar no portal — variam por conta): historicamente ~1.000 req/dia no tier grátis +
  limite de rajada. Os 736 cabem em ~1 dia; o script tem `--delay`.

## 4. Fixtures — rode e me mande os JSON (sonda 4)

Salve como `scripts/digikey_fixtures.py` e rode (produz `micron_fase2/fixtures/digikey/<pn>.json`):

```python
#!/usr/bin/env python3
import os, sys, json, time, requests
CID, SEC = os.getenv("DIGIKEY_CLIENT_ID"), os.getenv("DIGIKEY_CLIENT_SECRET")
HOST = os.getenv("DIGIKEY_HOST", "https://api.digikey.com")   # sandbox: https://sandbox-api.digikey.com
assert CID and SEC, "defina DIGIKEY_CLIENT_ID / DIGIKEY_CLIENT_SECRET no ambiente"

tok = requests.post(f"{HOST}/v1/oauth2/token", data={
    "grant_type": "client_credentials", "client_id": CID, "client_secret": SEC}).json()["access_token"]
H = {"X-DIGIKEY-Client-Id": CID, "Authorization": f"Bearer {tok}", "accept": "application/json"}

PNS = [
    "MT29VZZZ7D7DQKWL",     # JZ083 — estoque, uMCP (7D7, fora do catálogo)
    "MT29TZZZ7D7EKKBT",     # JZ013 — estoque, uMCP (7D7)
    "MT62F1BAD4BS-DC-Y52P", # LPDDR5X abreviado automotivo (fora do catálogo)
    "MT53E1BAD4DB-DC",      # LPDDR4X abreviado
    # + 1 MTFC (eMMC) do seu identity_only.xlsx, ex.: filtre prefixo MTFC e cole 1 aqui
]
out = "micron_fase2/fixtures/digikey"; os.makedirs(out, exist_ok=True)
for pn in PNS:
    r = requests.get(f"{HOST}/products/v4/search/{requests.utils.quote(pn, safe='')}/productdetails", headers=H)
    open(f"{out}/{pn.replace('/', '_')}.json", "w", encoding="utf-8").write(
        json.dumps(r.json(), ensure_ascii=False, indent=1))
    print(pn, r.status_code)
    time.sleep(1.0)
print("→", out)
```

Me mande a pasta `micron_fase2/fixtures/digikey/` (ou cole os JSON no chat). Com o shape real eu
monto o cliente DigiKey dentro do `fill_micron_specs` (Fase D/E) — sem fixture, não escrevo parser.
