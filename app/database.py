"""
Configuração do banco de dados PostgreSQL
Gerencia conexão e sessões usando SQLAlchemy
"""
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import config

# Criar engine de conexão com o PostgreSQL
engine = create_engine(
    config.DATABASE_URL,
    pool_pre_ping=True,  # Verifica conexão antes de usar
    echo=False  # Mudar para True para debug SQL
)

# Configurar sessão local
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base declarativa para os models
Base = declarative_base()


def get_db():
    """
    Dependency injection para FastAPI
    Cria uma sessão de banco de dados e fecha após uso

    Uso:
        @app.get("/endpoint")
        def endpoint(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Inicializa o banco de dados criando todas as tabelas
    Importa os models e cria as tabelas se não existirem
    """
    from . import models
    Base.metadata.create_all(bind=engine)


def migrate_db():
    """
    Aplica migrações incrementais de forma idempotente.
    Usa ADD COLUMN IF NOT EXISTS para não quebrar banco existente.
    """
    migrations = [
        # === Migrações pré-Fase 1 (mantidas) ===
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS plano VARCHAR(10)",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS aguardando_escolha_plano BOOLEAN DEFAULT FALSE",
        "ALTER TABLE pagamentos ADD COLUMN IF NOT EXISTS plano VARCHAR(10)",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS followup_1_enviado BOOLEAN DEFAULT FALSE",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS followup_2_enviado BOOLEAN DEFAULT FALSE",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS followup_3_enviado BOOLEAN DEFAULT FALSE",

        # === Fase 1 — Painel/Landing/Escritório (consolidado) ===
        # usuarios: tipo de conta + hierarquia escritorio
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS tipo VARCHAR(30) DEFAULT 'normal'",
        "CREATE INDEX IF NOT EXISTS idx_usuarios_tipo ON usuarios(tipo)",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS master_id INTEGER REFERENCES usuarios(id)",
        "CREATE INDEX IF NOT EXISTS idx_usuarios_master_id ON usuarios(master_id)",

        # usuarios: integração Google Drive (Fase 4 usa, schema agora)
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS link_drive VARCHAR(500)",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS drive_folder_id VARCHAR(100)",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS drive_ativo BOOLEAN DEFAULT FALSE",

        # usuarios: nome de exibição (cliente cadastrado pelo contador)
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS nome_exibicao VARCHAR(100)",

        # usuarios: preapproval Mercado Pago (Fase 5)
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS mp_preapproval_id VARCHAR(100)",

        # Expandir plano pra aceitar 'escritorio'
        "ALTER TABLE usuarios ALTER COLUMN plano TYPE VARCHAR(20)",
        "ALTER TABLE pagamentos ALTER COLUMN plano TYPE VARCHAR(20)",

        # consultas: rastreio do dono master (escritorio)
        "ALTER TABLE consultas ADD COLUMN IF NOT EXISTS master_id INTEGER REFERENCES usuarios(id)",
        "CREATE INDEX IF NOT EXISTS idx_consultas_master_id ON consultas(master_id)",
        "ALTER TABLE consultas ADD COLUMN IF NOT EXISTS drive_sync BOOLEAN DEFAULT FALSE",

        # Tabela nova: OTPs do painel
        """
        CREATE TABLE IF NOT EXISTS otp_codes (
            id SERIAL PRIMARY KEY,
            telefone VARCHAR(20) NOT NULL,
            codigo VARCHAR(6) NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            used BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_otp_telefone ON otp_codes(telefone)",
        "CREATE INDEX IF NOT EXISTS idx_otp_created_at ON otp_codes(created_at)",
    ]

    with engine.connect() as conn:
        for stmt in migrations:
            conn.execute(text(stmt))
        conn.commit()
