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
    "boas_vindas": (
        "🔥 Bem-vindo ao DanfeZap!\n\n"
        "Você ganhou *2 consultas grátis* 👇\n\n"
        "Manda agora a *foto* ou o *print da chave* da NF-e\n"
        "e receba o XML + DANFE em segundos 📄"
    ),

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

    "ajuda": """
📞 *Precisa de ajuda?*

Fique tranquilo! A equipe *DanfeZap* está pronta para te atender.

Entre em contato com nosso suporte:
*(34) 99943-4613*

Estamos aqui para ajudar! 🚛
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

    "consultas_gratis_acabou": (
        "🚫 Suas consultas grátis acabaram\n\n"
        "⚡ Isso aqui economiza um tempo absurdo no dia a dia\n\n"
        "Pra continuar usando 👇\n\n"
        "💼 *1 — Básico* R$14,90 (100 consultas/mês)\n"
        "⚡ *2 — Profissional* R$49 (Ilimitado)\n\n"
        "👉 Recomendado pra quem usa com frequência\n\n"
        "Qual você quer liberar? Responde *1* ou *2*"
    ),

    "assinatura_vencida": (
        "⏳ Sua assinatura venceu!\n\n"
        "⚡ Isso aqui economiza um tempo absurdo no dia a dia\n\n"
        "Renova pra continuar usando 👇\n\n"
        "💼 *1 — Básico* R$14,90 (100 consultas/mês)\n"
        "⚡ *2 — Profissional* R$49 (Ilimitado)\n\n"
        "Qual você quer? Responde *1* ou *2*"
    ),

    "limite_atingido": (
        "⚠️ Você atingiu o limite de consultas do plano atual.\n\n"
        "Suas consultas renovam no próximo pagamento.\n\n"
        "Digita *assinar* pra ver as opções."
    ),

    "escolher_plano": (
        "Qual plano você quer?\n\n"
        "💼 *1 — Básico* R$14,90 (100 consultas/mês)\n"
        "⚡ *2 — Profissional* R$49 (Ilimitado)\n\n"
        "Responde *1* ou *2*"
    ),

    "uso_extremo": (
        "⚠️ Uso muito acima do normal detectado.\n\n"
        "Fala com a gente pra liberar um plano personalizado 😉\n"
        "📞 (34) 99943-4613"
    ),

    "processando": "🔍 Buscando sua nota...",

    "erro_api": """
❌ Deu um problema na consulta.

