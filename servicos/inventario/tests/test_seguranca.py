"""Este serviço confere o token por conta própria, sem perguntar ao serviço de Usuários."""
from datetime import timedelta

import jwt

from tests.conftest import cabecalho, fazer_token


def test_rotas_exigem_login(cliente):
    for metodo, rota in [("get", "/ativos"), ("get", "/ativos/1"), ("post", "/ativos")]:
        r = getattr(cliente, metodo)(rota)
        assert r.status_code == 401, rota
        assert r.headers["www-authenticate"] == "Bearer"


def test_esquema_de_autorizacao_errado(cliente):
    assert cliente.get("/ativos", headers={"Authorization": "Basic YTpi"}).status_code == 401


def test_token_adulterado(cliente):
    h = cabecalho(4, "tecnico")
    h["Authorization"] += "x"
    assert cliente.get("/ativos", headers=h).status_code == 401


def test_token_assinado_com_outro_segredo(cliente):
    h = cabecalho(1, "admin", segredo="segredo-de-outra-pessoa-com-mais-de-32-caracteres")
    assert cliente.get("/ativos", headers=h).status_code == 401


def test_token_sem_assinatura_alg_none(cliente):
    assert cliente.get("/ativos", headers=cabecalho(1, "admin", algoritmo="none")).status_code == 401


def test_token_expirado(cliente):
    assert cliente.get("/ativos", headers=cabecalho(2, "solicitante", expira_em=timedelta(minutes=-5))).status_code == 401


def test_token_de_outro_emissor(cliente):
    h = cabecalho(1, "admin", iss="outro-sistema")
    assert cliente.get("/ativos", headers=h).status_code == 401


def test_token_sem_perfil_ou_com_perfil_desconhecido(cliente, sessao):
    import time

    from app import config

    sem_perfil = jwt.encode({"sub": "2", "iss": config.JWT_EMISSOR, "iat": int(time.time()), "exp": int(time.time()) + 600},
                            config.JWT_SEGREDO, algorithm="HS256")
    assert cliente.get("/ativos", headers={"Authorization": f"Bearer {sem_perfil}"}).status_code == 401
    assert cliente.get("/ativos", headers=cabecalho(2, "superusuario")).status_code == 401


def test_token_valido_de_solicitante_pode_consultar_mas_nao_cadastrar(cliente):
    h = cabecalho(2, "solicitante")
    assert cliente.get("/ativos", headers=h).status_code == 200
    r = cliente.post("/ativos", headers=h, json={"patrimonio": "PAT-9", "tipo": "outro", "descricao": "X", "setor": "TI"})
    assert r.status_code == 403
