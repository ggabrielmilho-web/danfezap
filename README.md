# Bot DANFE WhatsApp

Bot de WhatsApp em Python para motoristas autônomos consultarem DANFE (documento fiscal). O motorista digita a chave de 44 dígitos ou **envia foto do DANFE** para extração automática, e recebe o PDF do DANFE e o XML da NFe.

## 🚀 Stack Técnica

- **Linguagem:** Python 3.11+
- **Framework:** FastAPI
- **Banco de dados:** PostgreSQL 15
- **WhatsApp:** UazAPI
- **Consulta DANFE:** API MeuDanfe (primário) + ConsultaDanfe (fallback gratuito)
- **Pagamento:** Mercado Pago (Pix)
- **Processamento de imagem:** pyzbar (grátis) + Google Vision API (fallback)
- **Containerização:** Docker + Docker Compose (Swarm em produção)

## 📁 Estrutura do Projeto

```
danfezap/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app + webhooks
│   ├── config.py            # Configurações e variáveis de ambiente
│   ├── database.py          # Conexão PostgreSQL
│   ├── models.py            # SQLAlchemy models
│   ├── services/
│   │   ├── __init__.py
│   │   ├── whatsapp.py      # UazAPI (enviar mensagens/PDF/XML)
│   │   ├── danfe.py         # MeuDanfe + orquestrador de fallback
│   │   ├── consultadanfe.py # ConsultaDanfe (fallback gratuito)
│   │   ├── pagamento.py     # Mercado Pago Pix
│   │   ├── validador.py     # Validação chave NFe
│   │   └── image_reader.py  # Extração de chaves de imagens (pyzbar + Google Vision)
│   ├── handlers/
│   │   ├── __init__.py
│   │   └── mensagem.py      # Lógica de processamento das mensagens
│   └── utils/
│       └── __init__.py
├── requirements.txt
├── .env                     # Variáveis de ambiente (não commitar)
├── .env.example            # Template de variáveis
├── docker-compose.yml      # Orquestração dos containers
├── Dockerfile              # Build da aplicação
├── init_db.sql            # Script SQL das tabelas
└── README.md
```

## 🗄️ Banco de Dados

### Tabelas

**usuarios**
- Armazena usuários do bot, assinaturas e sistema de consultas
- Campos principais: `consultas_gratis`, `assinante`, `consultas_mes`, `limite_consultas`

**consultas**
- Histórico de consultas de DANFE realizadas (apenas bem-sucedidas contam no limite)

**pagamentos**
- Registro de transações do Mercado Pago

## ⚙️ Configuração

### 1. Clonar o repositório

```bash
git clone <repo-url>
cd danfezap
```

### 2. Configurar variáveis de ambiente

Copie o arquivo `.env.example` para `.env` e configure:

```bash
cp .env.example .env
```

Edite o arquivo `.env` com suas credenciais:

```env
# Banco de dados
DATABASE_URL=postgresql://botdanfe:senha_segura@localhost:5432/danfezap

# UazAPI (WhatsApp)
UAZAPI_URL=https://sua-instancia.uazapi.com
UAZAPI_TOKEN=seu_token

# URL base para webhooks
WEBHOOK_BASE_URL=https://seu-dominio.com

# Mercado Pago
MERCADOPAGO_ACCESS_TOKEN=seu_access_token
MERCADOPAGO_WEBHOOK_SECRET=seu_webhook_secret

# MeuDanfe API (primário)
API_KEY=sua_api_key_meudanfe

# ConsultaDanfe (fallback gratuito quando MeuDanfe falha; false desativa)
CONSULTADANFE_FALLBACK_ATIVO=true

# Google Vision API (opcional - fallback para leitura de imagens de baixa qualidade)
GOOGLE_VISION_API_KEY=sua_api_key_aqui

# App
VALOR_ASSINATURA=14.90
DIAS_ASSINATURA=30
CONSULTAS_GRATIS=2
LIMITE_CONSULTAS_MES=100

# Planos
VALOR_PLANO_BASICO=14.90
VALOR_PLANO_PRO=49.00
LIMITE_PLANO_BASICO=100
LIMITE_PLANO_PRO=1000

# Admin (kill switch do bot)
ADMIN_TOKEN=seu_token_secreto

# Follow-up automático
FOLLOWUP_ATIVO=true
```

