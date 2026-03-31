"""
Serviço de processamento de imagens para extrair chaves NFe
Usa pyzbar (grátis) como primeira opção e Google Vision OCR como fallback
"""
import re
import base64
import logging
from typing import Optional
import httpx
from PIL import Image
from io import BytesIO
from pyzbar import pyzbar
from app.config import config
from app.services.validador import validar_chave_nfe

logger = logging.getLogger(__name__)


class ImageReaderService:
    """
    Serviço para processar imagens e extrair chaves NFe automaticamente

    Estratégia:
    1. Tenta pyzbar (código de barras/QR Code) - GRÁTIS
    2. Se falhar, tenta Google Vision OCR - Pago ($1.50/1000 req)
    3. Valida chave extraída com validar_chave_nfe()
    """

    def __init__(self):
        self.google_api_key = config.GOOGLE_VISION_API_KEY
        self.evolution_url = config.EVOLUTION_URL
        self.evolution_apikey = config.EVOLUTION_APIKEY
        self.google_vision_url = "https://vision.googleapis.com/v1/images:annotate"

    def _get_headers(self):
        """Headers para Evolution API"""
        return {
            "apikey": self.evolution_apikey,
            "Content-Type": "application/json"
        }

    async def baixar_imagem_whatsapp(self, data: dict) -> Optional[bytes]:
        """
        Obtém bytes da imagem do webhook da Evolution API

        Tenta em ordem:
        1. base64 direto no webhook (imageMessage.base64 ou message.base64)
        2. Evolution API getBase64FromMediaMessage (descriptografa a mídia)

        Args:
            data: Objeto data completo do webhook da Evolution API

        Returns:
            bytes da imagem ou None se falhar
        """
        try:
            message = data.get("message", {})
            image_message = message.get("imageMessage", {})

            # 1. Tenta base64 direto no webhook
            base64_data = image_message.get("base64") or message.get("base64") or data.get("base64")

            if base64_data:
                logger.info("Imagem recebida em base64 do webhook")
                image_bytes = base64.b64decode(base64_data)
                logger.info(f"Imagem decodificada: {len(image_bytes)} bytes")
                return image_bytes

            # 2. Chama Evolution API para descriptografar a mídia
            logger.info("base64 não encontrado no webhook, buscando via Evolution API")
            key = data.get("key", {})
            instance = config.EVOLUTION_INSTANCE

            url = f"{self.evolution_url}/chat/getBase64FromMediaMessage/{instance}"
            payload = {
                "message": {
                    "key": key,
                    "message": message
                },
                "convertToMp4": False
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=self._get_headers())

                if response.status_code not in (200, 201):
                    logger.error(f"Evolution API erro ao buscar mídia: Status {response.status_code} - {response.text}")
                    return None

                result = response.json()
                base64_data = result.get("base64")

                if not base64_data:
                    logger.error(f"Evolution API não retornou base64. Resposta: {result}")
                    return None

                logger.info("Imagem obtida via Evolution API getBase64FromMediaMessage")
                image_bytes = base64.b64decode(base64_data)
                logger.info(f"Imagem decodificada: {len(image_bytes)} bytes")
                return image_bytes

        except Exception as e:
            logger.error(f"Erro ao obter imagem: {e}")
            return None

    def extrair_chave_pyzbar(self, image_bytes: bytes) -> Optional[str]:
        """
        Tenta ler código de barras/QR Code com pyzbar (GRÁTIS)

        Suporta vários formatos: EAN, CODE128, QR_CODE, etc.

        Args:
            image_bytes: Bytes da imagem

        Returns:
            Chave de 44 dígitos ou None se não encontrar
        """
        try:
            logger.info("Tentando extrair chave com pyzbar (código de barras/QR)")

            # Converter bytes para imagem PIL
            image = Image.open(BytesIO(image_bytes))

            # Detectar códigos na imagem
            decoded_objects = pyzbar.decode(image)

            if not decoded_objects:
                logger.info("pyzbar: Nenhum código de barras/QR detectado")
                return None

            logger.info(f"pyzbar: {len(decoded_objects)} código(s) detectado(s)")

            # Processar cada código detectado
            for obj in decoded_objects:
                data = obj.data.decode('utf-8')
                logger.debug(f"pyzbar: Código detectado: {data[:50]}...")

                # Buscar 44 dígitos consecutivos
                chave = self._extrair_44_digitos(data)

                if chave:
                    # Validar chave
                    validacao = validar_chave_nfe(chave)
                    if validacao["valida"]:
                        logger.info(f"pyzbar: Chave válida encontrada: {chave}")
                        return chave
                    else:
                        logger.debug(f"pyzbar: Chave inválida: {validacao['erro']}")

            logger.info("pyzbar: Nenhuma chave válida encontrada nos códigos")
            return None

        except Exception as e:
            logger.error(f"Erro no pyzbar: {e}")
            return None

    async def extrair_chave_google_vision(self, image_bytes: bytes) -> Optional[str]:
        """
        OCR com Google Vision API (FALLBACK)

        Usa API REST: https://vision.googleapis.com/v1/images:annotate

        Args:
            image_bytes: Bytes da imagem

        Returns:
            Chave de 44 dígitos ou None se não encontrar
        """
        try:
            logger.info("Tentando extrair chave com Google Vision OCR")

            if not self.google_api_key:
                logger.error("GOOGLE_VISION_API_KEY não configurada")
                return None

            # Converter imagem para base64
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')

            # Montar request para Google Vision
            url = f"{self.google_vision_url}?key={self.google_api_key}"

            payload = {
                "requests": [
                    {
                        "image": {
                            "content": image_base64
                        },
                        "features": [
                            {
                                "type": "TEXT_DETECTION",
                                "maxResults": 1
                            }
                        ]
                    }
                ]
            }

            # Fazer request
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload)

                if response.status_code != 200:
                    logger.error(f"Google Vision erro: Status {response.status_code}")
                    logger.debug(f"Resposta: {response.text}")
                    return None

                result = response.json()

                # Extrair texto detectado
                if "responses" not in result or not result["responses"]:
                    logger.info("Google Vision: Nenhum texto detectado")
                    return None

                first_response = result["responses"][0]

                if "textAnnotations" not in first_response:
                    logger.info("Google Vision: Nenhum texto detectado")
                    return None

                # Pegar texto completo (primeira anotação contém tudo)
                texto_completo = first_response["textAnnotations"][0]["description"]

                logger.debug(f"Google Vision: Texto extraído: {texto_completo[:100]}...")

                # Buscar 44 dígitos consecutivos
                chave = self._extrair_44_digitos(texto_completo)

                if chave:
                    # Validar chave
                    validacao = validar_chave_nfe(chave)
                    if validacao["valida"]:
                        logger.info(f"Google Vision: Chave válida encontrada: {chave}")
                        return chave
                    else:
                        logger.debug(f"Google Vision: Chave inválida: {validacao['erro']}")

                logger.info("Google Vision: Nenhuma chave válida encontrada no texto")
                return None

        except Exception as e:
            logger.error(f"Erro no Google Vision: {e}")
            return None

    def _extrair_44_digitos(self, texto: str) -> Optional[str]:
        """
        Busca padrão de 44 dígitos consecutivos no texto

        Args:
            texto: Texto extraído do código de barras ou OCR

        Returns:
            String com 44 dígitos ou None se não encontrar
        """
        # 1. Busca direta: 44 dígitos exatos sem adjacentes no texto original
        match = re.search(r'(?<!\d)\d{44}(?!\d)', texto)
        if match:
            return match.group(0)

        # 2. Chave formatada com espaços/hífens entre grupos (ex: "3118 0222 1649 ...")
        # Remove apenas separadores entre dígitos adjacentes, sem concatenar tudo
        texto_compacto = re.sub(r'(?<=\d)[\s\-]+(?=\d)', '', texto)
        match = re.search(r'(?<!\d)\d{44}(?!\d)', texto_compacto)
        if match:
            return match.group(0)

        return None

    async def processar_imagem(self, message: dict) -> dict:
        """
        Fluxo principal de processamento de imagem

        1. Baixa imagem da Evolution API
        2. Tenta pyzbar (código de barras/QR) - GRÁTIS
        3. Se falhar, tenta Google Vision OCR - Pago
        4. Se falhar, retorna erro

        Args:
            message: Objeto message do webhook da Evolution API

        Returns:
            dict: {
                "sucesso": True/False,
                "chave": "44 dígitos" ou None,
                "metodo": "pyzbar" ou "google_vision" ou None,
                "erro": mensagem de erro ou None
            }
        """
        try:
            # 1. Baixar imagem
            logger.info("Iniciando processamento de imagem")

            image_bytes = await self.baixar_imagem_whatsapp(message)

            if not image_bytes:
                return {
                    "sucesso": False,
                    "chave": None,
                    "metodo": None,
                    "erro": "Não foi possível baixar a imagem"
                }

            logger.info(f"Imagem baixada: {len(image_bytes)} bytes")

            # 2. Tentar pyzbar (código de barras/QR Code) - GRÁTIS
            chave = self.extrair_chave_pyzbar(image_bytes)

            if chave:
                return {
                    "sucesso": True,
                    "chave": chave,
                    "metodo": "pyzbar",
                    "erro": None
                }

            # 3. Tentar Google Vision OCR - Pago (fallback)
            chave = await self.extrair_chave_google_vision(image_bytes)

            if chave:
                return {
                    "sucesso": True,
                    "chave": chave,
                    "metodo": "google_vision",
                    "erro": None
                }

            # 4. Falhou em ambos os métodos
            return {
                "sucesso": False,
                "chave": None,
                "metodo": None,
                "erro": "Nenhuma chave NFe encontrada na imagem"
            }

        except Exception as e:
            logger.error(f"Erro ao processar imagem: {e}")
            return {
                "sucesso": False,
                "chave": None,
                "metodo": None,
                "erro": str(e)
            }


# Instância global
image_reader_service = ImageReaderService()
