"""
Handler de mensagens do bot
Lógica principal de processamento de mensagens do WhatsApp
"""
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from ..models import Usuario, Consulta, Pagamento
from ..services.validador import validar_chave_nfe, extrair_info_chave
from ..services.danfe import danfe_service
from ..services.whatsapp import whatsapp_service
from ..services.pagamento import pagamento_service
from ..config import config
import base64


# Mensagens do bot
MENSAGENS = {
    "boas_vindas": """
🚛 *Bot DANFE* - Bem-vindo!

Consulte o DANFE e XML da nota fiscal em segundos.

Você tem *5 consultas grátis* pra testar!

Manda a chave de 44 dígitos 👇
""",

    "instrucoes": """
📋 *Como usar o bot:*

1️⃣ Manda a chave de 44 dígitos da nota
2️⃣ Recebe o PDF do DANFE e o XML

*Comandos:*
• *status* - Ver suas consultas
• *ajuda* - Ver essa mensagem
• *assinar* - Assinar por R$14,90/mês

💡 Assinantes têm 100 consultas/mês
""",

    "chave_invalida": """
❌ Essa chave não tá válida.

A chave da NFe tem 44 dígitos.

Exemplo:
35210812345678000190550010000123451234567890

Confere e manda de novo!
""",

    "nota_nao_disponivel": """
⚠️ Nota não encontrada ou ainda não tá disponível.

Aguarda uns 5-10 minutos e tenta de novo.
""",

    "consultas_gratis_acabou": """
😕 Suas 5 consultas grátis acabaram!

Gostou do serviço? Assina por apenas *R$14,90/mês* e libera *100 consultas*.

Digite *assinar* pra gerar o Pix.
""",

    "assinatura_vencida": """
⚠️ Sua assinatura venceu!

Renova por *R$14,90* e libera mais *100 consultas*.

Digite *assinar* pra gerar o Pix.
""",

    "limite_atingido": """
⚠️ Você atingiu o limite de 100 consultas desse período.

Suas consultas renovam quando você fizer o próximo pagamento.

Digite *assinar* pra renovar agora.
""",

    "processando": """
⏳ Buscando o DANFE...

Aguarda só um pouquinho!
""",

    "erro_api": """
❌ Deu um problema na consulta.

Tenta de novo em alguns minutos.
""",

    "sucesso": """
✅ DANFE encontrado!

Enviando PDF e XML...
""",

    "pagamento_confirmado": """
✅ Pagamento confirmado!

Sua assinatura está ativa por 30 dias.
Você tem *100 consultas* disponíveis.

Manda a chave da nota aí! 👇
""",

    "status": """
📊 *Seu status:*

{status_texto}
Consultas usadas: {consultas_usadas}/{limite}
{info_extra}
"""
}


async def verificar_pode_consultar(usuario) -> dict:
    """
    Verifica se usuário pode fazer consulta

    Retorna:
    {"pode": True/False, "motivo": str, "acao": str, "tipo": str}
    """

    # Caso 1: Não é assinante, usa consultas grátis
    if not usuario.assinante:
        if usuario.consultas_gratis > 0:
            return {"pode": True, "tipo": "gratis"}
        else:
            return {
                "pode": False,
                "motivo": "consultas_gratis_acabou",
                "acao": "pedir_assinatura"
            }

    # Caso 2: É assinante, verifica se venceu
    if usuario.data_expiracao and datetime.now() > usuario.data_expiracao:
        return {
            "pode": False,
            "motivo": "assinatura_vencida",
            "acao": "pedir_renovacao"
        }

    # Caso 3: É assinante ativo, verifica limite mensal
    if usuario.consultas_mes >= usuario.limite_consultas:
        return {
            "pode": False,
            "motivo": "limite_atingido",
            "acao": "aguardar_renovacao"
        }

    return {"pode": True, "tipo": "assinante"}


async def registrar_consulta_contador(db, usuario):
    """
    Registra a consulta e decrementa o contador correto
    """
    if not usuario.assinante:
        usuario.consultas_gratis -= 1
    else:
        usuario.consultas_mes += 1

    db.commit()
    db.refresh(usuario)


