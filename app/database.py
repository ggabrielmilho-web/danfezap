"""
Configuração do banco de dados PostgreSQL
Gerencia conexão e sessões usando SQLAlchemy
"""
from sqlalchemy import create_engine
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
