"""
Serviço de OTP (one-time password) via WhatsApp para login no painel.

Fluxo:
1. gerar_otp(telefone) → cria código 6 dígitos, salva com TTL, dispara via WhatsApp.
2. validar_otp(telefone, codigo) → confere, marca used=True, retorna telefone normalizado.

Rate limit: max OTP_RATE_LIMIT_MAX por telefone em OTP_RATE_LIMIT_JANELA_SEGUNDOS.
"""
import secrets
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from ..config import config
from ..models import OtpCode
from ..utils.telefone import normalizar_telefone_br
from .whatsapp import whatsapp_service

logger = logging.getLogger(__name__)


class OtpService:
    """Geração e validação de OTPs single-use com TTL curto."""

    async def gerar_otp(self, telefone: str, db: Session) -> dict:
        tel = normalizar_telefone_br(telefone)

        # Rate limit: contar OTPs criados pra esse telefone na janela
        janela_inicio = datetime.utcnow() - timedelta(seconds=config.OTP_RATE_LIMIT_JANELA_SEGUNDOS)
        recentes = db.query(OtpCode).filter(
            OtpCode.telefone == tel,
            OtpCode.created_at >= janela_inicio,
        ).count()

        if recentes >= config.OTP_RATE_LIMIT_MAX:
            logger.warning(f"Rate limit OTP excedido pra {tel}: {recentes} tentativas")
            return {"sucesso": False, "erro": "limite_excedido", "telefone": tel}

        # Gera código 6 dígitos com zero-padding (000000 é válido também)
        codigo = f"{secrets.randbelow(1_000_000):06d}"

        otp = OtpCode(
            telefone=tel,
            codigo=codigo,
            expires_at=datetime.utcnow() + timedelta(seconds=config.OTP_TTL_SEGUNDOS),
            used=False,
        )
        db.add(otp)
        db.commit()

        # Envia via WhatsApp (assíncrono)
        mensagem = (
            f"🔐 *DanfeZap*\n\n"
            f"Seu código de acesso: *{codigo}*\n\n"
            f"Válido por 5 minutos. Não compartilhe."
        )
        resultado = await whatsapp_service.enviar_mensagem(tel, mensagem)

        if not resultado.get("sucesso"):
            logger.error(f"Falha ao enviar OTP pra {tel}: {resultado.get('erro')}")
            return {"sucesso": False, "erro": "falha_envio_whatsapp", "telefone": tel}

        logger.info(f"OTP gerado e enviado pra {tel}")
        return {"sucesso": True, "erro": None, "telefone": tel}

    def validar_otp(self, telefone: str, codigo: str, db: Session) -> dict:
        tel = normalizar_telefone_br(telefone)
        codigo = (codigo or "").strip()

        otp = db.query(OtpCode).filter(
            OtpCode.telefone == tel,
            OtpCode.codigo == codigo,
            OtpCode.used == False,
            OtpCode.expires_at > datetime.utcnow(),
        ).order_by(OtpCode.created_at.desc()).first()

        if not otp:
            return {"valido": False, "telefone": tel}

        otp.used = True
        db.commit()
        logger.info(f"OTP validado pra {tel}")
        return {"valido": True, "telefone": tel}


otp_service = OtpService()
