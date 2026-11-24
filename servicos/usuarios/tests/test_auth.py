"""Login e conferência de token (autenticação) no serviço de Usuários."""
from datetime import datetime, timedelta, timezone

import jwt

from app import config
from tests.conftest import SENHA


def token_falso(usuario_id, perfil="admin", segredo=None, algoritmo="HS256", **extra):
    agora = datetime.now(timezone.utc)
    dados = {"sub": str(usuario_id), "perfil": perfil, "iss": config.JWT_EMISSOR, "iat": agora,
             "exp": agora + timedelta(hours=1), **extra}
    return jwt.encode(dados, segredo if algoritmo != "none" else None, algorithm=algoritmo)


def test_rotas_exigem_login(cliente, contas):
    for metodo, rota in [("get", "/usuarios"), ("get", "/usuarios/1"), ("post", "/usuarios"), ("get", "/auth/eu")]:
        assert getattr(cliente, metodo)(rota).status_code == 401, rota


def test_login_devolve_token_e_dados_do_usuario(cliente, contas):
    r = cliente.post("/auth/login", json={"email": "ana@x.com", "senha": SENHA})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["token_type"] == "bearer" and corpo["usuario"]["perfil"] == "solicitante"
    assert "senha" not in corpo["usuario"] and "senha_hash" not in corpo["usuario"]


def test_token_do_login_traz_o_perfil(cliente, contas):
    token = contas["carla"]["headers"]["Authorization"].split()[1]
    dados = jwt.decode(token, config.JWT_SEGREDO, algorithms=["HS256"], issuer=config.JWT_EMISSOR)
    assert dados["perfil"] == "tecnico" and dados["sub"] == str(contas["carla"]["id"])


def test_login_com_senha_errada(cliente, contas):
    r = cliente.post("/auth/login", json={"email": "ana@x.com", "senha": "errada123"})
    assert r.status_code == 401 and r.json()["detail"] == "E-mail ou senha inválidos."


def test_login_com_email_inexistente_tem_a_mesma_mensagem(cliente, contas):
    r = cliente.post("/auth/login", json={"email": "ninguem@x.com", "senha": "errada123"})
    assert r.status_code == 401 and r.json()["detail"] == "E-mail ou senha inválidos."


def test_bloqueio_apos_varias_senhas_erradas(cliente, contas):
    for _ in range(config.LOGIN_MAX_FALHAS):
        cliente.post("/auth/login", json={"email": "ana@x.com", "senha": "errada123"})
    # mesmo com a senha certa, fica bloqueado por um tempo
    assert cliente.post("/auth/login", json={"email": "ana@x.com", "senha": SENHA}).status_code == 429


def test_token_adulterado(cliente, contas):
    token = contas["ana"]["headers"]["Authorization"] + "x"
    assert cliente.get("/auth/eu", headers={"Authorization": token}).status_code == 401


def test_token_assinado_com_outro_segredo(cliente, contas):
    falso = token_falso(contas["admin"]["id"], segredo="segredo-de-outra-pessoa-com-mais-de-32-caracteres")
    assert cliente.get("/auth/eu", headers={"Authorization": f"Bearer {falso}"}).status_code == 401


def test_token_sem_assinatura_alg_none(cliente, contas):
    falso = token_falso(contas["admin"]["id"], algoritmo="none")
    assert cliente.get("/auth/eu", headers={"Authorization": f"Bearer {falso}"}).status_code == 401


def test_token_expirado(cliente, contas):
    antigo = datetime.now(timezone.utc) - timedelta(hours=2)
    vencido = jwt.encode({"sub": str(contas["ana"]["id"]), "perfil": "solicitante", "iss": config.JWT_EMISSOR,
                          "iat": antigo, "exp": antigo + timedelta(minutes=5)}, config.JWT_SEGREDO, algorithm="HS256")
    assert cliente.get("/auth/eu", headers={"Authorization": f"Bearer {vencido}"}).status_code == 401


def test_token_sem_perfil_ou_com_perfil_desconhecido(cliente, contas):
    agora = datetime.now(timezone.utc)
    sem_perfil = jwt.encode({"sub": str(contas["ana"]["id"]), "iss": config.JWT_EMISSOR, "iat": agora,
                             "exp": agora + timedelta(hours=1)}, config.JWT_SEGREDO, algorithm="HS256")
    estranho = token_falso(contas["ana"]["id"], perfil="superusuario", segredo=config.JWT_SEGREDO)
    for token in (sem_perfil, estranho):
        assert cliente.get("/auth/eu", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_perfil_vale_o_do_banco_e_nao_o_do_token(cliente, contas):
    """Este serviço é o dono dos usuários: um token dizendo 'admin' para a Ana não a torna admin."""
    mentiroso = token_falso(contas["ana"]["id"], perfil="admin", segredo=config.JWT_SEGREDO)
    r = cliente.post("/usuarios", headers={"Authorization": f"Bearer {mentiroso}"},
                     json={"nome": "Eva", "email": "eva@x.com", "perfil": "admin", "senha": "Forte1234"})
    assert r.status_code == 403


def test_senha_guardada_com_hash(sessao, contas):
    from app.usuarios.modelos import Usuario
    with sessao() as db:
        u = db.query(Usuario).filter_by(email="ana@x.com").one()
        assert SENHA not in u.senha_hash and u.senha_hash.startswith("scrypt$")
