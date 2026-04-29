"""
Serviço de follow-up automático com controle anti-spam:
- Flag por usuário garante envio único por mensagem
- Ordem aleatória (shuffle) a cada execução
- Delay aleatório entre envios (2–7 min) para evitar padrão detectável
"""
import asyncio
import random
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from ..database import SessionLocal
from ..models import Usuario
from ..config import config
from .whatsapp import whatsapp_service

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
    if not config.FOLLOWUP_ATIVO:
        logger.info("Follow-up desativado (FOLLOWUP_ATIVO=false)")
        return

    db = SessionLocal()
    try:
        agora = datetime.now()
        pendentes = []  # lista de (usuario, mensagem, nome_da_flag)

        # Janela 1 — 2h a 4h após cadastro, nunca usou nenhuma consulta
        inicio_2h = agora - timedelta(hours=4)
        fim_2h    = agora - timedelta(hours=2)
        for u in db.query(Usuario).filter(
            Usuario.data_cadastro >= inicio_2h,
            Usuario.data_cadastro < fim_2h,
            Usuario.consultas_gratis == config.CONSULTAS_GRATIS,
            Usuario.assinante == False,
            Usuario.followup_1_enviado == False
        ).all():
            pendentes.append((u, MSGS_FOLLOWUP["ativacao"], "followup_1_enviado"))

        # Janela 2 — 24h a 26h após cadastro, usou mas não assinou
        inicio_24h = agora - timedelta(hours=26)
        fim_24h    = agora - timedelta(hours=24)
        for u in db.query(Usuario).filter(
            Usuario.data_cadastro >= inicio_24h,
            Usuario.data_cadastro < fim_24h,
            Usuario.consultas_gratis > 0,
            Usuario.assinante == False,
            Usuario.followup_2_enviado == False
        ).all():
            pendentes.append((u, MSGS_FOLLOWUP["reforco"], "followup_2_enviado"))

        # Janela 3 — 72h a 74h após cadastro, nunca assinou
        inicio_72h = agora - timedelta(hours=74)
        fim_72h    = agora - timedelta(hours=72)
        for u in db.query(Usuario).filter(
            Usuario.data_cadastro >= inicio_72h,
            Usuario.data_cadastro < fim_72h,
            Usuario.assinante == False,
            Usuario.followup_3_enviado == False
        ).all():
            pendentes.append((u, MSGS_FOLLOWUP["recuperacao"], "followup_3_enviado"))

        if not pendentes:
            logger.info("Follow-up: nenhum usuário pendente nesta execução")
            return

        # Embaralha para não seguir ordem fixa
        random.shuffle(pendentes)
        logger.info(f"Follow-up: {len(pendentes)} mensagem(ns) a enviar")

        for usuario, mensagem, flag in pendentes:
            try:
                await whatsapp_service.enviar_mensagem(usuario.telefone, mensagem)
                setattr(usuario, flag, True)
                db.commit()
                logger.info(f"Follow-up '{flag}' enviado: {usuario.telefone}")
            except Exception as e:
                logger.error(f"Erro ao enviar follow-up para {usuario.telefone}: {e}")
                continue

            # Delay aleatório entre 2 e 7 minutos — evita padrão detectável
            delay = random.randint(120, 420)
            logger.info(f"Aguardando {delay}s antes do próximo envio")
            await asyncio.sleep(delay)

    except Exception as e:
        logger.error(f"Erro no job de follow-up: {e}")
    finally:
        db.close()


def iniciar_scheduler(app):
    """Registra e inicia o scheduler de follow-up junto ao ciclo de vida do FastAPI."""
    scheduler = AsyncIOScheduler()
    scheduler.add_job(_checar_e_enviar, "interval", hours=2)
    scheduler.start()
    logger.info("Scheduler de follow-up iniciado (intervalo: 2h)")
