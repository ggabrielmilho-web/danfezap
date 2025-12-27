# Bot DANFE WhatsApp

Bot de WhatsApp em Python para motoristas autônomos consultarem DANFE (documento fiscal). O motorista digita a chave de 44 dígitos da nota fiscal e recebe o PDF do DANFE e o XML da NFe.

## 🚀 Stack Técnica

- **Linguagem:** Python 3.11+
- **Framework:** FastAPI
- **Banco de dados:** PostgreSQL 15
- **WhatsApp:** Evolution API v2.3.7+
- **Consulta DANFE:** API MeuDanfe (https://api.meudanfe.com.br/v2)
- **Pagamento:** Mercado Pago (Pix)
- **Containerização:** Docker + Docker Compose

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
│   │   ├── whatsapp.py      # Evolution API (enviar mensagens/PDF/XML)
│   │   ├── danfe.py         # Consulta API MeuDanfe (PDF e XML)
│   │   ├── pagamento.py     # Mercado Pago Pix
│   │   └── validador.py     # Validação chave NFe
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

# Evolution API
EVOLUTION_URL=https://api.carvalhoia.com
EVOLUTION_APIKEY=sua_api_key
EVOLUTION_INSTANCE=danfezap

# Mercado Pago
MERCADOPAGO_ACCESS_TOKEN=seu_access_token
MERCADOPAGO_WEBHOOK_SECRET=seu_webhook_secret

# MeuDanfe API
API_KEY=sua_api_key_meudanfe

# App
VALOR_ASSINATURA=14.90
DIAS_ASSINATURA=30
CONSULTAS_GRATIS=5
LIMITE_CONSULTAS_MES=100
```

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
  "app": "Bot DANFE WhatsApp",
  "version": "1.0.0"
}
```

## 🔧 Configurar Webhooks

### Evolution API

Configure o webhook no painel da Evolution API:

```
URL: http://seu-servidor.com:8000/webhook/evolution
Events: messages.upsert
```

### Mercado Pago

Configure o webhook no painel do Mercado Pago:

```
URL: http://seu-servidor.com:8000/webhook/mercadopago
Events: payment
```

## 📱 Como Funciona

### Fluxo do Usuário

1. **Primeiro contato**
   - Usuário envia mensagem no WhatsApp
   - Bot registra e dá **5 consultas grátis**
   - Envia mensagem de boas-vindas

2. **Consulta de DANFE (Usuário Gratuito)**
   - Usuário envia chave de 44 dígitos
   - Bot valida estrutura localmente (Módulo 11)
   - Consulta DANFE na API MeuDanfe
   - Envia PDF do DANFE e XML da NFe de volta
   - **Importante:** Apenas consultas bem-sucedidas consomem o contador (erros não contam!)
   - Após 5 consultas, precisa assinar

3. **Assinatura Mensal**
   - Valor: R$ 14,90/mês
   - Libera **100 consultas por mês**
   - Contador reseta a cada pagamento
   - Válida por 30 dias

4. **Renovação da assinatura**
   - Bot gera Pix de R$ 14,90
   - Usuário paga via Pix
   - Webhook confirma pagamento
   - Assinatura ativa por 30 dias + 100 consultas disponíveis

### Comandos

- **status** - Ver consultas usadas/disponíveis e dias restantes
- **ajuda** - Ver instruções de uso
- **assinar** - Gerar Pix para assinar/renovar
- **<chave_44_digitos>** - Consultar DANFE

### Sistema de Consultas

**Usuário Gratuito:**
- 5 consultas grátis
- Apenas consultas bem-sucedidas contam
- Erros não descontam do limite

**Assinante:**
- 100 consultas por mês
- Contador reseta a cada pagamento (não por mês calendário)
- Válida por 30 dias

## 🌐 Endpoints da API

### GET /
Health check da aplicação

### GET /health
Status de saúde do serviço

### GET /stats
Estatísticas do bot:
- Total de usuários
- Usuários ativos
- Total de consultas
- Taxa de sucesso

### POST /webhook/evolution
Recebe mensagens do WhatsApp

### POST /webhook/mercadopago
Recebe confirmações de pagamento

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

FastAPI gera documentação automática:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 📊 Monitoramento

### Ver logs em tempo real

```bash
# Logs da aplicação
docker logs -f danfezap-app

# Logs do PostgreSQL
docker logs -f danfezap-postgres
```

### Parar containers

```bash
docker-compose down
```

### Parar e remover volumes (limpar banco)

```bash
docker-compose down -v
```

## 🔒 Segurança

- Nunca commite o arquivo `.env` (já está no .gitignore)
- Use HTTPS em produção (nginx + certbot)
- Configure firewall para expor apenas as portas necessárias
- Valide webhook signatures do Mercado Pago em produção

## 🐛 Troubleshooting

### Container não inicia

```bash
# Ver logs completos
docker logs danfezap-app

# Reconstruir container
docker-compose up -d --build --force-recreate
```

### Erro de conexão com banco

- Verifique se o PostgreSQL está rodando: `docker ps`
- Verifique DATABASE_URL no .env
- Aguarde alguns segundos para o PostgreSQL iniciar completamente

### Webhook não recebe mensagens

- Verifique se a URL está acessível publicamente
- Use ngrok para testes locais: `ngrok http 8000`
- Configure a URL do webhook na Evolution API

## 📝 Licença

Projeto desenvolvido para uso comercial.

## 👨‍💻 Autor

Bot DANFE WhatsApp - Sistema de consulta de notas fiscais

---

**Versão:** 2.0.0
**Última atualização:** Dezembro 2025

## 📋 Changelog

### v2.0.0 (Dezembro 2025)
- ✅ Migração de "7 dias grátis" para "5 consultas grátis"
- ✅ Sistema de limite mensal: 100 consultas para assinantes
- ✅ Contador reseta a cada pagamento (não por mês calendário)
- ✅ Apenas consultas bem-sucedidas consomem o contador
- ✅ Comando "assinar" para gerar Pix
- ✅ Idempotência no webhook de pagamento
- ✅ Novos campos no banco: `consultas_gratis`, `assinante`, `consultas_mes`, `limite_consultas`
