"""
Serviço de integração com UazAPI (WhatsApp)
Envia mensagens de texto, documentos PDF e imagens
"""
import httpx
import base64
import logging
from typing import Optional
from ..config import config

logger = logging.getLogger(__name__)


class WhatsAppService:
    """
    Serviço para enviar mensagens via UazAPI
    """

    def __init__(self):
        self.base_url = config.UAZAPI_URL
        self.token = config.UAZAPI_TOKEN
        self.timeout = 30.0

    def _get_headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "token": self.token
        }

    def _formatar_numero(self, telefone: str) -> str:
        """Retorna número apenas com dígitos + código do Brasil"""
        numero = ''.join(filter(str.isdigit, telefone))
        if not numero.startswith('55'):
            numero = '55' + numero
        return numero

    async def enviar_mensagem(self, telefone: str, texto: str) -> dict:
        try:
            url = f"{self.base_url}/send/text"
            payload = {
                "number": self._formatar_numero(telefone),
                "text": texto
            }

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=self._get_headers())

            if response.status_code in (200, 201):
                return {"sucesso": True, "erro": None}
            else:
                logger.error(f"Erro enviar_mensagem: {response.status_code} - {response.text}")
                return {"sucesso": False, "erro": f"Status {response.status_code}: {response.text}"}

        except httpx.TimeoutException:
            return {"sucesso": False, "erro": "Timeout ao enviar mensagem"}
        except Exception as e:
            return {"sucesso": False, "erro": str(e)}

    async def enviar_pdf(self, telefone: str, pdf_bytes: bytes, filename: str, caption: Optional[str] = None) -> dict:
        try:
            url = f"{self.base_url}/send/media"
            payload = {
                "number": self._formatar_numero(telefone),
                "type": "document",
                "file": base64.b64encode(pdf_bytes).decode('utf-8'),
                "docName": filename
            }
            if caption:
                payload["text"] = caption

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=self._get_headers())

            if response.status_code in (200, 201):
                return {"sucesso": True, "erro": None}
            else:
                logger.error(f"Erro enviar_pdf: {response.status_code} - {response.text}")
                return {"sucesso": False, "erro": f"Status {response.status_code}: {response.text}"}

        except httpx.TimeoutException:
            return {"sucesso": False, "erro": "Timeout ao enviar PDF"}
        except Exception as e:
            return {"sucesso": False, "erro": str(e)}

    async def enviar_xml(self, telefone: str, xml_bytes: bytes, filename: str, caption: Optional[str] = None) -> dict:
        try:
            url = f"{self.base_url}/send/media"
            payload = {
                "number": self._formatar_numero(telefone),
                "type": "document",
                "file": base64.b64encode(xml_bytes).decode('utf-8'),
                "docName": filename
            }
            if caption:
                payload["text"] = caption

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=self._get_headers())

            if response.status_code in (200, 201):
                return {"sucesso": True, "erro": None}
            else:
                logger.error(f"Erro enviar_xml: {response.status_code} - {response.text}")
                return {"sucesso": False, "erro": f"Status {response.status_code}: {response.text}"}

        except httpx.TimeoutException:
            return {"sucesso": False, "erro": "Timeout ao enviar XML"}
        except Exception as e:
            return {"sucesso": False, "erro": str(e)}

    async def enviar_imagem(self, telefone: str, imagem_bytes: bytes, caption: Optional[str] = None) -> dict:
        try:
            url = f"{self.base_url}/send/media"
            payload = {
                "number": self._formatar_numero(telefone),
                "type": "image",
                "file": base64.b64encode(imagem_bytes).decode('utf-8')
            }
            if caption:
                payload["text"] = caption

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=self._get_headers())

            if response.status_code in (200, 201):
                return {"sucesso": True, "erro": None}
            else:
                logger.error(f"Erro enviar_imagem: {response.status_code} - {response.text}")
                return {"sucesso": False, "erro": f"Status {response.status_code}: {response.text}"}

        except httpx.TimeoutException:
            return {"sucesso": False, "erro": "Timeout ao enviar imagem"}
        except Exception as e:
            return {"sucesso": False, "erro": str(e)}


# Instância global do serviço
whatsapp_service = WhatsAppService()
