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
        self.uazapi_token = config.UAZAPI_TOKEN
        self.google_vision_url = "https://vision.googleapis.com/v1/images:annotate"

    async def baixar_imagem_uazapi(self, message_data: dict) -> Optional[bytes]:
        """
        Obtém bytes da imagem do webhook da UazAPI.

        Tenta em ordem:
        1. Download da URL em message.content.URL
        2. Thumbnail em base64 de message.content.JPEGThumbnail (fallback)
        """
        try:
            content = message_data.get("content", {})
            if not isinstance(content, dict):
                logger.error("Campo content inválido ou ausente")
                return None

            # 1. Tenta download da URL completa e valida se é imagem real
            file_url = content.get("URL", "")
            if file_url:
                logger.info(f"Baixando imagem de: {file_url}")
                headers = {"token": self.uazapi_token}
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(file_url, headers=headers)
                    if response.status_code == 200:
                        candidate = response.content
                        try:
                            from PIL import Image as PILImage
                            PILImage.open(BytesIO(candidate)).verify()
                            logger.info(f"Imagem baixada e válida: {len(candidate)} bytes")
                            return candidate
                        except Exception:
                            logger.warning("Arquivo baixado é criptografado (.enc), usando thumbnail")
                    else:
                        logger.warning(f"Falha ao baixar URL ({response.status_code}), usando thumbnail")

            # 2. Fallback: thumbnail em base64 já disponível no webhook
            thumbnail_b64 = content.get("JPEGThumbnail", "")
            if thumbnail_b64:
                logger.info("Usando JPEGThumbnail do webhook como fallback")
                image_bytes = base64.b64decode(thumbnail_b64)
                logger.info(f"Thumbnail decodificado: {len(image_bytes)} bytes")
                return image_bytes

            logger.error("Nenhuma fonte de imagem disponível no payload")
            return None

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

    async def processar_imagem(self, message_data: dict) -> dict:
        """
        Fluxo principal de processamento de imagem

        1. Baixa imagem via content.URL ou thumbnail do webhook
        2. Tenta pyzbar (código de barras/QR) - GRÁTIS
        3. Se falhar, tenta Google Vision OCR - Pago
        4. Se falhar, retorna erro

        Args:
            message_data: Objeto message do webhook da UazAPI

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

            image_bytes = await self.baixar_imagem_uazapi(message_data)

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
