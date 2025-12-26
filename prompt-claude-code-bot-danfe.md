# Documentação Completa - Bot DANFE WhatsApp

## Contexto do Projeto

Bot de WhatsApp em Python para motoristas autônomos consultarem DANFE (documento fiscal). O motorista digita a chave de 44 dígitos da nota fiscal e recebe o PDF de volta.

---

# TAREFAS (executar em ordem)

## TAREFA 1: Setup inicial e estrutura do projeto
- Criar estrutura de pastas
- Criar requirements.txt
- Criar .env.example
- Criar docker-compose.yml
- Criar config.py

## TAREFA 2: Banco de dados
- Criar database.py (conexão PostgreSQL)
- Criar models.py (SQLAlchemy)
- Criar script SQL de criação das tabelas

## TAREFA 3: Validador de chave NFe
- Criar validador.py
- Implementar validação dos 44 dígitos
- Implementar cálculo do dígito verificador

## TAREFA 4: Serviço de consulta DANFE
- Criar danfe.py
- Implementar consulta na API externa
- Tratar retorno base64 para bytes

## TAREFA 5: Integração Evolution API (WhatsApp)
- Criar whatsapp.py
- Implementar envio de mensagem texto
- Implementar envio de PDF

## TAREFA 6: Integração Mercado Pago
- Criar pagamento.py
- Implementar geração de Pix
- Implementar verificação de pagamento

## TAREFA 7: Handler de mensagens
- Criar mensagem.py
- Implementar lógica principal do bot
- Implementar todas as mensagens

## TAREFA 8: App principal e webhooks
- Criar main.py (FastAPI)
- Implementar webhook Evolution API
- Implementar webhook Mercado Pago

## TAREFA 9: Finalização
- Criar Dockerfile
- Criar README.md
- Testar fluxo completo

---

# ESPECIFICAÇÕES DETALHADAS

## Stack Técnica

- **Linguagem:** Python 3.11+
- **Framework:** FastAPI
- **Banco de dados:** PostgreSQL
- **WhatsApp:** Evolution API (webhook para receber mensagens, API REST para enviar)
- **Consulta DANFE:** API https://consultadanfe.com/CDanfe/api_generate
- **Pagamento:** Mercado Pago API (Pix)

## Estrutura do Projeto

```
bot-danfe/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app + rotas webhook
│   ├── config.py            # Variáveis de ambiente
│   ├── database.py          # Conexão PostgreSQL
│   ├── models.py            # SQLAlchemy models
│   ├── services/
│   │   ├── __init__.py
│   │   ├── whatsapp.py      # Evolution API (enviar mensagens/PDF)
│   │   ├── danfe.py         # Consulta API DANFE
│   │   ├── pagamento.py     # Mercado Pago Pix
│   │   └── validador.py     # Validação chave NFe
│   ├── handlers/
│   │   ├── __init__.py
│   │   └── mensagem.py      # Lógica de processamento das mensagens
│   └── utils/
│       ├── __init__.py
│       └── helpers.py
├── requirements.txt
├── .env.example
├── docker-compose.yml       # PostgreSQL + App
└── README.md
```

## Banco de Dados (PostgreSQL)

### Tabela: usuarios

