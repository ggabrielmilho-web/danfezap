"""
Configurações do Bot DANFE WhatsApp
Carrega variáveis de ambiente e centraliza configurações
"""
from dotenv import load_dotenv
import os

# Carregar variáveis do arquivo .env
load_dotenv()


class Config:
    """Classe de configuração centralizada"""

    # Banco de dados
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://botdanfe:senha_segura@localhost:5432/danfezap")

    # Evolution API (WhatsApp)
    EVOLUTION_URL = os.getenv("EVOLUTION_URL", "http://localhost:8080")
    EVOLUTION_APIKEY = os.getenv("EVOLUTION_APIKEY", "")
    EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE", "")

    # Mercado Pago
    MERCADOPAGO_ACCESS_TOKEN = os.getenv("MERCADOPAGO_ACCESS_TOKEN", "")
    MERCADOPAGO_WEBHOOK_SECRET = os.getenv("MERCADOPAGO_WEBHOOK_SECRET", "")

    # Configurações da aplicação
    VALOR_ASSINATURA = float(os.getenv("VALOR_ASSINATURA", "14.90"))
    DIAS_TRIAL = int(os.getenv("DIAS_TRIAL", "7"))
    DIAS_ASSINATURA = int(os.getenv("DIAS_ASSINATURA", "30"))

    @classmethod
    def validar_config(cls):
        """Valida se as configurações essenciais estão definidas"""
        erros = []

        if not cls.EVOLUTION_APIKEY:
            erros.append("EVOLUTION_APIKEY não configurada")

        if not cls.EVOLUTION_INSTANCE:
            erros.append("EVOLUTION_INSTANCE não configurada")

        if not cls.MERCADOPAGO_ACCESS_TOKEN:
            erros.append("MERCADOPAGO_ACCESS_TOKEN não configurada")

        if erros:
            raise ValueError(f"Configurações faltando: {', '.join(erros)}")

        return True


# Instância global de configuração
config = Config()
