"""
Serviço de integração com Evolution API (WhatsApp)
Envia mensagens de texto e documentos PDF
"""
import httpx
import base64
from typing import Optional
from ..config import config


class WhatsAppService:
    """
    Serviço para enviar mensagens via Evolution API
    """

    def __init__(self):
        self.base_url = config.EVOLUTION_URL
        self.apikey = config.EVOLUTION_APIKEY
        self.instance = config.EVOLUTION_INSTANCE
        self.timeout = 30.0

    def _get_headers(self) -> dict:
        """Retorna headers padrão para requisições"""
        return {
            "Content-Type": "application/json",
            "apikey": self.apikey
        }

    def _formatar_numero(self, telefone: str) -> str:
        """
        Formata número de telefone para o padrão do WhatsApp
        Remove caracteres especiais e garante formato correto

        Args:
            telefone: Número de telefone (pode conter máscara)

        Returns:
            str: Número formatado (ex: 5511999999999)
        """
        # Remover todos os caracteres não numéricos
        numero = ''.join(filter(str.isdigit, telefone))

        # Se não começa com 55 (código do Brasil), adiciona
        if not numero.startswith('55'):
            numero = '55' + numero

        # Adicionar @s.whatsapp.net no final
        return f"{numero}@s.whatsapp.net"

    async def enviar_mensagem(self, telefone: str, texto: str) -> dict:
        """
        Envia mensagem de texto via Evolution API

        Args:
            telefone: Número de telefone do destinatário
            texto: Texto da mensagem

        Returns:
            dict: {
                "sucesso": True/False,
                "erro": str ou None
            }
        """
        try:
            # Formatar número
            numero_formatado = self._formatar_numero(telefone)

            # Endpoint de envio de texto
            url = f"{self.base_url}/message/sendText/{self.instance}"

            # Payload
            payload = {
                "number": numero_formatado,
                "text": texto
            }

            # Fazer requisição
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self._get_headers()
                )

                if response.status_code == 200 or response.status_code == 201:
                    return {
                        "sucesso": True,
                        "erro": None
                    }
                else:
                    return {
                        "sucesso": False,
                        "erro": f"API retornou status {response.status_code}: {response.text}"
                    }

        except httpx.TimeoutException:
            return {
                "sucesso": False,
                "erro": "Timeout ao enviar mensagem"
            }

        except Exception as e:
            return {
                "sucesso": False,
                "erro": f"Erro ao enviar mensagem: {str(e)}"
            }

    async def enviar_pdf(self, telefone: str, pdf_bytes: bytes, filename: str, caption: Optional[str] = None) -> dict:
        """
        Envia documento PDF via Evolution API

        Args:
            telefone: Número de telefone do destinatário
            pdf_bytes: Bytes do arquivo PDF
            filename: Nome do arquivo (ex: DANFE_12345.pdf)
            caption: Legenda opcional para o documento

        Returns:
            dict: {
                "sucesso": True/False,
                "erro": str ou None
            }
        """
        try:
            # Formatar número
            numero_formatado = self._formatar_numero(telefone)

            # Converter PDF para base64
            pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')

            # Endpoint de envio de mídia
            url = f"{self.base_url}/message/sendMedia/{self.instance}"

            # Payload
            payload = {
                "number": numero_formatado,
                "mediatype": "document",
                "media": pdf_base64,
                "fileName": filename
            }

            # Adicionar caption se fornecido
            if caption:
                payload["caption"] = caption

            # Fazer requisição
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self._get_headers()
                )

                if response.status_code == 200 or response.status_code == 201:
                    return {
                        "sucesso": True,
                        "erro": None
                    }
                else:
                    return {
                        "sucesso": False,
                        "erro": f"API retornou status {response.status_code}: {response.text}"
                    }

        except httpx.TimeoutException:
            return {
                "sucesso": False,
                "erro": "Timeout ao enviar PDF"
            }

        except Exception as e:
            return {
                "sucesso": False,
                "erro": f"Erro ao enviar PDF: {str(e)}"
            }

    async def enviar_imagem(self, telefone: str, imagem_bytes: bytes, caption: Optional[str] = None) -> dict:
        """
        Envia imagem (ex: QR Code do Pix) via Evolution API

        Args:
            telefone: Número de telefone do destinatário
            imagem_bytes: Bytes da imagem
            caption: Legenda opcional para a imagem

        Returns:
            dict: {
                "sucesso": True/False,
                "erro": str ou None
            }
        """
        try:
            # Formatar número
            numero_formatado = self._formatar_numero(telefone)

            # Converter imagem para base64
            imagem_base64 = base64.b64encode(imagem_bytes).decode('utf-8')

            # Endpoint de envio de mídia
            url = f"{self.base_url}/message/sendMedia/{self.instance}"

            # Payload
            payload = {
                "number": numero_formatado,
                "mediatype": "image",
                "media": imagem_base64
            }

            # Adicionar caption se fornecido
            if caption:
                payload["caption"] = caption

            # Fazer requisição
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self._get_headers()
                )

                if response.status_code == 200 or response.status_code == 201:
                    return {
                        "sucesso": True,
                        "erro": None
                    }
                else:
                    return {
                        "sucesso": False,
                        "erro": f"API retornou status {response.status_code}: {response.text}"
                    }

        except httpx.TimeoutException:
            return {
                "sucesso": False,
                "erro": "Timeout ao enviar imagem"
            }

        except Exception as e:
            return {
                "sucesso": False,
                "erro": f"Erro ao enviar imagem: {str(e)}"
            }


# Instância global do serviço
whatsapp_service = WhatsAppService()
