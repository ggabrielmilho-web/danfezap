"""
Serviço de consulta de DANFE
Integração com API MeuDanfe (https://api.meudanfe.com.br/v2)
"""
import httpx
import base64
from typing import Optional
import asyncio
from ..config import config


class DanfeService:
    """
    Serviço para consultar DANFE via API MeuDanfe
    """

    def __init__(self):
        self.base_url = "https://api.meudanfe.com.br/v2"
        self.api_key = config.MEUDANFE_API_KEY
        self.timeout = 30.0  # 30 segundos de timeout

    def _get_headers(self) -> dict:
        """Retorna headers com API Key"""
        return {
            "Api-Key": self.api_key,
            "Content-Type": "application/json"
        }

    async def consultar_danfe(self, chave: str) -> dict:
        """
        Consulta DANFE na API MeuDanfe

        Fluxo:
        1. PUT /fd/add/{chave} - Adiciona/busca a nota (R$0,01 se nova)
        2. GET /fd/get/da/{chave} - Baixa o PDF em base64 (grátis)

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
            async with httpx.AsyncClient(timeout=self.timeout) as client:

                # PASSO 1: Adicionar/buscar a nota fiscal
                url_add = f"{self.base_url}/fd/add/{chave}"

                response_add = await client.put(
                    url_add,
                    headers=self._get_headers()
                )

                # Verificar se conseguiu buscar a nota
                if response_add.status_code != 200:
                    # Tentar pegar mensagem de erro do response
                    try:
                        error_data = response_add.json()
                        error_msg = error_data.get("message", "Nota fiscal não encontrada")
                    except:
                        error_msg = f"Nota fiscal não encontrada (status {response_add.status_code})"

                    return {
                        "sucesso": False,
                        "pdf_bytes": None,
                        "xml_bytes": None,
                        "filename": None,
                        "erro": error_msg
                    }

                # PASSO 2: Baixar o DANFE em PDF
                url_pdf = f"{self.base_url}/fd/get/da/{chave}"

                response_pdf = await client.get(
                    url_pdf,
                    headers=self._get_headers()
                )

                # Verificar se conseguiu baixar o PDF
                if response_pdf.status_code != 200:
                    return {
                        "sucesso": False,
                        "pdf_bytes": None,
                        "xml_bytes": None,
                        "filename": None,
                        "erro": "Erro ao gerar PDF do DANFE"
                    }

                # Processar resposta JSON
                data = response_pdf.json()

                # Extrair base64 do PDF (campo "data" da API MeuDanfe)
                pdf_base64 = data.get("data")

                if not pdf_base64:
                    return {
                        "sucesso": False,
                        "pdf_bytes": None,
                        "xml_bytes": None,
                        "filename": None,
                        "erro": f"API não retornou o PDF. Resposta: {list(data.keys())}"
                    }

                # Decodificar base64 para bytes
                try:
                    pdf_bytes = base64.b64decode(pdf_base64)
                except Exception as e:
                    return {
                        "sucesso": False,
                        "pdf_bytes": None,
                        "xml_bytes": None,
                        "filename": None,
                        "erro": f"Erro ao decodificar PDF: {str(e)}"
                    }

                # PASSO 3: Baixar o XML da NFe
                url_xml = f"{self.base_url}/fd/get/xml/{chave}"

                response_xml = await client.get(
                    url_xml,
                    headers=self._get_headers()
                )

                # Verificar se conseguiu baixar o XML
                xml_bytes = None
                if response_xml.status_code == 200:
                    try:
                        data_xml = response_xml.json()
                        xml_base64 = data_xml.get("data")
                        if xml_base64:
                            # A API retorna o XML em TEXTO no campo "data", não em base64!
                            # Converter a string XML para bytes UTF-8
                            xml_bytes = xml_base64.encode('utf-8')
                            print(f"✓ XML baixado: {len(xml_bytes)} bytes")

                            # Verificar se é XML válido (começa com <?xml ou <nfeProc)
                            try:
                                xml_inicio = xml_bytes[:100].decode('utf-8', errors='ignore')
                                if '<?xml' in xml_inicio or '<nfeProc' in xml_inicio:
                                    print(f"✓ XML válido: {xml_inicio[:50]}...")
                                else:
                                    print(f"⚠ Aviso: XML pode estar corrompido. Início: {xml_inicio[:50]}")
                            except:
                                pass
                    except Exception as e:
                        # Se falhar ao baixar XML, continua sem ele
                        print(f"Aviso: Não foi possível baixar o XML: {str(e)}")

                # Gerar nome do arquivo (últimos 8 dígitos da chave)
                filename = f"DANFE_{chave[-8:]}.pdf"

                return {
                    "sucesso": True,
                    "pdf_bytes": pdf_bytes,
                    "xml_bytes": xml_bytes,
                    "filename": filename,
                    "erro": None
                }

        except httpx.TimeoutException:
            return {
                "sucesso": False,
                "pdf_bytes": None,
                "xml_bytes": None,
                "filename": None,
                "erro": "Timeout na consulta da API (mais de 30 segundos)"
            }

        except httpx.ConnectError:
            return {
                "sucesso": False,
                "pdf_bytes": None,
                "xml_bytes": None,
                "filename": None,
                "erro": "Erro de conexão com a API MeuDanfe"
            }

        except Exception as e:
            return {
                "sucesso": False,
                "pdf_bytes": None,
                "xml_bytes": None,
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
