"""Serviço de Chamados (HelpDesk TI em microsserviços).

Dono das tabelas de chamados e comentários. Para conferir técnico e equipamento, chama os
serviços de Usuários e Inventário por HTTP (com timeout e repasse do token). Se algum deles
estiver fora do ar, responde 503 com uma mensagem clara; listar e consultar chamados continua
funcionando, porque não depende de ninguém.
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import clientes, dados_exemplo
from app.chamados.rotas import router as chamados_router
from app.config import DOCS_ATIVA
from app.database import Base, SessionLocal, engine, get_db
from app.erros import NaoEncontrado, RegraDeNegocio, SemPermissao, ServicoIndisponivel
from app.eventos import get_publicador
from app.seguranca_http import CabecalhosDeSeguranca

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    """Cria as tabelas e, se pedido, os dados de exemplo ao iniciar; fecha o cliente HTTP ao sair."""
    Base.metadata.create_all(engine)
    if (os.getenv("DADOS_EXEMPLO") or "1") == "1":
        with SessionLocal() as db:
            dados_exemplo.carregar(db, get_publicador())
    yield
    clientes.fechar_http()


app = FastAPI(
    title="HelpDesk TI · Serviço de Chamados", version="3.0.0", lifespan=ciclo_de_vida,
    docs_url="/docs" if DOCS_ATIVA else None, redoc_url=None,
    openapi_url="/openapi.json" if DOCS_ATIVA else None,
)
app.add_middleware(CabecalhosDeSeguranca)

app.include_router(chamados_router)


@app.exception_handler(NaoEncontrado)
def tratar_nao_encontrado(request: Request, erro: NaoEncontrado):
    return JSONResponse(status_code=404, content={"detail": str(erro)})


@app.exception_handler(RegraDeNegocio)
def tratar_regra(request: Request, erro: RegraDeNegocio):
    return JSONResponse(status_code=422, content={"detail": str(erro)})


@app.exception_handler(SemPermissao)
def tratar_sem_permissao(request: Request, erro: SemPermissao):
    return JSONResponse(status_code=403, content={"detail": str(erro)})


@app.exception_handler(ServicoIndisponivel)
def tratar_servico_indisponivel(request: Request, erro: ServicoIndisponivel):
    # 503 com mensagem clara; o motivo técnico já foi para o log em app/clientes.py
    return JSONResponse(status_code=503, content={"detail": str(erro)}, headers={"Retry-After": "5"})


@app.exception_handler(IntegrityError)
def tratar_conflito(request: Request, erro: IntegrityError):
    # Não expõe detalhes do banco na resposta
    return JSONResponse(status_code=409, content={"detail": "O registro conflita com outro já existente."})


@app.get("/saude", tags=["Saúde"])
def saude(db: Session = Depends(get_db)):
    """Sem login. Confere só o banco DESTE serviço: o Chamados está saudável mesmo que os outros caiam."""
    db.execute(text("SELECT 1"))
    return {"servico": "chamados", "status": "ok"}
