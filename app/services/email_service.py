"""
Serviço de envio de emails usando Resend API
Envia PDF e XML do DANFE por email para usuários cadastrados
"""
import resend
import base64
import logging
from typing import List, Optional
from app.config import config

logger = logging.getLogger(__name__)

# Configurar API Key do Resend
resend.api_key = config.RESEND_API_KEY


async def enviar_email_danfe(
    emails: List[str],
    chave_nfe: str,
    pdf_bytes: bytes,
    xml_bytes: Optional[bytes] = None
) -> dict:
    """
    Envia PDF e XML do DANFE por email usando Resend

    Args:
        emails: Lista de emails destinatários
        chave_nfe: Chave de 44 dígitos da NFe
        pdf_bytes: Bytes do PDF do DANFE
        xml_bytes: Bytes do XML (opcional)

    Returns:
        dict: {"sucesso": bool, "erro": str or None}
    """
    try:
        if not resend.api_key:
            logger.error("RESEND_API_KEY não configurada")
            return {"sucesso": False, "erro": "API Key não configurada"}

        logger.info(f"Enviando email para {len(emails)} destinatário(s)")

        # Converter bytes para base64 (requerido pela Resend API)
        pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')

        # Preparar anexos
        attachments = [
            {
                "filename": f"DANFE_{chave_nfe[-10:]}.pdf",
                "content": pdf_base64
            }
        ]

        # Adicionar XML se disponível
        if xml_bytes:
            xml_base64 = base64.b64encode(xml_bytes).decode('utf-8')
            attachments.append({
                "filename": f"XML_{chave_nfe[-10:]}.xml",
                "content": xml_base64
            })

        # Enviar email via Resend
        r = resend.Emails.send({
            "from": "DanfeZap <gabriel@carvalhoia.com>",
            "to": emails,
            "subject": f"DANFE - Chave: ...{chave_nfe[-10:]}",
            "html": f"""
                <h2>🚛 DanfeZap</h2>
                <p>Segue o DANFE e XML da nota fiscal.</p>
                <p><strong>Chave NFe:</strong> {chave_nfe}</p>
                <br>
                <p>Obrigado por usar o DanfeZap!</p>
                <p style="color: #666; font-size: 12px;">
                    Este email foi enviado automaticamente. Não responda.
                </p>
            """,
            "attachments": attachments
        })

        logger.info(f"Email enviado com sucesso: {r}")
        return {"sucesso": True, "erro": None}

    except Exception as e:
        logger.error(f"Erro ao enviar email: {e}")
        return {"sucesso": False, "erro": str(e)}


class EmailService:
    """Serviço para gerenciar envio de emails"""

    async def enviar_danfe(
        self,
        emails: List[str],
        chave_nfe: str,
        pdf_bytes: bytes,
        xml_bytes: Optional[bytes] = None
    ):
        """
        Wrapper para enviar_email_danfe

        Args:
            emails: Lista de emails destinatários
            chave_nfe: Chave de 44 dígitos da NFe
            pdf_bytes: Bytes do PDF do DANFE
            xml_bytes: Bytes do XML (opcional)

        Returns:
            dict: {"sucesso": bool, "erro": str or None}
        """
        return await enviar_email_danfe(emails, chave_nfe, pdf_bytes, xml_bytes)


# Instância global do serviço
email_service = EmailService()
