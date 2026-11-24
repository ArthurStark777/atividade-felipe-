"""Regras de negócio: SLA, status, comentários e painel (as mesmas do monólito)."""
from datetime import datetime


def abrir(cliente, contas, ativo, quem="ana", prioridade="alta", **extra):
    dados = {"titulo": "PC não liga", "descricao": "Nada acontece", "prioridade": prioridade, "ativo_id": ativo["id"], **extra}
    return cliente.post("/chamados", headers=contas[quem]["headers"], json=dados)


def atribuir(cliente, contas, cid, tecnico="carla"):
    return cliente.patch(f"/chamados/{cid}/atribuir", headers=contas["carla"]["headers"],
                         json={"tecnico_id": contas[tecnico]["id"]})


def test_abrir_calcula_sla_e_publica_evento(cliente, contas, ativo, eventos):
    r = abrir(cliente, contas, ativo, prioridade="critica")
    assert r.status_code == 201
    c = r.json()
    assert c["solicitante_id"] == contas["ana"]["id"] and c["status"] == "aberto"
    horas = (datetime.fromisoformat(c["prazo_sla"]) - datetime.fromisoformat(c["criado_em"])).total_seconds() / 3600
    assert round(horas) == 4
    tipo, dados = eventos.publicados[0]
    assert tipo == "ChamadoAberto"
    assert dados["chamado_id"] == c["id"] and dados["solicitante_id"] == contas["ana"]["id"]
    assert dados["prazo_sla"] == c["prazo_sla"]


def test_sla_por_prioridade(cliente, contas, ativo):
    esperado = {"critica": 4, "alta": 8, "media": 24, "baixa": 72}
    for prioridade, horas in esperado.items():
        c = abrir(cliente, contas, ativo, prioridade=prioridade).json()
        dif = datetime.fromisoformat(c["prazo_sla"]) - datetime.fromisoformat(c["criado_em"])
        assert round(dif.total_seconds() / 3600) == horas


def test_abrir_sem_equipamento_nao_consulta_o_inventario(cliente, contas, inventario):
    r = cliente.post("/chamados", headers=contas["ana"]["headers"],
                     json={"titulo": "Sem acesso", "descricao": "Preciso de acesso", "prioridade": "baixa"})
    assert r.status_code == 201 and r.json()["ativo_id"] is None
    assert inventario.tokens_recebidos == []


def test_abrir_com_ativo_inexistente(cliente, contas, ativo):
    assert abrir(cliente, contas, ativo, ativo_id=999).status_code == 404


def test_atribuir_muda_status_e_publica_evento(cliente, contas, ativo, eventos):
    cid = abrir(cliente, contas, ativo).json()["id"]
    r = atribuir(cliente, contas, cid)
    assert r.status_code == 200 and r.json()["status"] == "em_atendimento" and r.json()["tecnico_id"] == contas["carla"]["id"]
    assert eventos.publicados[-1] == ("ChamadoAtribuido", {"chamado_id": cid, "tecnico_id": contas["carla"]["id"]})


def test_so_tecnico_pode_ser_atribuido(cliente, contas, ativo):
    cid = abrir(cliente, contas, ativo).json()["id"]
    assert atribuir(cliente, contas, cid, tecnico="ana").status_code == 422


def test_tecnico_inexistente(cliente, contas, ativo):
    cid = abrir(cliente, contas, ativo).json()["id"]
    r = cliente.patch(f"/chamados/{cid}/atribuir", headers=contas["carla"]["headers"], json={"tecnico_id": 999})
    assert r.status_code == 404


def test_nao_atribui_chamado_resolvido(cliente, contas, ativo):
    cid = abrir(cliente, contas, ativo).json()["id"]
    atribuir(cliente, contas, cid)
    cliente.patch(f"/chamados/{cid}/status", headers=contas["carla"]["headers"], json={"status": "resolvido"})
    assert atribuir(cliente, contas, cid).status_code == 422


