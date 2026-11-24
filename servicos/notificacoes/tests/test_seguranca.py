"""Este serviço confere o token por conta própria."""
from datetime import timedelta

from tests.conftest import cabecalho


def test_rota_exige_login(cliente):
    r = cliente.get("/notificacoes")
    assert r.status_code == 401 and r.headers["www-authenticate"] == "Bearer"


def test_token_adulterado(cliente):
    h = cabecalho(2, "solicitante")
    h["Authorization"] += "x"
    assert cliente.get("/notificacoes", headers=h).status_code == 401


def test_token_assinado_com_outro_segredo(cliente):
    h = cabecalho(2, "solicitante", segredo="segredo-de-outra-pessoa-com-mais-de-32-caracteres")
    assert cliente.get("/notificacoes", headers=h).status_code == 401


def test_token_sem_assinatura_alg_none(cliente):
    assert cliente.get("/notificacoes", headers=cabecalho(2, "solicitante", algoritmo="none")).status_code == 401


def test_token_expirado(cliente):
    assert cliente.get("/notificacoes", headers=cabecalho(2, "solicitante", expira_em=timedelta(minutes=-1))).status_code == 401


def test_perfil_desconhecido(cliente):
    assert cliente.get("/notificacoes", headers=cabecalho(2, "superusuario")).status_code == 401