**Como obter a Google Vision API Key:**
1. Acesse o [Google Cloud Console](https://console.cloud.google.com/)
2. Crie um projeto ou selecione um existente
3. Habilite a "Cloud Vision API"
4. Vá em "Credenciais" → "Criar credencial" → "Chave de API"
5. Copie a chave gerada e adicione no `.env`

**Nota:** A Google Vision API é **opcional**. O bot funciona apenas com pyzbar (gratuito), mas a Google Vision oferece melhor precisão em imagens de baixa qualidade.

### 3. Subir os containers

```bash
docker-compose up -d --build
```

Isso irá criar:
- **danfezap-postgres**: PostgreSQL na porta 5432
- **danfezap-app**: FastAPI na porta 8000

### 4. Verificar se está rodando

```bash
# Verificar containers
docker ps

# Verificar logs
docker logs danfezap-app

# Testar API
curl http://localhost:8000/
```

Resposta esperada:
```json
{
  "status": "online",
  "app": "Bot DANFE WhatsApp"
}
```

## 🔧 Configurar Webhooks

### UazAPI

Configure o webhook no painel da UazAPI:

```
URL: https://seu-dominio.com/webhook/uazapi
Events: messages.upsert
```

### Mercado Pago

Configure o webhook no painel do Mercado Pago:

```
URL: https://seu-dominio.com/webhook/mercadopago
Events: payment
```

## 📱 Como Funciona

### Fluxo do Usuário

1. **Primeiro contato**
   - Usuário envia mensagem no WhatsApp
   - Bot registra e dá **2 consultas grátis**
   - Envia mensagem de boas-vindas

2. **Consulta de DANFE (Usuário Gratuito)**
   - **Opção 1:** Usuário envia chave de 44 dígitos (digitando)
   - **Opção 2:** Usuário envia **foto do DANFE** (extração automática)
     - Bot analisa a imagem com pyzbar (código de barras/QR Code)
     - Se falhar, usa Google Vision API como fallback
     - Extrai chave automaticamente e valida
   - Bot valida estrutura localmente (Módulo 11)
   - Consulta DANFE: **MeuDanfe (primário)** → se falhar → **ConsultaDanfe (fallback gratuito)**
   - Envia PDF do DANFE e XML da NFe de volta
   - **Importante:** Apenas consultas bem-sucedidas consomem o contador (erros não contam!)
   - Após 2 consultas, precisa assinar

3. **Assinatura Mensal**

   | Plano | Valor | Consultas |
   |-------|-------|-----------|
   | Básico | R$ 14,90/mês | 100 consultas |
   | Pro | R$ 49,00/mês | Ilimitado |

   - Contador reseta a cada pagamento
   - Válida por 30 dias

4. **Renovação da assinatura**
   - Bot gera Pix via Mercado Pago
   - Usuário paga via Pix
   - Webhook confirma pagamento automaticamente
   - Assinatura ativa por mais 30 dias

### Comandos

- **status** - Ver consultas usadas/disponíveis e dias restantes
- **ajuda** - Ver instruções de uso
- **assinar** - Gerar Pix para assinar/renovar
- **<chave_44_digitos>** - Consultar DANFE (digitando)
- **<foto_danfe>** - Enviar foto do DANFE (extração automática)

### Sistema de Consultas

**Usuário Gratuito:**
- 2 consultas grátis
- Apenas consultas bem-sucedidas contam
- Erros não descontam do limite

**Assinante Básico:**
- 100 consultas por mês
- Contador reseta a cada pagamento (não por mês calendário)
- Válida por 30 dias

**Assinante Pro:**
- Consultas ilimitadas
- Válida por 30 dias

### Consulta de DANFE com Fallback

O bot usa duas fontes de DANFE com fallback automático:

1. **MeuDanfe (primário):** Sempre consultado primeiro. Cobre todos os tipos (NF-e, CT-e) e qualquer data.
2. **ConsultaDanfe (fallback gratuito):** Acionado automaticamente quando o MeuDanfe falha. Cobre NF-e do mês atual e do mês anterior (se antes do dia 15). O motorista não percebe a troca — recebe PDF e XML normalmente.

Para desativar o fallback: `CONSULTADANFE_FALLBACK_ATIVO=false` no `.env`.

## 📷 Processamento de Imagens

O bot aceita **fotos do DANFE** para extrair a chave automaticamente, facilitando o processo para motoristas que não querem digitar os 44 números.

### Como Funciona

1. **Usuário envia foto** do DANFE pelo WhatsApp
2. Bot envia mensagem "📷 Analisando imagem..."
3. **Primeira tentativa: pyzbar (GRÁTIS)**
   - Tenta ler código de barras ou QR Code
   - Suporta: EAN, CODE128, QR_CODE, etc.
   - Sem custo adicional
4. **Fallback: Google Vision OCR**
   - Caso pyzbar falhe, usa Google Vision API
   - OCR mais robusto para imagens de baixa qualidade
   - Custo: ~$1.50 por 1000 imagens
5. **Validação automática**
   - Extrai sequência de 44 dígitos
   - Valida com algoritmo Módulo 11
   - Se válida, processa automaticamente
6. **Resultado**
   - ✅ Chave encontrada → processa como se fosse digitada
   - ❌ Chave não encontrada → pede foto melhor ou digitar manualmente

### Estratégia de Custo

- **90%+ das imagens:** Processadas com pyzbar (gratuito)
- **10% restante:** Fallback para Google Vision (pago)
- **Custo estimado:** $0.15 por 1000 consultas com imagem

### Tipos de Imagem Suportados

✅ **Funciona bem:**
- Foto do código de barras do DANFE
- Print/screenshot do DANFE digital
- QR Code da NFe
- Foto clara com boa iluminação

❌ **Pode falhar:**
- Foto muito desfocada
- Iluminação ruim (sombras, reflexo)
- Código de barras danificado
- Imagem muito pequena (baixa resolução)

## 🌐 Endpoints da API

### GET /
Health check da aplicação

### GET /health
Status de saúde do serviço

### GET /stats
Estatísticas do bot (total usuários, consultas, taxa de sucesso)

### POST /webhook/uazapi
Recebe mensagens do WhatsApp

### POST /webhook/mercadopago
Recebe confirmações de pagamento

### POST /admin/bot/on e /admin/bot/off
Kill switch do bot (requer ADMIN_TOKEN)

### GET /admin/bot/status
Status atual do bot

## 🧪 Desenvolvimento Local

### Instalar dependências

```bash
pip install -r requirements.txt
```

### Rodar sem Docker

```bash
# Subir apenas o PostgreSQL
docker-compose up -d postgres

# Rodar aplicação localmente
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Acessar documentação automática

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 📊 Monitoramento (Produção)

### Ver logs em tempo real

```bash
docker service logs -f danfezap_danfezap-api
```

### Filtrar logs relevantes

```bash
docker service logs -f danfezap_danfezap-api 2>&1 | grep -iE "ConsultaDanfe|Fallback|ERROR"
```

### Verificar fallback em ação

Procurar nos logs por:
- `✓ Fallback ConsultaDanfe SALVOU consulta XXXXXXXX` — fallback acionado com sucesso
- `⚠ Erro inesperado no fallback ConsultaDanfe` — bug no fallback (não derruba o fluxo)

## 🔒 Segurança

- Nunca commite o arquivo `.env` (já está no .gitignore)
- Use HTTPS em produção
- Configure firewall para expor apenas as portas necessárias
- Valide webhook signatures do Mercado Pago em produção
- Kill switch disponível via `/admin/bot/off` com ADMIN_TOKEN

## 🐛 Troubleshooting

### Container não inicia

```bash
docker service logs danfezap_danfezap-api
```

### Webhook não recebe mensagens

- Verifique se a URL está acessível publicamente
- Confirme que o webhook está configurado na UazAPI apontando para `/webhook/uazapi`

### Bot não consegue ler imagens

- Verifique se `pyzbar`, `opencv-python-headless` e `Pillow` estão no requirements
- Reconstrua a imagem Docker após mudanças nas dependências
- `GOOGLE_VISION_API_KEY` é opcional mas melhora taxa de sucesso em imagens ruins

### MeuDanfe não encontra a nota

- O fallback ConsultaDanfe é acionado automaticamente
- Se ambos falharem, verifique `ultimo_erro` na tabela `consultas`
- Para notas muito antigas (mais de 2 meses), apenas o MeuDanfe cobre

## 📝 Licença

Projeto desenvolvido para uso comercial.

---

**Versão:** 2.2.0
**Última atualização:** Maio 2026

## 📋 Changelog

### v2.2.0 (Maio 2026)
- ✅ **Fallback ConsultaDanfe:** Quando MeuDanfe falha, tenta ConsultaDanfe automaticamente (gratuito)
- ✅ Consultas grátis reduzidas de 5 para 2
- ✅ Plano Pro adicionado: R$ 49/mês ilimitado
- ✅ Migração de Evolution API para UazAPI

### v2.1.0 (Janeiro 2026)
- ✅ **Processamento de imagens:** Usuários podem enviar foto do DANFE
- ✅ Extração automática de chave NFe via pyzbar (gratuito)
- ✅ Google Vision API como fallback para imagens de baixa qualidade
- ✅ Validação automática com Módulo 11

### v2.0.0 (Dezembro 2025)
- ✅ Migração de "7 dias grátis" para sistema de consultas grátis
- ✅ Sistema de limite mensal: 100 consultas para assinantes
- ✅ Contador reseta a cada pagamento (não por mês calendário)
- ✅ Apenas consultas bem-sucedidas consomem o contador
- ✅ Comando "assinar" para gerar Pix