def test_fluxo_completo_de_status(cliente, contas, ativo, eventos):
    cid = abrir(cliente, contas, ativo).json()["id"]
    tec = contas["carla"]["headers"]
    atribuir(cliente, contas, cid)
    assert cliente.patch(f"/chamados/{cid}/status", headers=tec, json={"status": "resolvido"}).status_code == 200
    assert eventos.publicados[-1] == ("ChamadoResolvido", {"chamado_id": cid, "solicitante_id": contas["ana"]["id"]})
    # o próprio solicitante confirma e fecha
    r = cliente.patch(f"/chamados/{cid}/status", headers=contas["ana"]["headers"], json={"status": "fechado"})
    assert r.json()["status"] == "fechado"
    assert [t for t, _ in eventos.publicados] == ["ChamadoAberto", "ChamadoAtribuido", "ChamadoResolvido"]


def test_solicitante_reabre_chamado_resolvido(cliente, contas, ativo):
    cid = abrir(cliente, contas, ativo).json()["id"]
    atribuir(cliente, contas, cid)
    cliente.patch(f"/chamados/{cid}/status", headers=contas["carla"]["headers"], json={"status": "resolvido"})
    r = cliente.patch(f"/chamados/{cid}/status", headers=contas["ana"]["headers"], json={"status": "em_atendimento"})
    assert r.status_code == 200 and r.json()["status"] == "em_atendimento"


def test_transicao_invalida(cliente, contas, ativo):
    cid = abrir(cliente, contas, ativo).json()["id"]
    r = cliente.patch(f"/chamados/{cid}/status", headers=contas["carla"]["headers"], json={"status": "fechado"})
    assert r.status_code == 422


def test_iniciar_atendimento_sem_tecnico(cliente, contas, ativo):
    cid = abrir(cliente, contas, ativo).json()["id"]
    r = cliente.patch(f"/chamados/{cid}/status", headers=contas["carla"]["headers"], json={"status": "em_atendimento"})
    assert r.status_code == 422


def test_comentar_usa_o_usuario_logado(cliente, contas, ativo):
    cid = abrir(cliente, contas, ativo).json()["id"]
    r = cliente.post(f"/chamados/{cid}/comentarios", headers=contas["carla"]["headers"], json={"texto": "Verificando a fonte."})
    assert r.status_code == 201 and r.json()["autor_id"] == contas["carla"]["id"]
    assert len(cliente.get(f"/chamados/{cid}", headers=contas["ana"]["headers"]).json()["comentarios"]) == 1


def test_chamado_fechado_nao_recebe_comentarios(cliente, contas, ativo):
    cid = abrir(cliente, contas, ativo).json()["id"]
    atribuir(cliente, contas, cid)
    cliente.patch(f"/chamados/{cid}/status", headers=contas["carla"]["headers"], json={"status": "resolvido"})
    cliente.patch(f"/chamados/{cid}/status", headers=contas["ana"]["headers"], json={"status": "fechado"})
    r = cliente.post(f"/chamados/{cid}/comentarios", headers=contas["ana"]["headers"], json={"texto": "ainda aqui"})
    assert r.status_code == 422


def test_painel(cliente, contas, ativo):
    abrir(cliente, contas, ativo)
    abrir(cliente, contas, ativo, prioridade="baixa")
    p = cliente.get("/chamados/painel", headers=contas["carla"]["headers"]).json()
    assert p["total"] == 2 and p["por_status"] == {"aberto": 2} and p["atrasados"] == 0


def test_listar_com_filtros(cliente, contas, ativo):
    c1 = abrir(cliente, contas, ativo).json()["id"]
    abrir(cliente, contas, ativo)
    atribuir(cliente, contas, c1)
    tec = contas["carla"]["headers"]
    assert len(cliente.get("/chamados", headers=tec).json()) == 2
    assert [c["id"] for c in cliente.get("/chamados", params={"status": "em_atendimento"}, headers=tec).json()] == [c1]
    assert [c["id"] for c in cliente.get("/chamados", params={"tecnico_id": contas["carla"]["id"]}, headers=tec).json()] == [c1]


def test_saude_nao_exige_login_nem_os_outros_servicos(cliente, inventario, usuarios):
    inventario.fora = usuarios.fora = True
    r = cliente.get("/saude")
    assert r.status_code == 200 and r.json() == {"servico": "chamados", "status": "ok"}
