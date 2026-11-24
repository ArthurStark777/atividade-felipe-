"""Cadastro e consulta de usuários, permissões e validação de entrada."""


def test_admin_cria_usuario(cliente, contas):
    r = cliente.post("/usuarios", headers=contas["admin"]["headers"],
                     json={"nome": "Davi", "email": "davi@x.com", "perfil": "tecnico", "senha": "Forte1234"})
    assert r.status_code == 201
    assert "senha" not in r.json() and "senha_hash" not in r.json()


def test_email_repetido_e_recusado(cliente, contas):
    dados = {"nome": "Ana 2", "email": "ANA@x.com", "perfil": "solicitante", "senha": "Forte1234"}
    assert cliente.post("/usuarios", headers=contas["admin"]["headers"], json=dados).status_code == 422


def test_senha_fraca_e_recusada(cliente, contas):
    r = cliente.post("/usuarios", headers=contas["admin"]["headers"],
                     json={"nome": "Eva", "email": "eva@x.com", "perfil": "solicitante", "senha": "abcdefgh"})
    assert r.status_code == 422


def test_solicitante_nao_cria_usuario(cliente, contas):
    r = cliente.post("/usuarios", headers=contas["ana"]["headers"],
                     json={"nome": "Eva", "email": "eva@x.com", "perfil": "admin", "senha": "Forte1234"})
    assert r.status_code == 403


def test_campos_extras_sao_recusados(cliente, contas):
    r = cliente.post("/usuarios", headers=contas["admin"]["headers"],
                     json={"nome": "Eva", "email": "eva@x.com", "perfil": "solicitante", "senha": "Forte1234", "ativo": False})
    assert r.status_code == 422


def test_usuario_inexistente(cliente, contas):
    assert cliente.get("/usuarios/99", headers=contas["ana"]["headers"]).status_code == 404


def test_obter_usuario_devolve_so_dados_publicos(cliente, contas):
    """É este formato que o serviço de Chamados recebe ao conferir um técnico."""
    r = cliente.get(f"/usuarios/{contas['carla']['id']}", headers=contas["ana"]["headers"])
    assert r.status_code == 200
    assert set(r.json()) == {"id", "nome", "perfil"} and r.json()["perfil"] == "tecnico"


def test_lista_publica_nao_mostra_email(cliente, contas):
    lista = cliente.get("/usuarios", headers=contas["ana"]["headers"]).json()
    assert lista and all("email" not in u for u in lista)


def test_lista_filtra_por_perfil(cliente, contas):
    tecnicos = cliente.get("/usuarios", params={"perfil": "tecnico"}, headers=contas["ana"]["headers"]).json()
    assert [u["nome"] for u in tecnicos] == ["Carla"]


def test_requisicao_grande_demais(cliente, contas):
    corpo = '{"nome": "' + "x" * 70000 + '"}'
    r = cliente.post("/usuarios", headers={**contas["admin"]["headers"], "Content-Type": "application/json"}, content=corpo)
    assert r.status_code == 413


def test_saude_nao_exige_login(cliente):
    r = cliente.get("/saude")
    assert r.status_code == 200 and r.json() == {"servico": "usuarios", "status": "ok"}


def test_servico_nao_inicia_sem_segredo_valido(monkeypatch):
    """Sem segredo (ou com segredo curto) o serviço se recusa a iniciar, em vez de inventar um."""
    import importlib

    import pytest

    from app import config

    original = config.JWT_SEGREDO
    try:
        monkeypatch.setenv("JWT_SEGREDO", "curto")
        monkeypatch.delenv("JWT_SEGREDO_ARQUIVO", raising=False)
        with pytest.raises(RuntimeError):
            importlib.reload(config)
    finally:
        monkeypatch.setenv("JWT_SEGREDO", original)
        importlib.reload(config)
