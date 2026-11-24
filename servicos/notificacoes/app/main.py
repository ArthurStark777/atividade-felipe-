"""Serviço de Notificações (HelpDesk TI em microsserviços, bônus).

Não é chamado por ninguém para criar avisos: ele CONSOME eventos que o serviço de Chamados
publica. Se este serviço cair, os chamados continuam sendo abertos e os eventos esperam na fila.
"""
import logging
import threading
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import config, consumidor
from app.config import DOCS_ATIVA
from app.database import Base, SessionLocal, engine, get_db
from app.notificacoes.rotas import router as notificacoes_router
from app.seguranca_http import CabecalhosDeSeguranca

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    """Cria as tabelas e liga o consumidor de eventos em uma thread."""
    Base.metadata.create_all(engine)
    parar = threading.Event()
    app.state.thread = None
    if config.CONSUMIDOR_ATIVO:
        app.state.thread = threading.Thread(
            target=consumidor.criar(SessionLocal).executar, args=(parar,), name="consumidor-eventos", daemon=True)
        app.state.thread.start()
    yield
    parar.set()
    if app.state.thread is not None:
        app.state.thread.join(timeout=5)


app = FastAPI(
    title="HelpDesk TI · Serviço de Notificações", version="3.0.0", lifespan=ciclo_de_vida,
    docs_url="/docs" if DOCS_ATIVA else None, redoc_url=None,
    openapi_url="/openapi.json" if DOCS_ATIVA else None,
)
app.add_middleware(CabecalhosDeSeguranca)

app.include_router(notificacoes_router)


@app.get("/saude", tags=["Saúde"])
def saude(request: Request, db: Session = Depends(get_db)):
    """Sem login. Confere o banco e informa se o consumidor de eventos está rodando."""
    db.execute(text("SELECT 1"))
    thread = request.app.state.thread
    return {"servico": "notificacoes", "status": "ok",
            "consumidor": "desligado" if thread is None else ("ativo" if thread.is_alive() else "parado")}