```sql
CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY,
    telefone VARCHAR(20) UNIQUE NOT NULL,
    nome VARCHAR(100),
    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    data_expiracao TIMESTAMP NOT NULL,
    ativo BOOLEAN DEFAULT TRUE,
    mercadopago_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Tabela: consultas

```sql
CREATE TABLE consultas (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER REFERENCES usuarios(id),
    chave_nfe VARCHAR(44) NOT NULL,
    data_consulta TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sucesso BOOLEAN,
    tentativas INTEGER DEFAULT 1,
    ultimo_erro TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Tabela: pagamentos

```sql
CREATE TABLE pagamentos (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER REFERENCES usuarios(id),
    valor DECIMAL(10,2) NOT NULL,
    data_pagamento TIMESTAMP,
    id_transacao_mp VARCHAR(100),
    status VARCHAR(20) DEFAULT 'pendente',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Validação Local da Chave NFe (44 dígitos)

Implementar validação antes de chamar a API externa:

```python
def validar_chave_nfe(chave: str) -> dict:
    """
    Valida estrutura da chave de 44 dígitos
    
    Estrutura:
    - Posição 1-2: UF (código IBGE: 11-53)
    - Posição 3-4: Ano (ex: 24, 25)
    - Posição 5-6: Mês (01-12)
    - Posição 7-20: CNPJ emitente (14 dígitos)
    - Posição 21-22: Modelo (55=NFe, 57=CTe)
    - Posição 23-25: Série
    - Posição 26-34: Número da nota
    - Posição 35: Forma de emissão (1-9)
    - Posição 36-43: Código numérico
    - Posição 44: Dígito verificador
    
    Retorna:
    {"valida": True/False, "erro": "mensagem se inválida"}
    """
    
    # Verificar se tem 44 dígitos numéricos
    # Verificar UF válida (códigos IBGE)
    # Verificar mês válido (01-12)
    # Verificar modelo válido (55 ou 57)
    # Calcular e verificar dígito verificador (módulo 11)
```

Códigos UF válidos (IBGE):
```python
UFS_VALIDAS = {
    '11': 'RO', '12': 'AC', '13': 'AM', '14': 'RR', '15': 'PA',
    '16': 'AP', '17': 'TO', '21': 'MA', '22': 'PI', '23': 'CE',
    '24': 'RN', '25': 'PB', '26': 'PE', '27': 'AL', '28': 'SE',
    '29': 'BA', '31': 'MG', '32': 'ES', '33': 'RJ', '35': 'SP',
    '41': 'PR', '42': 'SC', '43': 'RS', '50': 'MS', '51': 'MT',
    '52': 'GO', '53': 'DF'
}
```

## API Consulta DANFE

Endpoint: `POST https://consultadanfe.com/CDanfe/api_generate`

```python
import requests
import base64

def consultar_danfe(chave: str) -> dict:
    """
    Consulta DANFE na API
    
    Retorna:
    {
        "sucesso": True/False,
        "pdf_bytes": bytes ou None,
        "filename": str ou None,
        "erro": str ou None
    }
    """
    
    # Montar XML mínimo com a chave ou enviar chave direto
    # POST para API
    # Se sucesso: decodificar base64 para bytes
    # Retornar resultado
```

## Evolution API (WhatsApp)

### Receber mensagens (Webhook)

```python
@app.post("/webhook/evolution")
async def webhook_evolution(request: Request):
    """
    Recebe mensagens do WhatsApp via Evolution API
    
    Payload esperado contém:
    - sender: número do remetente
    - message: conteúdo da mensagem
    - messageType: tipo (text, document, etc)
    """
    pass
```

### Enviar mensagem de texto

```python
def enviar_mensagem(telefone: str, texto: str):
    """
    Envia mensagem de texto via Evolution API
    
    POST {EVOLUTION_URL}/message/sendText/{INSTANCE}
    Headers: apikey
    Body: {"number": telefone, "text": texto}
    """
    pass
```

### Enviar PDF

```python
def enviar_pdf(telefone: str, pdf_bytes: bytes, filename: str):
    """
    Envia documento PDF via Evolution API
    
    POST {EVOLUTION_URL}/message/sendMedia/{INSTANCE}
    Headers: apikey
    Body: {
        "number": telefone,
        "mediatype": "document",
        "media": base64_do_pdf,
        "fileName": filename
    }
    """
    pass
```

## Mercado Pago (Pix)

### Gerar cobrança Pix

```python
def gerar_pix(usuario_id: int, telefone: str, valor: float = 14.90) -> dict:
    """
    Gera QR Code Pix via Mercado Pago
    
    Usar SDK mercadopago ou API REST direta
    
    Retorna:
    {
        "qr_code": str (código copia e cola),
        "qr_code_base64": str (imagem do QR),
        "id_transacao": str
    }
    """
    pass
```

### Webhook de confirmação

```python
@app.post("/webhook/mercadopago")
async def webhook_mercadopago(request: Request):
    """
    Recebe confirmação de pagamento do Mercado Pago
    
    - Verificar assinatura do webhook
    - Atualizar status do pagamento
    - Atualizar data_expiracao do usuário (+30 dias)
    - Enviar mensagem de confirmação no WhatsApp
    """
    pass
```

## Lógica Principal de Mensagens

```python
async def processar_mensagem(telefone: str, texto: str):
    """
    Fluxo principal:
    
    1. Buscar usuário pelo telefone
       - Se não existe: cadastrar com 7 dias grátis, enviar boas-vindas
    
    2. Verificar se assinatura está ativa
       - Se expirada: gerar Pix e enviar cobrança
    
    3. Processar comando/chave:
       - Se texto == "status": mostrar dias restantes
       - Se texto == "ajuda": mostrar instruções
       - Se texto parece chave (só números):
           - Validar estrutura localmente
           - Se inválida: "Chave incorreta, confere os 44 números"
           - Se válida: consultar API
               - Sucesso: enviar PDF
               - Erro: "Chave parece correta, mas nota não está 
                       disponível ainda. Tenta em 5-10 minutos"
       - Qualquer outra coisa: mostrar instruções
    """
    pass
```

## Mensagens do Bot

```python
MENSAGENS = {
    "boas_vindas": """
🚛 *Bot DANFE* - Bem-vindo!

Aqui você consulta o DANFE da nota fiscal rapidinho.

*Como usar:*
Manda a chave de 44 números da nota e eu te devolvo o PDF.

Você ganhou *7 dias grátis* pra testar!

Manda a primeira chave aí 👇
""",

    "instrucoes": """
📋 *Como usar o Bot DANFE:*

1️⃣ Manda a chave de 44 números da nota fiscal
2️⃣ Recebe o PDF do DANFE em segundos

*Comandos:*
- Digite *status* pra ver sua assinatura
- Digite *ajuda* pra ver essa mensagem

Dúvidas? Fala com a gente: (XX) XXXXX-XXXX
""",

    "chave_invalida": """
❌ Chave inválida

Confere se digitou os 44 números certinho, sem espaços ou letras.

Exemplo de chave:
35250112345678000199550010001234561123456789
""",

    "nota_nao_disponivel": """
⏳ Chave tá certa, mas a nota ainda não apareceu no sistema.

Isso acontece quando a nota acabou de ser emitida.

Tenta de novo em 5-10 minutos!
""",

    "assinatura_vencida": """
⚠️ Sua assinatura venceu!

Pra continuar usando, renova por apenas *R$ 14,90/mês*

Paga o Pix abaixo e já libera na hora 👇
""",

    "pagamento_confirmado": """
✅ Pagamento confirmado!

Sua assinatura tá ativa por mais 30 dias.

Pode mandar a chave da nota aí!
""",

    "status": """
📊 *Sua assinatura:*

Status: {status}
Válida até: {data_expiracao}
Consultas realizadas: {total_consultas}
""",

    "erro_api": """
😕 Deu um erro na consulta. Tenta de novo em alguns segundos.

Se continuar dando erro, manda mensagem pra gente.
""",

    "sucesso": """
✅ DANFE encontrado!

Tá aí o PDF 👆
"""
}
```

## Variáveis de Ambiente (.env.example)

```env
# Banco de dados
DATABASE_URL=postgresql://user:pass@localhost:5432/bot_danfe

# Evolution API
EVOLUTION_URL=http://localhost:8080
EVOLUTION_APIKEY=sua_api_key
EVOLUTION_INSTANCE=sua_instancia

# Mercado Pago
MERCADOPAGO_ACCESS_TOKEN=seu_token
MERCADOPAGO_WEBHOOK_SECRET=seu_secret

# App
VALOR_ASSINATURA=14.90
DIAS_TRIAL=7
DIAS_ASSINATURA=30
```

## Docker Compose

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: botdanfe
      POSTGRES_PASSWORD: senha_segura
      POSTGRES_DB: bot_danfe
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://botdanfe:senha_segura@postgres:5432/bot_danfe
    depends_on:
      - postgres
    volumes:
      - .:/app

volumes:
  postgres_data:
```

## Requisitos (requirements.txt)

```
fastapi==0.109.0
uvicorn==0.27.0
sqlalchemy==2.0.25
psycopg2-binary==2.9.9
python-dotenv==1.0.0
httpx==0.26.0
mercadopago==2.2.1
pydantic==2.5.3
python-multipart==0.0.6
```

## Observações Importantes

- Usar async/await para operações de I/O
- Implementar retry com backoff para chamadas de API externas
- Validar todos os inputs
- Não expor informações sensíveis em mensagens de erro
- Código limpo, comentado e organizado
