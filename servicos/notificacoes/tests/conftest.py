import os
import tempfile
from datetime import datetime, timedelta, timezone

# As variáveis precisam existir ANTES de importar a aplicação
os.environ["JWT_SEGREDO"] = "segredo-so-para-testes-com-mais-de-32-caracteres"
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "teste.db")
os.environ["CONSUMIDOR_ATIVO"] = "0"  # nos testes não há Redis: os eventos são entregues "na mão"

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import config
from app.database import Base, get_db
from app.main import app


def fazer_token(usuario_id: int, perfil: str, *, segredo: str | None = None, algoritmo: str = "HS256",
                expira_em: timedelta = timedelta(hours=1), **extra) -> str:
    """Cria um token como o serviço de Usuários criaria (aqui não existe login)."""
    agora = datetime.now(timezone.utc)
    dados = {"sub": str(usuario_id), "perfil": perfil, "iss": config.JWT_EMISSOR, "iat": agora,
             "exp": agora + expira_em, **extra}
    chave = None if algoritmo == "none" else (segredo or config.JWT_SEGREDO)
    return jwt.encode(dados, chave, algorithm=algoritmo)


def cabecalho(usuario_id: int, perfil: str, **opcoes) -> dict:
    return {"Authorization": f"Bearer {fazer_token(usuario_id, perfil, **opcoes)}"}


def evento(tipo: str, dados: dict, id: str = "evt-1") -> dict:
    """Um evento no formato que o serviço de Chamados publica."""
    return {"id": id, "tipo": tipo, "ocorrido_em": datetime.now(timezone.utc).isoformat(), "dados": dados}


@pytest.fixture
def sessao():
    """Banco novo, em memória, para cada teste."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Sessao = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def db_de_teste():
        db = Sessao()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = db_de_teste
    yield Sessao
    app.dependency_overrides.clear()


@pytest.fixture
def cliente(sessao):
    with TestClient(app) as c:
        yield c
