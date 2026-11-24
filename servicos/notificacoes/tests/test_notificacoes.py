"""A API de consulta: cada pessoa vê só os próprios avisos."""
from app.notificacoes import servico
from tests.conftest import cabecalho, evento


def entregar(sessao, e):
    with sessao() as db:
        servico.tratar_evento(db, e)


def test_cada_usuario_ve_so_as_proprias_notificacoes(cliente, sessao):
    entregar(sessao, evento("ChamadoAberto", {"chamado_id": 1, "solicitante_id": 2, "prazo_sla": "2026-11-20T10:00:00"}, id="a"))
    entregar(sessao, evento("ChamadoAtribuido", {"chamado_id": 1, "tecnico_id": 4}, id="b"))
    ana = cliente.get("/notificacoes", headers=cabecalho(2, "solicitante")).json()
    carla = cliente.get("/notificacoes", headers=cabecalho(4, "tecnico")).json()
    bia = cliente.get("/notificacoes", headers=cabecalho(3, "solicitante")).json()
    assert [a["tipo"] for a in ana] == ["ChamadoAberto"]
    assert [a["tipo"] for a in carla] == ["ChamadoAtribuido"]
    assert bia == []


def test_admin_tambem_ve_so_as_proprias(cliente, sessao):
    entregar(sessao, evento("ChamadoAtribuido", {"chamado_id": 1, "tecnico_id": 4}))
    assert cliente.get("/notificacoes", headers=cabecalho(1, "admin")).json() == []


def test_formato_da_resposta(cliente, sessao):
    entregar(sessao, evento("ChamadoResolvido", {"chamado_id": 9, "solicitante_id": 2}))
    aviso = cliente.get("/notificacoes", headers=cabecalho(2, "solicitante")).json()[0]
    assert set(aviso) == {"id", "tipo", "destinatario_id", "mensagem", "criada_em"}
    assert aviso["destinatario_id"] == 2


def test_nao_existe_rota_para_criar_notificacao_pela_api(cliente):
    """Avisos nascem só de eventos: ninguém consegue criar um aviso para outra pessoa pela API."""
    r = cliente.post("/notificacoes", headers=cabecalho(1, "admin"), json={"tipo": "X", "destinatario_id": 2, "mensagem": "oi"})
    assert r.status_code == 405


def test_saude(cliente):
    r = cliente.get("/saude")
    assert r.status_code == 200
    assert r.json() == {"servico": "notificacoes", "status": "ok", "consumidor": "desligado"}
