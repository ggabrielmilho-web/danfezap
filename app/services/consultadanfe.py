"""
Serviço de consulta de DANFE - Fallback gratuito
Integração com API ConsultaDanfe (https://consultadanfe.com)

Usado quando o MeuDanfe falha. Retorna o mesmo formato de dict que o
DanfeService para ser intercambiável no fluxo.
"""
import httpx
import base64


class ConsultaDanfeService:
    """
    Serviço para consultar DANFE via API ConsultaDanfe (gratuita)
    """

    def __init__(self):
        self.base_url = "https://consultadanfe.com/api/v1"
        self.timeout = 30.0

    async def consultar(self, chave: str) -> dict:
        """
        Consulta DANFE na API ConsultaDanfe

        Single call:
        POST /consulta com body {"chave": "..."} retorna PDF + XML em base64

        Args:
            chave: Chave de acesso da NFe (44 dígitos)

        Returns:
            dict: {
                "sucesso": True/False,
                "pdf_bytes": bytes ou None,
                "xml_bytes": bytes ou None,
                "filename": str ou None,
                "erro": str ou None
            }
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                url = f"{self.base_url}/consulta"

                response = await client.post(
                    url,
                    json={"chave": chave},
                    headers={"Content-Type": "application/json"}
                )

                # Caminho feliz
                if response.status_code == 200:
                    data = response.json()
                    pdf_base64 = data.get("pdf_base64")
                    xml_base64 = data.get("xml_base64")

                    if not pdf_base64:
                        return {
                            "sucesso": False,
                            "pdf_bytes": None,
                            "xml_bytes": None,
                            "filename": None,
                            "erro": "ConsultaDanfe não retornou PDF"
                        }

                    try:
                        pdf_bytes = base64.b64decode(pdf_base64)
                    except Exception as e:
                        return {
                            "sucesso": False,
                            "pdf_bytes": None,
                            "xml_bytes": None,
                            "filename": None,
                            "erro": f"Erro ao decodificar PDF do ConsultaDanfe: {str(e)}"
                        }

                    xml_bytes = None
                    if xml_base64:
                        try:
                            xml_bytes = base64.b64decode(xml_base64)
                            print(f"✓ XML baixado via ConsultaDanfe: {len(xml_bytes)} bytes")
                        except Exception as e:
                            print(f"Aviso: erro ao decodificar XML do ConsultaDanfe: {str(e)}")

                    filename = f"DANFE_{chave[-8:]}.pdf"

                    return {
                        "sucesso": True,
                        "pdf_bytes": pdf_bytes,
                        "xml_bytes": xml_bytes,
                        "filename": filename,
                        "erro": None
                    }

                # Janela de datas: erro estável e estruturado pela API
                if response.status_code == 400:
                    error_code = response.headers.get("X-Error-Code", "")
                    if error_code == "data_fora_da_janela":
                        return {
                            "sucesso": False,
                            "pdf_bytes": None,
                            "xml_bytes": None,
                            "filename": None,
                            "erro": "Nota fora da janela do ConsultaDanfe (mês atual ou anterior antes do dia 15)"
                        }
                    try:
                        error_data = response.json()
                        error_msg = error_data.get("message", f"ConsultaDanfe rejeitou (400): {error_code or 'sem código'}")
                    except Exception:
                        error_msg = f"ConsultaDanfe rejeitou (400)"
                    return {
                        "sucesso": False,
                        "pdf_bytes": None,
                        "xml_bytes": None,
                        "filename": None,
                        "erro": error_msg
                    }

                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After", "?")
                    return {
                        "sucesso": False,
                        "pdf_bytes": None,
                        "xml_bytes": None,
                        "filename": None,
                        "erro": f"ConsultaDanfe rate limit (retry em {retry_after}s)"
                    }

                try:
                    error_data = response.json()
                    error_msg = error_data.get("message", f"ConsultaDanfe status {response.status_code}")
                except Exception:
                    error_msg = f"ConsultaDanfe status {response.status_code}"
                return {
                    "sucesso": False,
                    "pdf_bytes": None,
                    "xml_bytes": None,
                    "filename": None,
                    "erro": error_msg
                }

        except httpx.TimeoutException:
            return {
                "sucesso": False,
                "pdf_bytes": None,
                "xml_bytes": None,
                "filename": None,
                "erro": "Timeout na consulta ConsultaDanfe (mais de 30 segundos)"
            }

        except httpx.ConnectError:
            return {
                "sucesso": False,
                "pdf_bytes": None,
                "xml_bytes": None,
                "filename": None,
                "erro": "Erro de conexão com a API ConsultaDanfe"
            }

        except Exception as e:
            return {
                "sucesso": False,
                "pdf_bytes": None,
                "xml_bytes": None,
                "filename": None,
                "erro": f"Erro inesperado ConsultaDanfe: {str(e)}"
            }


# Instância global do serviço
consultadanfe_service = ConsultaDanfeService()