class MensagemHandler:
    """Handler para processar mensagens recebidas do WhatsApp"""

    def __init__(self, db: Session):
        self.db = db

    async def processar_mensagem(self, telefone: str, texto: str):
        """
        Fluxo principal de processamento de mensagens

        Args:
            telefone: Número de telefone do remetente
            texto: Conteúdo da mensagem
        """
        # Limpar telefone (remover caracteres especiais)
        telefone_limpo = ''.join(filter(str.isdigit, telefone))

        # 1. Buscar ou criar usuário
        usuario = self._buscar_ou_criar_usuario(telefone_limpo)

        # 2. Processar comando/texto
        texto_limpo = texto.strip().lower()

        # Comando: status
        if texto_limpo == "status":
            await self._enviar_status(usuario)
            return

        # Comando: ajuda
        if texto_limpo in ["ajuda", "help", "menu"]:
            await whatsapp_service.enviar_mensagem(telefone_limpo, MENSAGENS["instrucoes"])
            return

        # Comando: assinar
        if texto_limpo == "assinar":
            await self._solicitar_pagamento(usuario, telefone_limpo)
            return

        # 3. Verificar se pode consultar
        verificacao = await verificar_pode_consultar(usuario)

        if not verificacao["pode"]:
            if verificacao["motivo"] == "consultas_gratis_acabou":
                await whatsapp_service.enviar_mensagem(
                    telefone_limpo,
                    MENSAGENS["consultas_gratis_acabou"]
                )
                await self._solicitar_pagamento(usuario, telefone_limpo)
            elif verificacao["motivo"] == "assinatura_vencida":
                await whatsapp_service.enviar_mensagem(
                    telefone_limpo,
                    MENSAGENS["assinatura_vencida"]
                )
                await self._solicitar_pagamento(usuario, telefone_limpo)
            elif verificacao["motivo"] == "limite_atingido":
                await whatsapp_service.enviar_mensagem(
                    telefone_limpo,
                    MENSAGENS["limite_atingido"]
                )
            return

        # 4. Verificar se é uma chave de NFe (somente números)
        if texto_limpo.replace(" ", "").isdigit():
            await self._processar_chave_nfe(usuario, telefone_limpo, texto_limpo)
            return

        # 5. Mensagem não reconhecida - enviar instruções
        await whatsapp_service.enviar_mensagem(telefone_limpo, MENSAGENS["instrucoes"])

    def _buscar_ou_criar_usuario(self, telefone: str) -> Usuario:
        """
        Busca usuário existente ou cria novo com período trial

        Args:
            telefone: Número de telefone

        Returns:
            Usuario: Objeto do usuário
        """
        # Buscar usuário existente
        usuario = self.db.query(Usuario).filter(Usuario.telefone == telefone).first()

        # Se não existe, criar novo
        if not usuario:
            # Criar com 5 consultas grátis (novo modelo)
            usuario = Usuario(
                telefone=telefone,
                data_cadastro=datetime.now(),
                consultas_gratis=config.CONSULTAS_GRATIS,  # 5 consultas
                assinante=False,
                consultas_mes=0,
                limite_consultas=config.LIMITE_CONSULTAS_MES,  # 100
                ativo=True,
                data_expiracao=None  # Não precisa mais para usuários grátis
            )

            self.db.add(usuario)
            self.db.commit()
            self.db.refresh(usuario)

            # Enviar mensagem de boas-vindas de forma assíncrona
            import asyncio
            asyncio.create_task(
                whatsapp_service.enviar_mensagem(telefone, MENSAGENS["boas_vindas"])
            )

        return usuario

    async def _enviar_status(self, usuario: Usuario):
        """Envia status da assinatura do usuário"""

        if not usuario.assinante:
            # Usuário não-assinante (modo grátis)
            consultas_usadas = 5 - usuario.consultas_gratis
            mensagem = MENSAGENS["status"].format(
                status_texto="Conta gratuita",
                consultas_usadas=consultas_usadas,
                limite=5,
                info_extra="Digite *assinar* pra ter 100 consultas/mês"
            )
        else:
            # Usuário assinante
            dias_restantes = 0
            if usuario.data_expiracao:
                delta = usuario.data_expiracao - datetime.now()
                dias_restantes = max(0, delta.days)

            status_texto = "✅ Assinante ativo" if usuario.assinatura_ativa else "❌ Assinatura vencida"
            info_extra = f"Renova em {dias_restantes} dias" if dias_restantes > 0 else "Digite *assinar* para renovar"

            mensagem = MENSAGENS["status"].format(
                status_texto=status_texto,
                consultas_usadas=usuario.consultas_mes,
                limite=usuario.limite_consultas,
                info_extra=info_extra
            )

        await whatsapp_service.enviar_mensagem(usuario.telefone, mensagem)

    async def _solicitar_pagamento(self, usuario: Usuario, telefone: str):
        """Solicita pagamento para renovar assinatura"""
        # Gerar Pix
        resultado_pix = pagamento_service.gerar_pix(
            usuario_id=usuario.id,
            telefone=telefone
        )

        if not resultado_pix["sucesso"]:
            await whatsapp_service.enviar_mensagem(
                telefone,
                "😕 Erro ao gerar pagamento. Tenta de novo em alguns minutos."
            )
            return

        # Salvar pagamento no banco
        pagamento = Pagamento(
            usuario_id=usuario.id,
            valor=config.VALOR_ASSINATURA,
            id_transacao_mp=resultado_pix["id_transacao"],
            status="pendente"
        )
        self.db.add(pagamento)
        self.db.commit()

        # Enviar mensagem de assinatura vencida
        await whatsapp_service.enviar_mensagem(telefone, MENSAGENS["assinatura_vencida"])

        # Enviar QR Code do Pix
        qr_code_base64 = resultado_pix["qr_code_base64"]
        qr_code_bytes = base64.b64decode(qr_code_base64)

        await whatsapp_service.enviar_imagem(
            telefone,
            qr_code_bytes,
            f"*Pix copia e cola:*\n\n`{resultado_pix['qr_code']}`"
        )

    async def _processar_chave_nfe(self, usuario: Usuario, telefone: str, chave: str):
        """Processa consulta de chave NFe"""
        # Remover espaços da chave
        chave_limpa = chave.replace(" ", "")

        # Validar estrutura da chave
        validacao = validar_chave_nfe(chave_limpa)

        if not validacao["valida"]:
            # Registrar tentativa inválida
            consulta = Consulta(
                usuario_id=usuario.id,
                chave_nfe=chave_limpa,
                sucesso=False,
                ultimo_erro=validacao["erro"]
            )
            self.db.add(consulta)
            self.db.commit()

            # Enviar mensagem de erro
            await whatsapp_service.enviar_mensagem(
                telefone,
                MENSAGENS["chave_invalida"]
            )
            return

        # Enviar mensagem de processamento
        await whatsapp_service.enviar_mensagem(telefone, MENSAGENS["processando"])

        # Consultar DANFE
        resultado_danfe = await danfe_service.consultar_com_retry(chave_limpa, max_tentativas=2)

        if not resultado_danfe["sucesso"]:
            # Registrar consulta com erro
            consulta = Consulta(
                usuario_id=usuario.id,
                chave_nfe=chave_limpa,
                sucesso=False,
                tentativas=resultado_danfe.get("tentativas", 1),
                ultimo_erro=resultado_danfe["erro"]
            )
            self.db.add(consulta)
            self.db.commit()

            # Verificar se é erro de nota não disponível
            if "não encontrada" in resultado_danfe["erro"].lower() or "não disponível" in resultado_danfe["erro"].lower():
                await whatsapp_service.enviar_mensagem(telefone, MENSAGENS["nota_nao_disponivel"])
            else:
                await whatsapp_service.enviar_mensagem(telefone, MENSAGENS["erro_api"])
            return

        # Sucesso! Registrar consulta
        consulta = Consulta(
            usuario_id=usuario.id,
            chave_nfe=chave_limpa,
            sucesso=True,
            tentativas=resultado_danfe.get("tentativas", 1)
        )
        self.db.add(consulta)
        self.db.commit()

        # CRÍTICO: Decrementar contador APENAS em caso de sucesso
        await registrar_consulta_contador(self.db, usuario)

        # Enviar PDF
        pdf_bytes = resultado_danfe["pdf_bytes"]
        filename = resultado_danfe["filename"]

        await whatsapp_service.enviar_pdf(
            telefone,
            pdf_bytes,
            filename
        )

        # Enviar XML (se disponível)
        xml_bytes = resultado_danfe.get("xml_bytes")
        if xml_bytes:
            xml_filename = f"NFE_{chave_limpa[-8:]}.xml"
            await whatsapp_service.enviar_xml(
                telefone,
                xml_bytes,
                xml_filename
            )

        # Enviar mensagem de sucesso
        await whatsapp_service.enviar_mensagem(telefone, MENSAGENS["sucesso"])


async def processar_mensagem_recebida(telefone: str, texto: str, db: Session):
    """
    Função auxiliar para processar mensagem recebida

    Args:
        telefone: Número de telefone do remetente
        texto: Conteúdo da mensagem
        db: Sessão do banco de dados
    """
    handler = MensagemHandler(db)
    await handler.processar_mensagem(telefone, texto)
