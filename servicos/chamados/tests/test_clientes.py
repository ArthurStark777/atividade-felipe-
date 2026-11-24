"""Clientes HTTP: timeout, falhas de rede e repasse do token (com um servidor de mentira)."""
import httpx
import pytest

from app import config
from app.clientes import ClienteInventario, ClienteUsuarios, fechar_http, http_compartilhado
from app.erros import NaoEncontrado, RegraDeNegocio, ServicoIndisponivel


def cliente_com(handler, classe=ClienteInventario):
    """Cria um cliente cujo 'servidor' é a função `handler` (nenhuma rede é usada)."""
    return classe("http://servico:8000", httpx.Client(transport=httpx.MockTransport(handler)))


def levanta(erro):
    def handler(request):
        raise erro
    return handler


def test_ativo_encontrado_e_token_repassado():
    vistos = []

    def handler(request):
        vistos.append(request)
        return httpx.Response(200, json={"id": 7, "patrimonio": "PAT-7"})

    ativo = cliente_com(handler).obter_ativo(7, "tok123")
    assert ativo["patrimonio"] == "PAT-7"
    assert str(vistos[0].url) == "http://servico:8000/ativos/7"
    assert vistos[0].headers["authorization"] == "Bearer tok123"


def test_ativo_inexistente_vira_nao_encontrado():
    with pytest.raises(NaoEncontrado):
        cliente_com(lambda r: httpx.Response(404, json={"detail": "x"})).obter_ativo(9, "t")


@pytest.mark.parametrize("erro", [
    httpx.ConnectTimeout("lento"), httpx.ReadTimeout("lento"),          # timeout
    httpx.ConnectError("recusou"), httpx.ReadError("caiu"),             # serviço fora do ar / conexão cortada
])
def test_falhas_de_rede_viram_servico_indisponivel(erro):
    with pytest.raises(ServicoIndisponivel) as e:
        cliente_com(levanta(erro)).obter_ativo(1, "t")
    assert "Inventário" in str(e.value)


@pytest.mark.parametrize("status", [500, 502, 503, 504, 401, 403])
def test_respostas_de_erro_do_servico_viram_indisponivel(status):
    with pytest.raises(ServicoIndisponivel):
        cliente_com(lambda r: httpx.Response(status)).obter_ativo(1, "t")


@pytest.mark.parametrize("resposta", [
    httpx.Response(200, content=b"isto nao e json"), httpx.Response(200, json=["lista"]), httpx.Response(418),
])
def test_resposta_inesperada_vira_indisponivel(resposta):
    with pytest.raises(ServicoIndisponivel):
        cliente_com(lambda r: resposta).obter_ativo(1, "t")


def test_usuario_tecnico_e_aceito():
    h = lambda r: httpx.Response(200, json={"id": 4, "nome": "Carla", "perfil": "tecnico"})
    assert cliente_com(h, ClienteUsuarios).obter_tecnico(4, "t")["id"] == 4


def test_usuario_que_nao_e_tecnico_e_recusado():
    h = lambda r: httpx.Response(200, json={"id": 2, "nome": "Ana", "perfil": "solicitante"})
    with pytest.raises(RegraDeNegocio):
        cliente_com(h, ClienteUsuarios).obter_tecnico(2, "t")


def test_usuario_inexistente():
    with pytest.raises(NaoEncontrado):
        cliente_com(lambda r: httpx.Response(404), ClienteUsuarios).obter_tecnico(9, "t")


def test_usuarios_fora_do_ar():
    with pytest.raises(ServicoIndisponivel) as e:
        cliente_com(levanta(httpx.ConnectError("x")), ClienteUsuarios).obter_tecnico(4, "t")
    assert "Usuários" in str(e.value)


def test_cliente_real_tem_timeout_configurado():
    """Sem timeout, um serviço lento travaria o Chamados. O padrão vem de config.py."""
    fechar_http()
    try:
        t = http_compartilhado().timeout
        assert t.read == config.TIMEOUT_SEGUNDOS and t.connect == config.TIMEOUT_CONEXAO_SEGUNDOS
        assert t.read is not None and t.read <= 10
    finally:
        fechar_http()