Tenta de novo em alguns minutos.
""",

    "sucesso": "✅ Pronto! Aqui está 👇",

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
""",

    "perguntar_email_principal": (
        "📩 Se quiser receber automaticamente no email também, me manda seu email aqui 😉"
    ),

    "email_cadastrado": """
✅ Email cadastrado: {email}
""",

    "email_enviado_automatico": """
✅ DANFE enviado!

📧 Também enviei pro(s) seu(s) email(s) cadastrado(s).
""",

    "email_invalido": """
❌ Email inválido.

Manda um email válido (ex: seuemail@gmail.com) ou "não" pra pular.
""",

    "erro_envio_email": """
⚠️ Erro ao enviar email. Mas o DANFE foi enviado aqui no WhatsApp!
""",

    "ver_emails": (
        "📧 *Email cadastrado:*\n\n"
        "{email}\n\n"
        "Quer alterar? Manda o novo email ou *limpar* pra apagar."
    ),

    "nao_entendi": """
Não entendi 😅

📸 Manda a foto do código de barras
Ou digita a chave de 44 dígitos

*Comandos:*
• *status* - Ver suas consultas
• *email* - Cadastrar/ver emails
• *assinar* - R$14,90/mês
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

    # Caso 3: É assinante ativo, verifica uso extremo (plano Pro acima de 1500)
    if getattr(usuario, "plano", None) == "pro" and usuario.consultas_mes > 1500:
        return {
            "pode": False,
            "motivo": "uso_extremo",
            "acao": "contato_suporte"
        }

    # Caso 4: É assinante ativo, verifica limite mensal
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
        usuario, usuario_novo = self._buscar_ou_criar_usuario(telefone_limpo)

        # 2. Verificar se está aguardando escolha de plano
        if getattr(usuario, "aguardando_escolha_plano", False):
            await self._processar_escolha_plano(usuario, telefone_limpo, texto)
            return

        # 3. Verificar se está aguardando resposta de email
        if usuario.aguardando_email_principal or usuario.aguardando_email_secundario:
            processou = await self._processar_resposta_email(usuario, telefone_limpo, texto)
            if processou:
                return  # Email processado, para por aqui

        # 4. Processar comando/texto
        texto_limpo = texto.strip().lower()

        # Comando: status
        if texto_limpo == "status":
            await self._enviar_status(usuario)
            return

        # Comando: ajuda
        if texto_limpo in ["ajuda", "help", "menu"]:
            await whatsapp_service.enviar_mensagem(telefone_limpo, MENSAGENS["ajuda"])
            return

        # Comando: assinar
        if texto_limpo == "assinar":
            usuario.aguardando_escolha_plano = True
            self.db.commit()
            await whatsapp_service.enviar_mensagem(telefone_limpo, MENSAGENS["escolher_plano"])
            return

        # Comando: email
        if texto_limpo in ["email", "e-mail"]:
            await self._gerenciar_emails(usuario, telefone_limpo)
            return

        # 5. Verificar se pode consultar
        verificacao = await verificar_pode_consultar(usuario)

        if not verificacao["pode"]:
            motivo = verificacao["motivo"]
            if motivo in ("consultas_gratis_acabou", "assinatura_vencida"):
                usuario.aguardando_escolha_plano = True
                self.db.commit()
                await whatsapp_service.enviar_mensagem(
                    telefone_limpo,
                    MENSAGENS[motivo]
                )
            elif motivo == "limite_atingido":
                await whatsapp_service.enviar_mensagem(
                    telefone_limpo,
                    MENSAGENS["limite_atingido"]
                )
            elif motivo == "uso_extremo":
                await whatsapp_service.enviar_mensagem(
                    telefone_limpo,
                    MENSAGENS["uso_extremo"]
                )
            return

        # 6. Verificar se é uma chave de NFe (somente números)
        if texto_limpo.replace(" ", "").isdigit():
            await self._processar_chave_nfe(usuario, telefone_limpo, texto_limpo)
            return

        # 7. Mensagem não reconhecida - enviar resposta padrão
        # Não enviar se for usuário novo (já recebeu boas-vindas)
        if not usuario_novo:
            await whatsapp_service.enviar_mensagem(telefone_limpo, MENSAGENS["nao_entendi"])

    def _buscar_ou_criar_usuario(self, telefone: str) -> tuple[Usuario, bool]:
        """
        Busca usuário existente ou cria novo com período trial

        Args:
            telefone: Número de telefone

        Returns:
            tuple[Usuario, bool]: (Objeto do usuário, True se novo usuário criado)
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

            return usuario, True  # Usuário novo criado

        return usuario, False  # Usuário existente

    async def _enviar_status(self, usuario: Usuario):
        """Envia status da assinatura do usuário"""

        if not usuario.assinante:
            # Usuário não-assinante (modo grátis)
            consultas_usadas = config.CONSULTAS_GRATIS - usuario.consultas_gratis
            mensagem = MENSAGENS["status"].format(
                status_texto="Conta gratuita",
                consultas_usadas=consultas_usadas,
                limite=config.CONSULTAS_GRATIS,
                info_extra="Digite *assinar* pra ver os planos disponíveis"
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

    async def _processar_escolha_plano(self, usuario: Usuario, telefone: str, texto: str):
        """Processa a escolha de plano (1=básico, 2=pro) e gera o Pix correspondente."""
        texto_limpo = texto.strip().lower()

        if texto_limpo in ("1", "basico", "básico"):
            plano = "basico"
            valor = config.VALOR_PLANO_BASICO
        elif texto_limpo in ("2", "pro", "profissional"):
            plano = "pro"
            valor = config.VALOR_PLANO_PRO
        else:
            await whatsapp_service.enviar_mensagem(telefone, MENSAGENS["escolher_plano"])
            return

        usuario.aguardando_escolha_plano = False
        usuario.plano = plano
        self.db.commit()

        await whatsapp_service.enviar_mensagem(telefone, "💳 Gerando seu Pix... 👇")
        await self._solicitar_pagamento(usuario, telefone, plano=plano, valor=valor)

    async def _solicitar_pagamento(self, usuario: Usuario, telefone: str, plano: str = "basico", valor: float = None):
        """Solicita pagamento para renovar assinatura"""
        if valor is None:
            valor = config.VALOR_PLANO_BASICO

        # Gerar Pix
        resultado_pix = pagamento_service.gerar_pix(
            usuario_id=usuario.id,
            telefone=telefone,
            valor=valor,
            plano=plano
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
            valor=valor,
            id_transacao_mp=resultado_pix["id_transacao"],
            status="pendente",
            plano=plano
        )
        self.db.add(pagamento)
        self.db.commit()

        # Enviar QR Code do Pix
        qr_code_base64 = resultado_pix["qr_code_base64"]
        qr_code_bytes = base64.b64decode(qr_code_base64)

        # Mensagem 1: QR Code com informações
        await whatsapp_service.enviar_imagem(
            telefone,
            qr_code_bytes,
            f"💳 *Pagamento via Pix*\n\nEscaneie o QR Code ou copie o código abaixo:"
        )

        # Mensagem 2: Código Pix puro (sem formatação para facilitar cópia)
        await whatsapp_service.enviar_mensagem(
            telefone,
            resultado_pix['qr_code']
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

        # Enviar por email se cadastrado
        if usuario.email:
            from app.services.email_service import email_service

            resultado_email = await email_service.enviar_danfe(
                emails=[usuario.email],
                chave_nfe=chave_limpa,
                pdf_bytes=pdf_bytes,
                xml_bytes=xml_bytes
            )

            if resultado_email["sucesso"]:
                await whatsapp_service.enviar_mensagem(
                    telefone,
                    "📧 Enviei pro seu email também!"
                )
            else:
                await whatsapp_service.enviar_mensagem(
                    telefone,
                    MENSAGENS["erro_envio_email"]
                )
        else:
            # Não tem email → perguntar se quer cadastrar
            usuario.aguardando_email_principal = True
            self.db.commit()

            await whatsapp_service.enviar_mensagem(
                telefone,
                MENSAGENS["perguntar_email_principal"]
            )

    def _validar_email(self, texto: str) -> bool:
        """
        Valida formato básico de email

        Args:
            texto: Texto a ser validado

        Returns:
            bool: True se formato válido, False caso contrário
        """
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, texto.strip()))

    async def _processar_resposta_email(self, usuario: Usuario, telefone: str, texto: str) -> bool:
        """
        Processa resposta quando usuário está aguardando cadastro de email

        Args:
            usuario: Objeto do usuário
            telefone: Número de telefone
            texto: Texto enviado pelo usuário

        Returns:
            bool: True se processou email, False se deve continuar fluxo normal
        """
        texto_limpo = texto.strip().lower()

        # Aguardando email principal
        if usuario.aguardando_email_principal:
            # Se disser não, cancela
            if texto_limpo in ["não", "nao", "n"]:
                usuario.aguardando_email_principal = False
                self.db.commit()
                await whatsapp_service.enviar_mensagem(
                    telefone,
                    "👍 Beleza! Qualquer coisa é só mandar outra chave."
                )
                return True

            # Se for email válido, salva e encerra
            if self._validar_email(texto):
                usuario.email = texto.strip()
                usuario.aguardando_email_principal = False
                self.db.commit()

                await whatsapp_service.enviar_mensagem(
                    telefone,
                    MENSAGENS["email_cadastrado"].format(email=usuario.email)
                )
                return True

            # Email inválido mas não é comando/chave → avisar
            if not texto_limpo.replace(" ", "").isdigit() and texto_limpo not in ["status", "ajuda", "assinar", "email"]:
                await whatsapp_service.enviar_mensagem(
                    telefone,
                    MENSAGENS["email_invalido"]
                )
                return True

            # É comando ou chave → resetar estado e continuar fluxo normal
            usuario.aguardando_email_principal = False
            self.db.commit()
            return False

        return False

    async def _gerenciar_emails(self, usuario: Usuario, telefone: str):
        """
        Mostra e permite gerenciar emails cadastrados

        Args:
            usuario: Objeto do usuário
            telefone: Número de telefone
        """
        if not usuario.email:
            await whatsapp_service.enviar_mensagem(
                telefone,
                "📧 Você ainda não cadastrou nenhum email.\n\nFaça uma consulta e vou te perguntar se quer receber por email!"
            )
            return

        await whatsapp_service.enviar_mensagem(
            telefone,
            MENSAGENS["ver_emails"].format(email=usuario.email)
        )


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
