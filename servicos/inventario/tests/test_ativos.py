"""Inventário: cadastro, consulta e permissões."""


def novo(patrimonio="PAT-1", **extra):
    return {"patrimonio": patrimonio, "tipo": "computador", "descricao": "Desktop", "setor": "TI", **extra}


def test_tecnico_cadastra_e_consulta_ativo(cliente, contas):
    r = cliente.post("/ativos", headers=contas["carla"], json=novo())
    assert r.status_code == 201
    ativo = r.json()
    assert cliente.get(f"/ativos/{ativo['id']}", headers=contas["ana"]).json()["patrimonio"] == "PAT-1"


def test_admin_tambem_cadastra(cliente, contas):
    assert cliente.post("/ativos", headers=contas["admin"], json=novo()).status_code == 201


def test_solicitante_nao_cadastra_ativo(cliente, contas):
    assert cliente.post("/ativos", headers=contas["ana"], json=novo("PAT-9")).status_code == 403


def test_filtra_por_setor(cliente, contas):
    h = contas["carla"]
    cliente.post("/ativos", headers=h, json=novo("PAT-1", tipo="impressora", setor="RH"))
    cliente.post("/ativos", headers=h, json=novo("PAT-2", setor="TI"))
    assert len(cliente.get("/ativos", params={"setor": "RH"}, headers=h).json()) == 1
    assert len(cliente.get("/ativos", headers=h).json()) == 2


def test_ativo_inexistente(cliente, contas):
    r = cliente.get("/ativos/99", headers=contas["ana"])
    assert r.status_code == 404 and "99" in r.json()["detail"]


def test_patrimonio_repetido_e_recusado(cliente, contas):
    h = contas["carla"]
    cliente.post("/ativos", headers=h, json=novo("PAT-1"))
    assert cliente.post("/ativos", headers=h, json=novo("PAT-1")).status_code == 422


def test_campos_invalidos_ou_extras_sao_recusados(cliente, contas):
    h = contas["carla"]
    assert cliente.post("/ativos", headers=h, json=novo("com espaço")).status_code == 422
    assert cliente.post("/ativos", headers=h, json=novo("PAT-3", tipo="foguete")).status_code == 422
    assert cliente.post("/ativos", headers=h, json=novo("PAT-4", id=50)).status_code == 422
    assert cliente.post("/ativos", headers=h, json=novo("PAT-5", descricao="x" * 500)).status_code == 422


def test_requisicao_grande_demais(cliente, contas):
    corpo = '{"patrimonio": "' + "x" * 70000 + '"}'
    r = cliente.post("/ativos", headers={**contas["carla"], "Content-Type": "application/json"}, content=corpo)
    assert r.status_code == 413


def test_saude_nao_exige_login(cliente):
    r = cliente.get("/saude")
    assert r.status_code == 200 and r.json() == {"servico": "inventario", "status": "ok"}
