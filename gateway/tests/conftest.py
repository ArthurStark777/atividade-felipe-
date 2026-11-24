import httpx
import pytest
from starlette.testclient import TestClient

from app.main import criar_app


class ServicosDeMentira:
    """Faz o papel dos quatro serviços: guarda as requisições recebidas e responde como programado."""

    def __init__(self):
        self.recebidas: list[httpx.Request] = []
        self.fora: dict[str, Exception] = {}          # porta/host -> erro a lançar (serviço fora do ar)
        self.respostas: dict[str, httpx.Response] = {}  # caminho -> resposta pronta

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.recebidas.append(request)
        servico = request.url.host                     # usuarios, inventario, chamados, notificacoes
        if servico in self.fora:
            raise self.fora[servico]
        if request.url.path in self.respostas:
            return self.respostas[request.url.path]
        return httpx.Response(200, json={"servico": servico, "caminho": request.url.path})


@pytest.fixture
def servicos():
    return ServicosDeMentira()


@pytest.fixture
def cliente(servicos):
    http = httpx.AsyncClient(transport=httpx.MockTransport(servicos))
    with TestClient(criar_app(http)) as c:
        yield c
