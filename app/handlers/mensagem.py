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

Aqui você consulta o DANFE da nota fiscal rapidinho.

*Como usar:*
Manda a chave de 44 números da nota e eu te devolvo o PDF.

Você ganhou *7 dias grátis* pra testar!

Manda a primeira chave aí 👇
""",

    "instrucoes": """
📋 *Como usar o Bot DANFE:*

1️⃣ Manda a chave de 44 números da nota fiscal
2️⃣ Recebe o PDF do DANFE em segundos

*Comandos:*
- Digite *status* pra ver sua assinatura
- Digite *ajuda* pra ver essa mensagem

Dúvidas? Fala com a gente: (XX) XXXXX-XXXX
""",

    "chave_invalida": """
❌ Chave inválida

Confere se digitou os 44 números certinho, sem espaços ou letras.

Exemplo de chave:
35250112345678000199550010001234561123456789
""",

    "nota_nao_disponivel": """
⏳ Chave tá certa, mas a nota ainda não apareceu no sistema.

Isso acontece quando a nota acabou de ser emitida.

Tenta de novo em 5-10 minutos!
""",

    "assinatura_vencida": """
⚠️ Sua assinatura venceu!

Pra continuar usando, renova por apenas *R$ 14,90/mês*

Paga o Pix abaixo e já libera na hora 👇
""",

    "pagamento_confirmado": """
✅ Pagamento confirmado!

Sua assinatura tá ativa por mais 30 dias.

Pode mandar a chave da nota aí!
""",

    "status": """
📊 *Sua assinatura:*

Status: {status}
Válida até: {data_expiracao}
Consultas realizadas: {total_consultas}
""",

    "erro_api": """
😕 Deu um erro na consulta. Tenta de novo em alguns segundos.

Se continuar dando erro, manda mensagem pra gente.
""",

    "sucesso": """
✅ DANFE encontrado!

Tá aí o PDF e o XML 👆
""",

    "processando": """
⏳ Consultando a nota fiscal...

Aguarda uns segundinhos...
"""
}


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

        # 3. Verificar se assinatura está ativa
        if not usuario.assinatura_ativa:
            await self._solicitar_pagamento(usuario, telefone_limpo)
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
            # Criar com período trial (7 dias grátis)
            data_expiracao = datetime.now() + timedelta(days=config.DIAS_TRIAL)

            usuario = Usuario(
                telefone=telefone,
                data_expiracao=data_expiracao,
                ativo=True
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
        """Envia status da assinatura para o usuário"""
        # Contar consultas
        total_consultas = self.db.query(Consulta).filter(
            Consulta.usuario_id == usuario.id,
            Consulta.sucesso == True
        ).count()

        # Status
        if usuario.assinatura_ativa:
            status = f"✅ Ativa ({usuario.dias_restantes} dias restantes)"
        else:
            status = "❌ Vencida"

        # Formatar data
        data_expiracao_str = usuario.data_expiracao.strftime("%d/%m/%Y às %H:%M")

        # Montar mensagem
        mensagem = MENSAGENS["status"].format(
            status=status,
            data_expiracao=data_expiracao_str,
            total_consultas=total_consultas
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
