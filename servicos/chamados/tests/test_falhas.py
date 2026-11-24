"""Tratamento de falhas: o que acontece quando Usuários, Inventário ou a fila caem."""


def abrir(cliente, contas, ativo_id=1, quem="ana"):
    dados = {"titulo": "PC não liga", "descricao": "Nada acontece", "prioridade": "alta"}
    if ativo_id is not None:
        dados["ativo_id"] = ativo_id
    return cliente.post("/chamados", headers=contas[quem]["headers"], json=dados)


def test_inventario_fora_do_ar_responde_503_claro(cliente, contas, inventario):
    inventario.fora = True
    r = abrir(cliente, contas)
    assert r.status_code == 503
    assert "Inventário" in r.json()["detail"] and "indisponível" in r.json()["detail"]
    assert r.headers["retry-after"] == "5"


def test_inventario_fora_do_ar_nao_deixa_chamado_pela_metade(cliente, contas, inventario, eventos):
    inventario.fora = True
    abrir(cliente, contas)
    assert cliente.get("/chamados", headers=contas["carla"]["headers"]).json() == []
    assert eventos.publicados == []


def test_inventario_fora_do_ar_nao_afeta_chamado_sem_equipamento(cliente, contas, inventario):
    inventario.fora = True
    assert abrir(cliente, contas, ativo_id=None).status_code == 201


def test_listar_e_consultar_funcionam_com_tudo_fora(cliente, contas, inventario, usuarios):
    cid = abrir(cliente, contas).json()["id"]
    inventario.fora = usuarios.fora = True
    h = contas["carla"]["headers"]
    assert cliente.get("/chamados", headers=h).status_code == 200
    assert cliente.get(f"/chamados/{cid}", headers=h).status_code == 200
    assert cliente.get("/chamados/painel", headers=h).status_code == 200
    assert cliente.post(f"/chamados/{cid}/comentarios", headers=h, json={"texto": "oi"}).status_code == 201


def test_usuarios_fora_do_ar_atribuir_responde_503_e_nada_muda(cliente, contas, usuarios, eventos):
    cid = abrir(cliente, contas).json()["id"]
    usuarios.fora = True
    r = cliente.patch(f"/chamados/{cid}/atribuir", headers=contas["carla"]["headers"], json={"tecnico_id": contas["carla"]["id"]})
    assert r.status_code == 503 and "Usuários" in r.json()["detail"]
    chamado = cliente.get(f"/chamados/{cid}", headers=contas["carla"]["headers"]).json()
    assert chamado["status"] == "aberto" and chamado["tecnico_id"] is None
    assert [t for t, _ in eventos.publicados] == ["ChamadoAberto"]


def test_mudar_status_nao_depende_de_outros_servicos(cliente, contas, inventario, usuarios):
    cid = abrir(cliente, contas).json()["id"]
    cliente.patch(f"/chamados/{cid}/atribuir", headers=contas["carla"]["headers"], json={"tecnico_id": contas["carla"]["id"]})
    inventario.fora = usuarios.fora = True
    r = cliente.patch(f"/chamados/{cid}/status", headers=contas["carla"]["headers"], json={"status": "resolvido"})
    assert r.status_code == 200


def test_token_do_usuario_e_repassado_aos_outros_servicos(cliente, contas, inventario, usuarios):
    token_ana = contas["ana"]["headers"]["Authorization"].removeprefix("Bearer ")
    token_carla = contas["carla"]["headers"]["Authorization"].removeprefix("Bearer ")
    cid = abrir(cliente, contas).json()["id"]
    cliente.patch(f"/chamados/{cid}/atribuir", headers=contas["carla"]["headers"], json={"tecnico_id": contas["carla"]["id"]})
    assert inventario.tokens_recebidos == [token_ana]
    assert usuarios.tokens_recebidos == [token_carla]


def test_fila_de_eventos_fora_do_ar_nao_impede_abrir_chamados(cliente, contas, eventos):
    eventos.falhar = True
    r = abrir(cliente, contas)
    assert r.status_code == 201
    assert cliente.get(f"/chamados/{r.json()['id']}", headers=contas["ana"]["headers"]).status_code == 200
