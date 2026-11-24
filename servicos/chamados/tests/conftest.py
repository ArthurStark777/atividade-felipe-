import os
import tempfile
from datetime import datetime, timedelta, timezone

# As variáveis precisam existir ANTES de importar a aplicação
os.environ["JWT_SEGREDO"] = "segredo-so-para-testes-com-mais-de-32-caracteres"
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "teste.db")
os.environ["DADOS_EXEMPLO"] = "0"

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import config
from app.clientes import get_cliente_inventario, get_cliente_usuarios
from app.database import Base, get_db
from app.erros import NaoEncontrado, RegraDeNegocio, ServicoIndisponivel
from app.eventos import get_publicador
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


# ---------- versões falsas dos outros serviços (sem rede) ----------

class InventarioFalso:
    """Faz o papel do serviço de Inventário. `fora = True` simula o serviço fora do ar."""

    def __init__(self):
        self.ativos = {1: {"id": 1, "patrimonio": "PAT-1"}}
        self.fora = False
        self.tokens_recebidos = []

    def obter_ativo(self, ativo_id, token):
        self.tokens_recebidos.append(token)
        if self.fora:
            raise ServicoIndisponivel("Inventário", "teste")
        if ativo_id not in self.ativos:
            raise NaoEncontrado(f"Ativo {ativo_id} não encontrado.")
        return self.ativos[ativo_id]


class UsuariosFalso:
    """Faz o papel do serviço de Usuários."""

    def __init__(self):
        self.perfis = {1: "admin", 2: "solicitante", 3: "solicitante", 4: "tecnico", 5: "tecnico"}
        self.fora = False
        self.tokens_recebidos = []

    def obter_tecnico(self, usuario_id, token):
        self.tokens_recebidos.append(token)
        if self.fora:
            raise ServicoIndisponivel("Usuários", "teste")
        if usuario_id not in self.perfis:
            raise NaoEncontrado(f"Usuário {usuario_id} não encontrado.")
        if self.perfis[usuario_id] != "tecnico":
            raise RegraDeNegocio(f"Usuário {usuario_id} não é técnico.")
        return {"id": usuario_id, "perfil": "tecnico"}


class PublicadorFalso:
    """Guarda os eventos em uma lista. `falhar = True` simula a fila fora do ar."""

    def __init__(self):
        self.publicados = []
        self.falhar = False

    def publicar(self, tipo, dados):
        if self.falhar:
            return False
        self.publicados.append((tipo, dados))
        return True


@pytest.fixture
def inventario():
    return InventarioFalso()


@pytest.fixture
def usuarios():
    return UsuariosFalso()


@pytest.fixture
def eventos():
    return PublicadorFalso()


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
def cliente(sessao, inventario, usuarios, eventos):
    app.dependency_overrides[get_cliente_inventario] = lambda: inventario
    app.dependency_overrides[get_cliente_usuarios] = lambda: usuarios
    app.dependency_overrides[get_publicador] = lambda: eventos
    with TestClient(app) as c:
        yield c


@pytest.fixture
def contas():
    """Cabeçalhos de login prontos. Ids: admin=1, ana=2, bia=3 (solicitantes), carla=4 (técnica)."""
    ids = {"admin": (1, "admin"), "ana": (2, "solicitante"), "bia": (3, "solicitante"), "carla": (4, "tecnico")}
    return {nome: {"headers": cabecalho(i, perfil), "id": i} for nome, (i, perfil) in ids.items()}


@pytest.fixture
def ativo():
    return {"id": 1}
