"""O gateway: tela, roteamento, repasse, falhas e segurança (os serviços são de mentira)."""
import httpx
import pytest

from app.main import caminho_suspeito, servico_da_rota


# ---------- a tela ----------

def test_tela_e_arquivos_estaticos_pelo_gateway(cliente):
    r = cliente.get("/")
    assert r.status_code == 200 and "HelpDesk TI" in r.text and "microsserviços" in r.text
    assert cliente.get("/app.js").headers["content-type"].startswith("text/javascript")
    assert cliente.get("/estilo.css").headers["content-type"].startswith("text/css")


def test_tela_escapa_o_html():
    from pathlib import Path
    js = (Path(__file__).parent.parent / "app" / "web" / "app.js").read_text()
    assert "const esc =" in js and "onclick" not in js


def test_tela_usa_o_mesmo_endereco_do_gateway():
    from pathlib import Path
    js = (Path(__file__).parent.parent / "app" / "web" / "app.js").read_text()
    assert 'const API = "";' in js  # chamadas relativas: o navegador fala só com o gateway


def test_cabecalhos_de_seguranca(cliente):
    r = cliente.get("/")
    assert "script-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "no-referrer"


def test_respostas_da_api_tambem_levam_os_cabecalhos_e_nao_ficam_em_cache(cliente):
    r = cliente.get("/chamados", headers={"Authorization": "Bearer abc"})
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "DENY"
    assert r.headers["cache-control"] == "no-store"


# ---------- roteamento ----------

@pytest.mark.parametrize("caminho, servico", [
    ("/auth/login", "usuarios"), ("/auth/eu", "usuarios"), ("/usuarios", "usuarios"), ("/usuarios/3", "usuarios"),
    ("/ativos", "inventario"), ("/ativos/1", "inventario"),
    ("/chamados", "chamados"), ("/chamados/painel", "chamados"), ("/chamados/5/atribuir", "chamados"),
    ("/chamados/5/comentarios", "chamados"),
    ("/notificacoes", "notificacoes"),
])
def test_cada_rota_vai_para_o_servico_certo(cliente, servicos, caminho, servico):
    r = cliente.get(caminho)
    assert r.status_code == 200
    assert r.json() == {"servico": servico, "caminho": caminho}
    assert servicos.recebidas[-1].url.host == servico


@pytest.mark.parametrize("caminho", [
    "/admin", "/docs", "/openapi.json", "/usuariosx", "/chamadosx/1", "/authx", "/saude/usuarios", "/segredo", "/.env",
])
def test_so_o_que_esta_na_tabela_e_encaminhado(cliente, servicos, caminho):
    assert cliente.get(caminho).status_code == 404
    assert servicos.recebidas == []


def test_servico_da_rota():
    assert servico_da_rota("/chamados") == "chamados" and servico_da_rota("/chamados/1") == "chamados"
    assert servico_da_rota("/chamadosx") is None and servico_da_rota("/") is None


@pytest.mark.parametrize("caminho", ["/chamados/../usuarios", "/chamados/./1", "/chamados//1", "/chamados\\1", "/a/.."])
def test_caminhos_suspeitos_sao_recusados(caminho):
    assert caminho_suspeito(caminho)


def test_caminho_com_pontos_codificados_nao_escapa_da_rota(cliente, servicos):
    r = cliente.get("/chamados/%2e%2e/usuarios")
    assert r.status_code == 404 and servicos.recebidas == []


def test_barra_no_final_nao_gera_redirecionamento_para_endereco_interno(cliente, servicos):
    r = cliente.get("/chamados/", follow_redirects=False)
    assert r.status_code == 200 and servicos.recebidas[-1].url.path == "/chamados"


# ---------- repasse ----------

def test_repassa_metodo_corpo_query_e_token(cliente, servicos):
    r = cliente.patch("/chamados/5/status?x=1&y=a%20b", json={"status": "resolvido"},
                      headers={"Authorization": "Bearer meu.token.jwt"})
    assert r.status_code == 200
    visto = servicos.recebidas[-1]
    assert visto.method == "PATCH" and visto.url.path == "/chamados/5/status"
    assert visto.url.query == b"x=1&y=a%20b"
    assert visto.headers["authorization"] == "Bearer meu.token.jwt"
    assert visto.headers["content-type"] == "application/json"
    assert visto.read() == b'{"status":"resolvido"}'


def test_so_repassa_cabecalhos_permitidos(cliente, servicos):
    cliente.get("/chamados", headers={"Cookie": "sessao=1", "X-Interno": "x", "Authorization": "Bearer t"})
    visto = servicos.recebidas[-1]
    assert "cookie" not in visto.headers and "x-interno" not in visto.headers
    assert visto.headers["host"] == "chamados:8000"  # o Host é do serviço, não o do cliente


