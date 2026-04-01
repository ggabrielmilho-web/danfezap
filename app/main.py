"""
App principal FastAPI
Webhooks para Evolution API (WhatsApp) e Mercado Pago
"""
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import logging

from .database import get_db, init_db
from .models import Usuario, Pagamento
from .handlers.mensagem import processar_mensagem_recebida
from .services.pagamento import pagamento_service
from .services.image_reader import image_reader_service
from .config import config

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Criar app FastAPI
app = FastAPI(
    title="Bot DANFE WhatsApp",
    description="Bot para consulta de DANFE via WhatsApp",
    version="1.0.0"
)


@app.on_event("startup")
async def startup_event():
    """Evento executado ao iniciar a aplicação"""
    logger.info("Iniciando Bot DANFE WhatsApp...")

    # Criar tabelas no banco de dados
    try:
        init_db()
        logger.info("Banco de dados inicializado com sucesso")
    except Exception as e:
        logger.error(f"Erro ao inicializar banco de dados: {e}")

    logger.info("Aplicação iniciada!")


@app.get("/")
async def root():
    """Endpoint raiz - verificação de saúde"""
    return {
        "status": "online",
        "app": "Bot DANFE WhatsApp",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """Endpoint de health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }


@app.post("/webhook/uazapi")
async def webhook_uazapi(request: Request, db: Session = Depends(get_db)):
    """
    Webhook para receber mensagens do WhatsApp via UazAPI

    Payload esperado:
    {
        "fromMe": false,
        "sender": "5511999999999@s.whatsapp.net",
        "messageType": "conversation",
        "text": "Texto da mensagem",
        "fileURL": "https://..." (para mídias)
    }
    """
    try:
        payload = await request.json()
        logger.info(f"Webhook UazAPI recebido: {payload}")

        # Ignorar mensagens enviadas por nós
        from_me = payload.get("fromMe", False)
        if from_me:
            logger.info("Mensagem ignorada: enviada por nós")
            return JSONResponse({"status": "ignored", "reason": "from_me"})

        # Extrair remetente
        sender = payload.get("sender", "")
        if not sender:
            logger.warning("Webhook sem sender")
            return JSONResponse({"status": "error", "message": "sender not found"})

        # Extrair telefone (remover @s.whatsapp.net ou @lid)
        telefone = sender.replace("@s.whatsapp.net", "").replace("@lid", "")

        message_type = payload.get("messageType", "")
        file_url = payload.get("fileURL", "")

        # Verificar se é imagem
        if message_type == "imageMessage":
            logger.info(f"Imagem recebida de {telefone}")
            await processar_imagem_recebida(telefone, file_url, db)
            return JSONResponse({"status": "success", "message": "image_processed"})

        # Mensagem de texto
        texto = payload.get("text", "")
        if not texto:
            logger.info(f"Mensagem sem texto ignorada (tipo: {message_type})")
            return JSONResponse({"status": "ignored", "reason": "no_text"})

        logger.info(f"Processando mensagem de {telefone}: {texto}")
        await processar_mensagem_recebida(telefone, texto, db)

        return JSONResponse({"status": "success", "message": "processed"})

    except Exception as e:
        logger.error(f"Erro ao processar webhook UazAPI: {e}")
        return JSONResponse(
            {"status": "error", "message": str(e)},
            status_code=500
        )


async def processar_imagem_recebida(telefone: str, file_url: str, db: Session):
    """
    Processa imagem recebida e extrai chave NFe automaticamente

    Fluxo:
    1. Envia "📷 Analisando imagem..."
    2. Tenta extrair chave (pyzbar → Google Vision)
    3. Se encontrar, valida e processa como chave NFe
    4. Se não encontrar, pede foto melhor ou digitar chave
    """
    from app.services.whatsapp import whatsapp_service
    from app.handlers.mensagem import MensagemHandler

    # 1. Enviar mensagem de processamento
    await whatsapp_service.enviar_mensagem(telefone, "📷 Analisando imagem...")

    try:
        # 2. Processar imagem
        resultado = await image_reader_service.processar_imagem(file_url)

        if resultado["sucesso"] and resultado["chave"]:
            # Chave encontrada!
            chave = resultado["chave"]
            metodo = resultado["metodo"]

            logger.info(f"Chave extraída de imagem ({metodo}): {chave}")

            # 3. Processar como mensagem de texto (chave NFe)
            handler = MensagemHandler(db)
            await handler.processar_mensagem(telefone, chave)

        else:
            # Não conseguiu extrair chave
            erro = resultado.get("erro", "Não consegui ler a chave")
            logger.warning(f"Falha ao extrair chave de imagem: {erro}")

            await whatsapp_service.enviar_mensagem(
                telefone,
                "❌ Não consegui ler a chave na imagem.\n\n"
                "Tenta:\n"
                "• Mandar uma foto mais clara\n"
                "• Focar no código de barras/QR Code\n"
                "• Ou digitar os 44 números da chave"
            )

    except Exception as e:
        logger.error(f"Erro ao processar imagem: {e}")
        await whatsapp_service.enviar_mensagem(
            telefone,
            "😕 Erro ao processar a imagem. Tenta de novo ou digita a chave."
        )


@app.post("/webhook/mercadopago")
async def webhook_mercadopago(request: Request, db: Session = Depends(get_db)):
    """
    Webhook para receber notificações de pagamento do Mercado Pago

    Payload esperado:
    {
        "action": "payment.created" ou "payment.updated",
        "type": "payment",
        "data": {
            "id": "123456789"
        }
    }
    """
    try:
        # Receber payload
        payload = await request.json()
        logger.info(f"Webhook Mercado Pago recebido: {payload}")

        # Processar webhook
        resultado = pagamento_service.processar_webhook(payload)

        # Verificar se é notificação de pagamento
        if resultado["tipo"] != "payment":
            logger.info(f"Tipo de notificação ignorado: {resultado['tipo']}")
            return JSONResponse({"status": "ignored"})

        # Verificar se o pagamento foi aprovado
        dados_pagamento = resultado.get("dados_pagamento")
        if not dados_pagamento or not dados_pagamento.get("pago"):
            logger.info(f"Pagamento não aprovado ainda. Status: {dados_pagamento.get('status') if dados_pagamento else 'unknown'}")
            return JSONResponse({"status": "pending"})

        # Pagamento aprovado! Atualizar no banco
        id_transacao = resultado["id_transacao"]

        # Buscar pagamento no banco
        pagamento = db.query(Pagamento).filter(
            Pagamento.id_transacao_mp == id_transacao
        ).first()

        if not pagamento:
            logger.warning(f"Pagamento não encontrado no banco: {id_transacao}")
            return JSONResponse({"status": "not_found"})

        # IDEMPOTÊNCIA: Verificar se pagamento já foi processado
        if pagamento.status == "aprovado":
            logger.info(f"Pagamento já processado anteriormente: {id_transacao}")
            return JSONResponse({
                "status": "already_processed",
                "message": "Pagamento já foi aprovado anteriormente"
            })

        # Atualizar status do pagamento
        pagamento.status = "aprovado"
        pagamento.data_pagamento = dados_pagamento.get("data_pagamento") or datetime.now()

        # Buscar usuário
        usuario = db.query(Usuario).filter(Usuario.id == pagamento.usuario_id).first()

        if not usuario:
            logger.error(f"Usuário não encontrado: {pagamento.usuario_id}")
            db.commit()
            return JSONResponse({"status": "user_not_found"})

        # Renovar/ativar assinatura
        usuario.assinante = True
        usuario.consultas_mes = 0  # RESETA O CONTADOR (libera 100 consultas)
        usuario.consultas_gratis = 0  # Zera consultas grátis (não precisa mais)
        usuario.data_pagamento = datetime.now().date()
        usuario.limite_consultas = config.LIMITE_CONSULTAS_MES  # 100

        # SEMPRE adiciona 30 dias a partir de AGORA (cancela trial se existir)
        usuario.data_expiracao = datetime.now() + timedelta(days=config.DIAS_ASSINATURA)
        usuario.ativo = True

        # Salvar no banco
        db.commit()

        logger.info(f"Pagamento aprovado! Usuário {usuario.id} com assinatura até {usuario.data_expiracao}")

        # Enviar mensagem de confirmação no WhatsApp
        from .services.whatsapp import whatsapp_service
        from .handlers.mensagem import MENSAGENS

        import asyncio
        asyncio.create_task(
            whatsapp_service.enviar_mensagem(
                usuario.telefone,
                MENSAGENS["pagamento_confirmado"]
            )
        )

        return JSONResponse({"status": "success", "message": "payment_approved"})

    except Exception as e:
        logger.error(f"Erro ao processar webhook Mercado Pago: {e}")
        return JSONResponse(
            {"status": "error", "message": str(e)},
            status_code=500
        )


@app.get("/stats")
async def stats(db: Session = Depends(get_db)):
    """Endpoint para estatísticas do bot (opcional)"""
    try:
        total_usuarios = db.query(Usuario).count()
        usuarios_ativos = db.query(Usuario).filter(
            Usuario.ativo == True,
            Usuario.data_expiracao > datetime.now()
        ).count()

        from .models import Consulta
        total_consultas = db.query(Consulta).count()
        consultas_sucesso = db.query(Consulta).filter(Consulta.sucesso == True).count()

        return {
            "total_usuarios": total_usuarios,
            "usuarios_ativos": usuarios_ativos,
            "total_consultas": total_consultas,
            "consultas_sucesso": consultas_sucesso,
            "taxa_sucesso": f"{(consultas_sucesso / total_consultas * 100):.2f}%" if total_consultas > 0 else "0%"
        }

    except Exception as e:
        logger.error(f"Erro ao buscar estatísticas: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
