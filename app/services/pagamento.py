"""
Serviço de integração com Mercado Pago
Gera cobranças Pix e verifica status de pagamento
"""
import mercadopago
from typing import Optional
from datetime import datetime, timedelta
from ..config import config


class PagamentoService:
    """
    Serviço para gerenciar pagamentos via Mercado Pago (Pix)
    """

    def __init__(self):
        # Inicializar SDK do Mercado Pago
        self.sdk = mercadopago.SDK(config.MERCADOPAGO_ACCESS_TOKEN)

    def gerar_pix(self, usuario_id: int, telefone: str, valor: Optional[float] = None) -> dict:
        """
        Gera cobrança Pix via Mercado Pago

        Args:
            usuario_id: ID do usuário no banco de dados
            telefone: Telefone do usuário
            valor: Valor da cobrança (padrão: config.VALOR_ASSINATURA)

        Returns:
            dict: {
                "sucesso": True/False,
                "qr_code": str (código copia e cola),
                "qr_code_base64": str (imagem do QR Code em base64),
                "id_transacao": str (ID da transação no Mercado Pago),
                "erro": str ou None
            }
        """
        try:
            # Usar valor padrão se não fornecido
            if valor is None:
                valor = config.VALOR_ASSINATURA

            # Calcular data de expiração (30 minutos)
            expiracao = datetime.now() + timedelta(minutes=30)

            # Criar payload para pagamento
            payment_data = {
                "transaction_amount": float(valor),
                "description": f"Assinatura DanfeZap - 30 dias",
                "payment_method_id": "pix",
                "payer": {
                    "email": f"user{usuario_id}@danfezap.com",  # Email fictício
                    "first_name": "Cliente",
                    "last_name": "DanfeZap",
                    "identification": {
                        "type": "CPF",
                        "number": "00000000000"  # CPF genérico (MP aceita)
                    }
                },
                "external_reference": f"usuario_{usuario_id}",  # Referência para identificar o usuário
                "date_of_expiration": expiracao.isoformat(),
                "notification_url": f"{config.WEBHOOK_BASE_URL}/webhook/mercadopago"  # Webhook
            }

            # Criar pagamento
            payment_response = self.sdk.payment().create(payment_data)
            payment = payment_response["response"]

            # Verificar se foi criado com sucesso
            if payment_response["status"] not in [200, 201]:
                return {
                    "sucesso": False,
                    "qr_code": None,
                    "qr_code_base64": None,
                    "id_transacao": None,
                    "erro": f"Erro ao criar pagamento: {payment_response.get('message', 'Erro desconhecido')}"
                }

            # Extrair dados do Pix
            pix_data = payment.get("point_of_interaction", {}).get("transaction_data", {})

            qr_code = pix_data.get("qr_code")  # Código copia e cola
            qr_code_base64 = pix_data.get("qr_code_base64")  # Imagem QR Code
            id_transacao = str(payment.get("id"))

            if not qr_code or not qr_code_base64:
                return {
                    "sucesso": False,
                    "qr_code": None,
                    "qr_code_base64": None,
                    "id_transacao": id_transacao,
                    "erro": "Mercado Pago não retornou dados do Pix"
                }

            return {
                "sucesso": True,
                "qr_code": qr_code,
                "qr_code_base64": qr_code_base64,
                "id_transacao": id_transacao,
                "erro": None
            }

        except Exception as e:
            return {
                "sucesso": False,
                "qr_code": None,
                "qr_code_base64": None,
                "id_transacao": None,
                "erro": f"Erro ao gerar Pix: {str(e)}"
            }

    def verificar_pagamento(self, id_transacao: str) -> dict:
        """
        Verifica status de um pagamento no Mercado Pago

        Args:
            id_transacao: ID da transação no Mercado Pago

        Returns:
            dict: {
                "pago": True/False,
                "status": str (approved, pending, rejected, etc),
                "data_pagamento": datetime ou None,
                "valor": float ou None,
                "erro": str ou None
            }
        """
        try:
            # Buscar pagamento
            payment_response = self.sdk.payment().get(id_transacao)
            payment = payment_response["response"]

            # Verificar se a consulta foi bem-sucedida
            if payment_response["status"] != 200:
                return {
                    "pago": False,
                    "status": "error",
                    "data_pagamento": None,
                    "valor": None,
                    "erro": "Erro ao consultar pagamento no Mercado Pago"
                }

            status = payment.get("status")
            valor = payment.get("transaction_amount")

            # Data de aprovação (se aprovado)
            data_aprovacao = payment.get("date_approved")
            data_pagamento = None

            if data_aprovacao:
                # Converter ISO string para datetime
                data_pagamento = datetime.fromisoformat(data_aprovacao.replace('Z', '+00:00'))

            # Verificar se está aprovado
            pago = status == "approved"

            return {
                "pago": pago,
                "status": status,
                "data_pagamento": data_pagamento,
                "valor": valor,
                "erro": None
            }

        except Exception as e:
            return {
                "pago": False,
                "status": "error",
                "data_pagamento": None,
                "valor": None,
                "erro": f"Erro ao verificar pagamento: {str(e)}"
            }

    def processar_webhook(self, webhook_data: dict) -> dict:
        """
        Processa notificação do webhook do Mercado Pago

        Args:
            webhook_data: Dados recebidos do webhook

        Returns:
            dict: {
                "tipo": str (payment, etc),
                "id_transacao": str,
                "action": str (payment.created, payment.updated),
                "dados_pagamento": dict ou None
            }
        """
        try:
            # Extrair tipo e ID da notificação
            tipo = webhook_data.get("type")
            action = webhook_data.get("action")

            # Extrair ID do pagamento
            data = webhook_data.get("data", {})
            id_transacao = data.get("id")

            # Se for notificação de pagamento
            if tipo == "payment" and id_transacao:
                # Verificar o pagamento
                verificacao = self.verificar_pagamento(str(id_transacao))

                return {
                    "tipo": tipo,
                    "id_transacao": str(id_transacao),
                    "action": action,
                    "dados_pagamento": verificacao
                }

            return {
                "tipo": tipo,
                "id_transacao": id_transacao,
                "action": action,
                "dados_pagamento": None
            }

        except Exception as e:
            return {
                "tipo": "error",
                "id_transacao": None,
                "action": None,
                "dados_pagamento": None,
                "erro": f"Erro ao processar webhook: {str(e)}"
            }


# Instância global do serviço
pagamento_service = PagamentoService()
