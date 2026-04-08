"""
Serviço de follow-up automático
Envia mensagens de reengajamento em janelas de tempo após o cadastro
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
from ..database import SessionLocal
from ..models import Usuario
from ..config import config
from .whatsapp import whatsapp_service
import logging

logger = logging.getLogger(__name__)

MSGS_FOLLOWUP = {
    "ativacao": (
        "👀 Ainda não testou?\n\n"
        "Manda uma foto da chave da nota aqui 👇\n"
        "e vê funcionando na hora, leva 5 segundos!"
    ),
    "reforco": (
        "🔥 Isso aqui ajuda MUITO no dia a dia\n\n"
        "Se tiver outra nota aí, testa de novo 👇"
    ),
    "recuperacao": (
        "👀 Ainda tá pedindo XML pro cliente?\n\n"
        "Aqui você resolve isso em segundos 👇"
    ),
}


async def _checar_e_enviar():
    db = SessionLocal()
    try:
        agora = datetime.now()

        # Janela 1 — 2h a 4h após cadastro, nunca usou nenhuma consulta
        inicio_2h = agora - timedelta(hours=4)
        fim_2h    = agora - timedelta(hours=2)
        usuarios_2h = db.query(Usuario).filter(
            Usuario.data_cadastro >= inicio_2h,
            Usuario.data_cadastro < fim_2h,
            Usuario.consultas_gratis == config.CONSULTAS_GRATIS,
            Usuario.assinante == False
        ).all()
        for u in usuarios_2h:
            await whatsapp_service.enviar_mensagem(u.telefone, MSGS_FOLLOWUP["ativacao"])
            logger.info(f"Follow-up ativação enviado: {u.telefone}")

        # Janela 2 — 24h a 26h após cadastro, usou pelo menos uma consulta mas não assinou
        inicio_24h = agora - timedelta(hours=26)
        fim_24h    = agora - timedelta(hours=24)
        usuarios_24h = db.query(Usuario).filter(
            Usuario.data_cadastro >= inicio_24h,
            Usuario.data_cadastro < fim_24h,
            Usuario.consultas_gratis > 0,
            Usuario.assinante == False
        ).all()
        for u in usuarios_24h:
            await whatsapp_service.enviar_mensagem(u.telefone, MSGS_FOLLOWUP["reforco"])
            logger.info(f"Follow-up reforço enviado: {u.telefone}")

        # Janela 3 — 72h a 74h após cadastro, nunca assinou
        inicio_72h = agora - timedelta(hours=74)
        fim_72h    = agora - timedelta(hours=72)
        usuarios_72h = db.query(Usuario).filter(
            Usuario.data_cadastro >= inicio_72h,
            Usuario.data_cadastro < fim_72h,
            Usuario.assinante == False
        ).all()
        for u in usuarios_72h:
            await whatsapp_service.enviar_mensagem(u.telefone, MSGS_FOLLOWUP["recuperacao"])
            logger.info(f"Follow-up recuperação enviado: {u.telefone}")

    except Exception as e:
        logger.error(f"Erro no job de follow-up: {e}")
    finally:
        db.close()


def iniciar_scheduler(app):
    """Registra e inicia o scheduler de follow-up junto ao ciclo de vida do FastAPI."""
    scheduler = AsyncIOScheduler()
    scheduler.add_job(_checar_e_enviar, "interval", hours=1)
    scheduler.start()
    logger.info("Scheduler de follow-up iniciado (intervalo: 1h)")
