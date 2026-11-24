"""Regras de notificações: transforma eventos dos chamados em avisos para as pessoas certas."""
import logging
from datetime import datetime

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.notificacoes.modelos import Notificacao

log = logging.getLogger("helpdesk.notificacoes")


class EventoInvalido(Exception):
    """O evento está malformado: repetir não adianta, então ele é descartado (com aviso no log)."""


# ---------- formato dos eventos (contrato com o serviço de Chamados) ----------

class Envelope(BaseModel):
    id: str
    tipo: str
    ocorrido_em: datetime
    dados: dict


class ChamadoAberto(BaseModel):
    chamado_id: int
    solicitante_id: int
    prazo_sla: datetime


class ChamadoAtribuido(BaseModel):
    chamado_id: int
    tecnico_id: int


class ChamadoResolvido(BaseModel):
    chamado_id: int
    solicitante_id: int


def _aberto(d: ChamadoAberto) -> tuple[int, str]:
    return d.solicitante_id, f"Seu chamado #{d.chamado_id} foi aberto. Prazo: {d.prazo_sla:%d/%m %H:%M}."


def _atribuido(d: ChamadoAtribuido) -> tuple[int, str]:
    return d.tecnico_id, f"O chamado #{d.chamado_id} foi atribuído a você."


def _resolvido(d: ChamadoResolvido) -> tuple[int, str]:
    return d.solicitante_id, f"Seu chamado #{d.chamado_id} foi resolvido. Confirme se está tudo certo."


# tipo do evento -> (formato dos dados, quem avisar e o que dizer)
REGRAS = {
    "ChamadoAberto": (ChamadoAberto, _aberto),
    "ChamadoAtribuido": (ChamadoAtribuido, _atribuido),
    "ChamadoResolvido": (ChamadoResolvido, _resolvido),
}


# ---------- operações ----------

def notificar(db: Session, tipo: str, destinatario_id: int, mensagem: str, evento_id: str | None = None) -> Notificacao:
    """Registra um aviso. No mundo real, aqui seria enviado um e-mail ou SMS."""
    aviso = Notificacao(tipo=tipo, destinatario_id=destinatario_id, mensagem=mensagem,
                        criada_em=datetime.now(), evento_id=evento_id)
    db.add(aviso)
    db.commit()
    db.refresh(aviso)
    return aviso


def tratar_evento(db: Session, bruto: dict) -> Notificacao | None:
    """Cria o aviso correspondente a um evento. Devolve None se o evento foi ignorado ou já tratado.

    Seguro para repetição: o mesmo evento (mesmo id) nunca gera dois avisos.
    """
    try:
        evento = Envelope.model_validate(bruto)
    except ValidationError as erro:
        raise EventoInvalido(f"envelope inválido: {erro.error_count()} erro(s)") from erro

    regra = REGRAS.get(evento.tipo)
    if regra is None:
        log.info("Evento %s ignorado (tipo desconhecido: %s)", evento.id, evento.tipo)
        return None
    if db.scalar(select(Notificacao.id).where(Notificacao.evento_id == evento.id)) is not None:
        log.info("Evento %s já tratado; ignorando a repetição", evento.id)
        return None

    modelo, montar = regra
    try:
        dados = modelo.model_validate(evento.dados)
    except ValidationError as erro:
        raise EventoInvalido(f"dados de {evento.tipo} inválidos: {erro.error_count()} erro(s)") from erro
    destinatario_id, mensagem = montar(dados)
    try:
        aviso = notificar(db, evento.tipo, destinatario_id, mensagem, evento.id)
    except IntegrityError:  # o mesmo evento chegou ao mesmo tempo por outro caminho
        db.rollback()
        return None
    log.info("Evento %s recebido: aviso criado para o usuário %s (%s)", evento.tipo, destinatario_id, evento.id)
    return aviso


def listar(db: Session, destinatario_id: int | None = None) -> list[Notificacao]:
    consulta = select(Notificacao).order_by(Notificacao.id)
    if destinatario_id:
        consulta = consulta.where(Notificacao.destinatario_id == destinatario_id)
    return list(db.scalars(consulta))
