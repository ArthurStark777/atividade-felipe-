"""Chamadas HTTP aos outros serviços.

No monólito, `usuarios.obter_tecnico(db, id)` e `inventario.obter(db, id)` eram chamadas de
função. Agora são chamadas pela rede, e a rede falha. Por isso:

- toda chamada tem TIMEOUT (nunca espera para sempre);
- o token do usuário é REPASSADO no cabeçalho Authorization (o outro serviço confere de novo);
- falha de conexão, timeout ou erro 5xx viram `ServicoIndisponivel` (o Chamados responde 503);
- "não existe" (404) continua sendo 404, como no monólito.
"""
import logging

import httpx

from app import config
from app.erros import NaoEncontrado, RegraDeNegocio, ServicoIndisponivel

log = logging.getLogger("helpdesk.chamados")

_http: httpx.Client | None = None


def http_compartilhado() -> httpx.Client:
    """Um cliente HTTP por processo (reaproveita conexões). httpx.Client é seguro entre threads."""
    global _http
    if _http is None:
        _http = httpx.Client(timeout=httpx.Timeout(config.TIMEOUT_SEGUNDOS, connect=config.TIMEOUT_CONEXAO_SEGUNDOS))
    return _http


def fechar_http() -> None:
    global _http
    if _http is not None:
        _http.close()
        _http = None


class _ClienteBase:
    nome = ""  # nome do serviço, usado na mensagem de erro

    def __init__(self, base_url: str, http: httpx.Client | None = None):
        self.base_url = base_url.rstrip("/")
        self._http = http

    @property
    def http(self) -> httpx.Client:
        return self._http or http_compartilhado()

    def _get(self, caminho: str, token: str) -> httpx.Response:
        try:
            resposta = self.http.get(self.base_url + caminho, headers={"Authorization": f"Bearer {token}"})
        except httpx.TimeoutException as erro:
            log.warning("Serviço de %s: tempo esgotado em GET %s", self.nome, caminho)
            raise ServicoIndisponivel(self.nome, "tempo esgotado") from erro
        except httpx.HTTPError as erro:
            log.warning("Serviço de %s: sem conexão em GET %s (%s)", self.nome, caminho, type(erro).__name__)
            raise ServicoIndisponivel(self.nome, "sem conexão") from erro
        # 5xx: o serviço está com problema. 401/403: algo errado entre os serviços (segredo diferente?),
        # e o usuário não tem o que fazer a respeito.
        if resposta.status_code >= 500 or resposta.status_code in (401, 403):
            log.warning("Serviço de %s respondeu %s em GET %s", self.nome, resposta.status_code, caminho)
            raise ServicoIndisponivel(self.nome, f"resposta {resposta.status_code}")
        return resposta

    def _json(self, resposta: httpx.Response) -> dict:
        if resposta.status_code != 200:
            raise ServicoIndisponivel(self.nome, f"resposta inesperada ({resposta.status_code})")
        try:
            dados = resposta.json()
        except ValueError as erro:
            raise ServicoIndisponivel(self.nome, "resposta inválida") from erro
        if not isinstance(dados, dict):
            raise ServicoIndisponivel(self.nome, "resposta inválida")
        return dados


class ClienteInventario(_ClienteBase):
    nome = "Inventário"

    def obter_ativo(self, ativo_id: int, token: str) -> dict:
        """GET /ativos/{id}. Lança NaoEncontrado se o equipamento não existe."""
        resposta = self._get(f"/ativos/{ativo_id}", token)
        if resposta.status_code == 404:
            raise NaoEncontrado(f"Ativo {ativo_id} não encontrado.")
        return self._json(resposta)


class ClienteUsuarios(_ClienteBase):
    nome = "Usuários"

    def obter_tecnico(self, usuario_id: int, token: str) -> dict:
        """GET /usuarios/{id}. Lança NaoEncontrado se não existe e RegraDeNegocio se não é técnico."""
        resposta = self._get(f"/usuarios/{usuario_id}", token)
        if resposta.status_code == 404:
            raise NaoEncontrado(f"Usuário {usuario_id} não encontrado.")
        usuario = self._json(resposta)
        if usuario.get("perfil") != "tecnico":
            raise RegraDeNegocio(f"Usuário {usuario_id} não é técnico.")
        return usuario


# Fornecedores usados pelo FastAPI (Depends). Os testes os substituem por versões falsas.
def get_cliente_inventario() -> ClienteInventario:
    return ClienteInventario(config.INVENTARIO_URL)


def get_cliente_usuarios() -> ClienteUsuarios:
    return ClienteUsuarios(config.USUARIOS_URL)
