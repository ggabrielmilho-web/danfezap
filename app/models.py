"""
Models SQLAlchemy para o banco de dados
Define as tabelas: usuarios, consultas e pagamentos
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, Text, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime, timedelta
from .database import Base


class Usuario(Base):
    """
    Tabela de usuários do bot
    Armazena informações de cadastro e assinatura
    """
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    telefone = Column(String(20), unique=True, nullable=False, index=True)
    nome = Column(String(100))
    data_cadastro = Column(DateTime, default=func.now())
    data_expiracao = Column(DateTime, nullable=True)
    data_pagamento = Column(Date, nullable=True)
    ativo = Column(Boolean, default=True)
    mercadopago_id = Column(String(100))

    # Novos campos para sistema de consultas
    consultas_gratis = Column(Integer, default=5)
    assinante = Column(Boolean, default=False)
    consultas_mes = Column(Integer, default=0)
    limite_consultas = Column(Integer, default=100)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relacionamentos
    consultas = relationship("Consulta", back_populates="usuario")
    pagamentos = relationship("Pagamento", back_populates="usuario")

    def __repr__(self):
        return f"<Usuario(id={self.id}, telefone={self.telefone}, ativo={self.ativo})>"

    @property
    def assinatura_ativa(self):
        """Verifica se a assinatura está ativa"""
        if not self.assinante:
            return False
        if not self.data_expiracao:
            return False
        return self.ativo and self.data_expiracao > datetime.now()

    @property
    def pode_consultar(self):
        """Verifica se pode fazer consulta (grátis ou assinante)"""
        # Não-assinante: verifica consultas grátis
        if not self.assinante:
            return self.consultas_gratis > 0

        # Assinante: verifica se não venceu e se não atingiu limite
        if self.data_expiracao and datetime.now() > self.data_expiracao:
            return False

        return self.consultas_mes < self.limite_consultas

    @property
    def consultas_disponiveis(self):
        """Retorna número de consultas disponíveis"""
        if not self.assinante:
            return self.consultas_gratis
        return self.limite_consultas - self.consultas_mes

    @property
    def dias_restantes(self):
        """Calcula quantos dias restam na assinatura"""
        if self.data_expiracao and self.data_expiracao > datetime.now():
            delta = self.data_expiracao - datetime.now()
            return delta.days
        return 0


class Consulta(Base):
    """
    Tabela de consultas de DANFE realizadas
    Registra histórico de consultas por usuário
    """
    __tablename__ = "consultas"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    chave_nfe = Column(String(44), nullable=False)
    data_consulta = Column(DateTime, default=func.now())
    sucesso = Column(Boolean)
    tentativas = Column(Integer, default=1)
    ultimo_erro = Column(Text)
    created_at = Column(DateTime, default=func.now())

    # Relacionamento
    usuario = relationship("Usuario", back_populates="consultas")

    def __repr__(self):
        return f"<Consulta(id={self.id}, chave_nfe={self.chave_nfe}, sucesso={self.sucesso})>"


class Pagamento(Base):
    """
    Tabela de pagamentos
    Registra transações de assinatura via Mercado Pago
    """
    __tablename__ = "pagamentos"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    valor = Column(Numeric(10, 2), nullable=False)
    data_pagamento = Column(DateTime)
    id_transacao_mp = Column(String(100))
    status = Column(String(20), default='pendente')  # pendente, aprovado, rejeitado
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relacionamento
    usuario = relationship("Usuario", back_populates="pagamentos")

    def __repr__(self):
        return f"<Pagamento(id={self.id}, valor={self.valor}, status={self.status})>"