def test_ip_do_cliente_nao_pode_ser_forjado(cliente, servicos):
    """O limite de tentativas de login usa X-Forwarded-For: o gateway define sozinho, ignorando o do cliente."""
    cliente.post("/auth/login", json={"email": "a@b.com", "senha": "x"}, headers={"X-Forwarded-For": "6.6.6.6"})
    visto = servicos.recebidas[-1]
    assert visto.headers["x-forwarded-for"] == "testclient" and "6.6.6.6" not in visto.headers["x-forwarded-for"]


def test_cada_requisicao_recebe_um_id_proprio(cliente, servicos):
    cliente.get("/chamados")
    cliente.get("/chamados")
    ids = {r.headers["x-request-id"] for r in servicos.recebidas}
    assert len(ids) == 2


def test_devolve_status_corpo_e_cabecalhos_do_servico(cliente, servicos):
    servicos.respostas["/chamados"] = httpx.Response(
        401, json={"detail": "Faça login para continuar."},
        headers={"WWW-Authenticate": "Bearer", "Set-Cookie": "x=1", "Server": "interno/1.0"})
    r = cliente.get("/chamados")
    assert r.status_code == 401 and r.json() == {"detail": "Faça login para continuar."}
    assert r.headers["www-authenticate"] == "Bearer"
    assert "set-cookie" not in r.headers and "server" not in r.headers  # detalhes internos não vazam


@pytest.mark.parametrize("status", [201, 204, 403, 404, 409, 422, 429, 500])
def test_repassa_qualquer_status_do_servico(cliente, servicos, status):
    servicos.respostas["/chamados"] = httpx.Response(status)
    assert cliente.get("/chamados").status_code == status


# ---------- falhas ----------

def test_servico_fora_do_ar_vira_503_claro(cliente, servicos):
    servicos.fora["inventario"] = httpx.ConnectError("recusou")
    r = cliente.get("/ativos")
    assert r.status_code == 503
    assert "Inventário" in r.json()["detail"] and "indisponível" in r.json()["detail"]
    assert r.headers["retry-after"] == "5"


def test_servico_parado_nao_derruba_os_outros(cliente, servicos):
    servicos.fora["inventario"] = httpx.ConnectError("recusou")
    assert cliente.get("/ativos").status_code == 503
    assert cliente.get("/usuarios").status_code == 200
    assert cliente.get("/chamados").status_code == 200
    assert cliente.get("/").status_code == 200  # a tela continua


def test_tempo_de_conexao_esgotado_vira_503(cliente, servicos):
    servicos.fora["chamados"] = httpx.ConnectTimeout("lento")
    assert cliente.get("/chamados").status_code == 503


def test_servico_que_demora_para_responder_vira_504(cliente, servicos):
    servicos.fora["chamados"] = httpx.ReadTimeout("lento")
    r = cliente.get("/chamados")
    assert r.status_code == 504 and "demorou" in r.json()["detail"]


def test_erro_5xx_do_proprio_servico_e_repassado(cliente, servicos):
    servicos.respostas["/chamados"] = httpx.Response(503, json={"detail": "O serviço de Inventário está indisponível."})
    r = cliente.get("/chamados")
    assert r.status_code == 503 and "Inventário" in r.json()["detail"]


# ---------- limites ----------

def test_corpo_grande_demais_com_content_length(cliente, servicos):
    r = cliente.post("/chamados", content=b"x" * 70000, headers={"Content-Type": "application/json"})
    assert r.status_code == 413 and servicos.recebidas == []


def test_corpo_grande_demais_sem_content_length(cliente, servicos):
    """Envio em pedaços (sem Content-Length) também é barrado, sem juntar tudo na memória."""
    def pedacos():
        for _ in range(80):
            yield b"x" * 1024
    r = cliente.post("/chamados", content=pedacos(), headers={"Content-Type": "application/json"})
    assert r.status_code == 413 and servicos.recebidas == []


def test_metodo_nao_permitido(cliente):
    assert cliente.request("TRACE", "/chamados").status_code == 405


# ---------- /saude ----------

def test_saude_com_todos_no_ar(cliente):
    r = cliente.get("/saude")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "gateway": "ok",
                        "servicos": {"usuarios": "ok", "inventario": "ok", "chamados": "ok", "notificacoes": "ok"}}


def test_saude_mostra_qual_servico_caiu_e_continua_respondendo_200(cliente, servicos):
    servicos.fora["inventario"] = httpx.ConnectError("recusou")
    r = cliente.get("/saude")
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["status"] == "degradado" and corpo["gateway"] == "ok"
    assert corpo["servicos"]["inventario"] == "fora do ar" and corpo["servicos"]["usuarios"] == "ok"


def test_saude_nao_exige_login_e_nao_repassa_token(cliente, servicos):
    cliente.get("/saude", headers={"Authorization": "Bearer segredo"})
    assert all("authorization" not in r.headers for r in servicos.recebidas)


def test_saude_distingue_servico_com_problemas_de_servico_fora_do_ar(cliente, servicos):
    servicos.respostas["/saude"] = httpx.Response(503)
    corpo = cliente.get("/saude").json()
    assert corpo["status"] == "degradado" and set(corpo["servicos"].values()) == {"com problemas"}
