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


@app.post("/webhook/evolution")
async def webhook_evolution(request: Request, db: Session = Depends(get_db)):
    """
    Webhook para receber mensagens do WhatsApp via Evolution API

    Payload esperado:
    {
        "event": "messages.upsert",
        "instance": "danfezap",
        "data": {
            "key": {
                "remoteJid": "5511999999999@s.whatsapp.net",
                "fromMe": false,
                ...
            },
            "message": {
                "conversation": "Texto da mensagem"
            },
            "messageType": "conversation",
            "pushName": "Nome do Usuário"
        }
    }
    """
    try:
        # Receber payload
        payload = await request.json()
        logger.info(f"Webhook Evolution recebido: {payload}")

        # Verificar se é uma mensagem recebida (não enviada por nós)
        event = payload.get("event")

        if event != "messages.upsert":
            logger.info(f"Evento ignorado: {event}")
            return JSONResponse({"status": "ignored", "reason": "event not messages.upsert"})

        # Extrair dados da mensagem
        data = payload.get("data", {})
        key = data.get("key", {})
        message = data.get("message", {})

        # Ignorar mensagens enviadas por nós
        from_me = key.get("fromMe", False)
        if from_me:
            logger.info("Mensagem ignorada: enviada por nós")
            return JSONResponse({"status": "ignored", "reason": "from_me"})

        # Extrair número do remetente
        remote_jid = key.get("remoteJid", "")
        if not remote_jid:
            logger.warning("Webhook sem remoteJid")
            return JSONResponse({"status": "error", "message": "remoteJid not found"})

        # Extrair telefone (remover @s.whatsapp.net)
        telefone = remote_jid.replace("@s.whatsapp.net", "")

        # Extrair texto da mensagem
        texto = None

        # Tentar diferentes formatos de mensagem
        if "conversation" in message:
            texto = message["conversation"]
        elif "extendedTextMessage" in message:
            texto = message["extendedTextMessage"].get("text", "")
        elif "imageMessage" in message:
            texto = message["imageMessage"].get("caption", "")

        if not texto:
            logger.info("Mensagem sem texto (pode ser mídia)")
            return JSONResponse({"status": "ignored", "reason": "no_text"})

        logger.info(f"Processando mensagem de {telefone}: {texto}")

        # Processar mensagem
        await processar_mensagem_recebida(telefone, texto, db)

        return JSONResponse({"status": "success", "message": "processed"})

    except Exception as e:
        logger.error(f"Erro ao processar webhook Evolution: {e}")
        return JSONResponse(
            {"status": "error", "message": str(e)},
            status_code=500
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
