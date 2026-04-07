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

    # UazAPI (WhatsApp)
    UAZAPI_URL = os.getenv("UAZAPI_URL", "https://free.uazapi.com")
    UAZAPI_TOKEN = os.getenv("UAZAP_TOKEN", "")

    # URL base para webhooks (onde nossa aplicação recebe callbacks)
    WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL", "http://localhost:8000")

    # Mercado Pago
    MERCADOPAGO_ACCESS_TOKEN = os.getenv("MERCADOPAGO_ACCESS_TOKEN", "")
    MERCADOPAGO_WEBHOOK_SECRET = os.getenv("MERCADOPAGO_WEBHOOK_SECRET", "")

    # MeuDanfe API
    MEUDANFE_API_KEY = os.getenv("API_KEY", "")

    # Google Vision API
    GOOGLE_VISION_API_KEY = os.getenv("GOOGLE_VISION_API_KEY", "")

    # Resend API (envio de emails)
    RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")

    # Admin (kill switch)
    ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")

    # Configurações da aplicação
    VALOR_ASSINATURA = float(os.getenv("VALOR_ASSINATURA", "14.90"))  # retrocompatibilidade → aponta para plano básico
    DIAS_TRIAL = int(os.getenv("DIAS_TRIAL", "7"))  # Mantido para compatibilidade
    DIAS_ASSINATURA = int(os.getenv("DIAS_ASSINATURA", "30"))

    # Novas configurações - sistema de consultas
    CONSULTAS_GRATIS = int(os.getenv("CONSULTAS_GRATIS", "2"))
    LIMITE_CONSULTAS_MES = int(os.getenv("LIMITE_CONSULTAS_MES", "100"))

    # Planos de assinatura
    VALOR_PLANO_BASICO  = float(os.getenv("VALOR_PLANO_BASICO", "14.90"))
    VALOR_PLANO_PRO     = float(os.getenv("VALOR_PLANO_PRO", "49.00"))
    LIMITE_PLANO_BASICO = int(os.getenv("LIMITE_PLANO_BASICO", "100"))
    LIMITE_PLANO_PRO    = int(os.getenv("LIMITE_PLANO_PRO", "1000"))

    @classmethod
    def validar_config(cls):
        """Valida se as configurações essenciais estão definidas"""
        erros = []

        if not cls.UAZAPI_TOKEN:
            erros.append("UAZAP_TOKEN não configurada")

        if not cls.MERCADOPAGO_ACCESS_TOKEN:
            erros.append("MERCADOPAGO_ACCESS_TOKEN não configurada")

        if erros:
            raise ValueError(f"Configurações faltando: {', '.join(erros)}")

        return True


# Instância global de configuração
config = Config()
