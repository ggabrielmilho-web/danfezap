"""
Serviço de consulta de DANFE
Integração com API https://consultadanfe.com
"""
import httpx
import base64
from typing import Optional
import asyncio


class DanfeService:
    """
    Serviço para consultar DANFE via API externa
    """

    def __init__(self):
        self.api_url = "https://consultadanfe.com/CDanfe/api_generate"
        self.timeout = 30.0  # 30 segundos de timeout

    async def consultar_danfe(self, chave: str) -> dict:
        """
        Consulta DANFE na API externa

        Args:
            chave: Chave de acesso da NFe (44 dígitos)

        Returns:
            dict: {
                "sucesso": True/False,
                "pdf_bytes": bytes ou None,
                "filename": str ou None,
                "erro": str ou None
            }
        """
        try:
            # Preparar payload para a API
            # A API pode aceitar apenas a chave ou um XML mínimo
            payload = {
                "chave": chave
            }

            # Fazer requisição POST para a API
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.api_url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    }
                )

                # Verificar status da resposta
                if response.status_code != 200:
                    return {
                        "sucesso": False,
                        "pdf_bytes": None,
                        "filename": None,
                        "erro": f"API retornou status {response.status_code}"
                    }

                # Processar resposta JSON
                data = response.json()

                # Verificar se a API retornou sucesso
                if not data.get("success", False) and not data.get("pdf"):
                    erro_msg = data.get("message", "Nota fiscal não encontrada")
                    return {
                        "sucesso": False,
                        "pdf_bytes": None,
                        "filename": None,
                        "erro": erro_msg
                    }

                # Extrair PDF em base64
                pdf_base64 = data.get("pdf") or data.get("data")

                if not pdf_base64:
                    return {
                        "sucesso": False,
                        "pdf_bytes": None,
                        "filename": None,
                        "erro": "API não retornou o PDF"
                    }

                # Decodificar base64 para bytes
                try:
                    pdf_bytes = base64.b64decode(pdf_base64)
                except Exception as e:
                    return {
                        "sucesso": False,
                        "pdf_bytes": None,
                        "filename": None,
                        "erro": f"Erro ao decodificar PDF: {str(e)}"
                    }

                # Gerar nome do arquivo
                filename = f"DANFE_{chave}.pdf"

                return {
                    "sucesso": True,
                    "pdf_bytes": pdf_bytes,
                    "filename": filename,
                    "erro": None
                }

        except httpx.TimeoutException:
            return {
                "sucesso": False,
                "pdf_bytes": None,
                "filename": None,
                "erro": "Timeout na consulta da API (mais de 30 segundos)"
            }

        except httpx.ConnectError:
            return {
                "sucesso": False,
                "pdf_bytes": None,
                "filename": None,
                "erro": "Erro de conexão com a API"
            }

        except Exception as e:
            return {
                "sucesso": False,
                "pdf_bytes": None,
                "filename": None,
                "erro": f"Erro inesperado: {str(e)}"
            }

    async def consultar_com_retry(self, chave: str, max_tentativas: int = 3) -> dict:
        """
        Consulta DANFE com retry automático em caso de falha

        Args:
            chave: Chave de acesso da NFe (44 dígitos)
            max_tentativas: Número máximo de tentativas (padrão: 3)

        Returns:
            dict: Mesmo formato de consultar_danfe() com campo adicional "tentativas"
        """
        ultima_resposta = None

        for tentativa in range(1, max_tentativas + 1):
            resultado = await self.consultar_danfe(chave)

            # Se teve sucesso, retorna imediatamente
            if resultado["sucesso"]:
                resultado["tentativas"] = tentativa
                return resultado

            # Salvar última resposta
            ultima_resposta = resultado

            # Se não foi a última tentativa, aguarda antes de tentar novamente
            if tentativa < max_tentativas:
                # Backoff exponencial: 2s, 4s, 8s...
                await asyncio.sleep(2 ** tentativa)

        # Retornar última tentativa com número de tentativas
        if ultima_resposta:
            ultima_resposta["tentativas"] = max_tentativas

        return ultima_resposta


# Instância global do serviço
danfe_service = DanfeService()
