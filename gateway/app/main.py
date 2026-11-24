"""API Gateway (HelpDesk TI em microsserviços).

O que faz:
- entrega a tela (index.html, app.js, estilo.css), no mesmo endereço de sempre;
- encaminha cada rota da API para o serviço dono dela (tabela em config.ROTAS);
- se o serviço de destino estiver fora do ar, responde 503 (ou 504 se demorar demais);
- /saude mostra quais serviços estão no ar.

O que NÃO faz: não confere token nem decide permissões. Isso é de cada serviço, de modo que
um serviço continua protegido mesmo que alguém o alcance sem passar pelo gateway.
"""
import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

import httpx
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Route

from app import config
from app.seguranca_http import CabecalhosDeSeguranca

log = logging.getLogger("helpdesk.gateway")

WEB = Path(__file__).parent / "web"
METODOS = ["GET", "POST", "PATCH", "PUT", "DELETE"]

# Só estes cabeçalhos do cliente seguem para os serviços (lista de permissão)
REPASSAR_AO_SERVICO = {"authorization", "content-type", "accept", "accept-language", "user-agent"}
# E só estes voltam para o cliente
DEVOLVER_AO_CLIENTE = {"content-type", "www-authenticate", "retry-after", "cache-control"}


def servico_da_rota(caminho: str) -> str | None:
    for prefixo, servico in config.ROTAS:
        if caminho == prefixo or caminho.startswith(prefixo + "/"):
            return servico
    return None


def caminho_suspeito(caminho: str) -> bool:
    """Recusa tentativas de "sair" da rota (/chamados/../usuarios) ou de confundir o roteamento."""
    return "\\" in caminho or "//" in caminho or any(parte in (".", "..") for parte in caminho.split("/"))


def erro(status: int, mensagem: str, **cabecalhos) -> JSONResponse:
    return JSONResponse(status_code=status, content={"detail": mensagem}, headers=cabecalhos)


async def ler_corpo(request: Request) -> bytes | None:
    """Lê o corpo respeitando o limite, MESMO sem Content-Length. Devolve None se passar do limite."""
    total, partes = 0, []
    async for pedaco in request.stream():
        total += len(pedaco)
        if total > config.TAMANHO_MAXIMO_REQUISICAO:
            return None
        partes.append(pedaco)
    return b"".join(partes)


async def encaminhar(request: Request) -> Response:
    caminho = request.url.path
    if len(caminho) > 1:
        caminho = caminho.rstrip("/")  # /chamados/ -> /chamados (evita redirecionamento para o endereço interno)
    servico = servico_da_rota(caminho)
    if servico is None or caminho_suspeito(caminho):
        return erro(404, "Rota não encontrada.")

    corpo = await ler_corpo(request)
    if corpo is None:
        return erro(413, "Requisição grande demais.")

    cabecalhos = {k: v for k, v in request.headers.items() if k in REPASSAR_AO_SERVICO}
    # Quem fez a chamada, para o limite de tentativas de login. Sobrescreve o que o cliente mandou
    # (o gateway é a borda: não se confia em X-Forwarded-For vindo de fora).
    cabecalhos["X-Forwarded-For"] = request.client.host if request.client else "desconhecido"
    cabecalhos["X-Request-ID"] = uuid.uuid4().hex

    url = config.SERVICOS[servico] + quote(caminho, safe="/:@!$&'()*+,;=-._~")
    if request.url.query:
        url += "?" + request.url.query

    nome = config.NOMES[servico]
    try:
        resposta = await request.app.state.http.request(request.method, url, content=corpo or None, headers=cabecalhos)
    except (httpx.ReadTimeout, httpx.WriteTimeout):
        log.warning("%s demorou demais: %s %s", nome, request.method, caminho)
        return erro(504, f"O serviço de {nome} demorou demais para responder.")
    except httpx.HTTPError as e:  # sem conexão, recusou, DNS (serviço parado), tempo de conexão...
        log.warning("%s indisponível: %s %s (%s)", nome, request.method, caminho, type(e).__name__)
        return erro(503, f"O serviço de {nome} está indisponível no momento. Tente novamente em instantes.",
                    **{"Retry-After": "5"})

    saida = {k: v for k, v in resposta.headers.items() if k in DEVOLVER_AO_CLIENTE}
    return Response(content=resposta.content, status_code=resposta.status_code, headers=saida)


async def saude(request: Request) -> JSONResponse:
    """Mostra quais serviços estão no ar. Responde 200 mesmo com serviço fora: é o gateway que está de pé."""
    async def checar(nome: str, base: str) -> tuple[str, str]:
        try:
            r = await request.app.state.http.get(base + "/saude", timeout=config.TIMEOUT_SAUDE_SEGUNDOS)
            return nome, "ok" if r.status_code == 200 else "com problemas"
        except httpx.HTTPError:
            return nome, "fora do ar"

    resultados = dict(await asyncio.gather(*(checar(n, b) for n, b in config.SERVICOS.items())))
    status = "ok" if all(v == "ok" for v in resultados.values()) else "degradado"
    return JSONResponse({"status": status, "gateway": "ok", "servicos": resultados})


async def tela_inicial(request: Request) -> FileResponse:
    return FileResponse(WEB / "index.html")


async def script(request: Request) -> FileResponse:
    return FileResponse(WEB / "app.js", media_type="text/javascript")


async def estilo(request: Request) -> FileResponse:
    return FileResponse(WEB / "estilo.css", media_type="text/css")


def criar_app(http: httpx.AsyncClient | None = None) -> Starlette:
    """Monta o gateway. Os testes passam um `http` com servidores de mentira."""

    @asynccontextmanager
    async def ciclo_de_vida(app: Starlette):
        cliente = http or httpx.AsyncClient(
            timeout=httpx.Timeout(config.TIMEOUT_SEGUNDOS, connect=config.TIMEOUT_CONEXAO_SEGUNDOS))
        app.state.http = cliente
        try:
            yield
        finally:
            if http is None:
                await cliente.aclose()

    return Starlette(
        routes=[
            Route("/", tela_inicial, methods=["GET"]),
            Route("/app.js", script, methods=["GET"]),
            Route("/estilo.css", estilo, methods=["GET"]),
            Route("/saude", saude, methods=["GET"]),
            Route("/{caminho:path}", encaminhar, methods=METODOS),
        ],
        middleware=[Middleware(CabecalhosDeSeguranca)],
        lifespan=ciclo_de_vida,
    )


app = criar_app()
