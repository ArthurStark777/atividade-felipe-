#!/usr/bin/env python3
"""Teste de integração do HelpDesk em microsserviços, contra o sistema NO AR (pelo gateway).

Uso (com `docker compose up --build` rodando, em outro terminal):

    python scripts/teste_integracao.py            # fluxo completo + segurança + notificações
    python scripts/teste_integracao.py --falha    # também para e religa o Inventário (usa docker compose)

Só usa a biblioteca padrão do Python. Sai com código 1 se alguma verificação falhar.
Variáveis opcionais: BASE_URL (padrão http://localhost:8000) e SENHA_EXEMPLO (padrão Helpdesk2026).
"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

BASE = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
SENHA = os.getenv("SENHA_EXEMPLO") or "Helpdesk2026"
falhas: list[str] = []


def chamar(metodo: str, caminho: str, corpo: dict | None = None, token: str | None = None) -> tuple[int, object]:
    """Faz uma requisição ao gateway. Devolve (status HTTP, corpo JSON)."""
    cabecalhos = {"Content-Type": "application/json"}
    if token:
        cabecalhos["Authorization"] = f"Bearer {token}"
    dados = json.dumps(corpo).encode() if corpo is not None else None
    pedido = urllib.request.Request(BASE + caminho, data=dados, method=metodo, headers=cabecalhos)
    try:
        with urllib.request.urlopen(pedido, timeout=15) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"null")
        except ValueError:
            return e.code, None
    except (urllib.error.URLError, OSError):
        return 0, None  # sem conexão com o gateway (status 0): quem chamou decide o que fazer


def verifica(descricao: str, condicao: bool, detalhe: object = "") -> bool:
    print(f"  {'✓' if condicao else '✗'} {descricao}" + ("" if condicao or detalhe == "" else f"   -> {detalhe}"))
    if not condicao:
        falhas.append(descricao)
    return condicao


def entrar(email: str) -> tuple[str, int]:
    status, corpo = chamar("POST", "/auth/login", {"email": email, "senha": SENHA})
    if status != 200:
        sys.exit(f"Não consegui entrar como {email} (HTTP {status}). Os dados de exemplo estão ligados (DADOS_EXEMPLO=1)?")
    return corpo["access_token"], corpo["usuario"]["id"]


def esperar(condicao, segundos: float = 15, passo: float = 0.5):
    fim = time.time() + segundos
    while time.time() < fim:
        resultado = condicao()
        if resultado:
            return resultado
        time.sleep(passo)
    return None


def servicos_no_ar() -> dict:
    status, corpo = chamar("GET", "/saude")
    return corpo.get("servicos", {}) if status == 200 and isinstance(corpo, dict) else {}


def docker_compose(*args: str) -> None:
    raiz = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    subprocess.run(["docker", "compose", *args], cwd=raiz, check=True, capture_output=True)


def fluxo_completo() -> None:
    print("\n1) Gateway e serviços")
    estado = servicos_no_ar()
    verifica("o gateway responde e todos os serviços estão no ar", bool(estado) and all(v == "ok" for v in estado.values()), estado)

    print("\n2) Segurança: sem token, tudo é recusado (401)")
    for rota in ("/chamados", "/chamados/painel", "/usuarios", "/ativos", "/notificacoes", "/auth/eu"):
        verifica(f"GET {rota} sem token -> 401", chamar("GET", rota)[0] == 401)
    verifica("token falso -> 401", chamar("GET", "/chamados", token="isto.nao.e.um.token")[0] == 401)
    verifica("senha errada no login -> 401", chamar("POST", "/auth/login", {"email": "ana@empresa.com", "senha": "errada123"})[0] == 401)

    print("\n3) Fluxo completo de um chamado (técnica Carla, solicitantes Ana e Bruno)")
    carla, id_carla = entrar("carla@empresa.com")
    ana, id_ana = entrar("ana@empresa.com")
    bruno, _ = entrar("bruno@empresa.com")

    status, ativos = chamar("GET", "/ativos", token=carla)
    verifica("lista de equipamentos (serviço de Inventário)", status == 200 and len(ativos) >= 1)
    ativo_id = ativos[0]["id"]

    status, chamado = chamar("POST", "/chamados", {"titulo": "Teste de integração", "descricao": "Aberto pelo script",
                                                   "prioridade": "alta", "ativo_id": ativo_id}, token=ana)
    verifica("Ana abre um chamado com equipamento -> 201", status == 201, chamado)
    cid = chamado["id"]
    verifica("o solicitante é a Ana (vem do token)", chamado["solicitante_id"] == id_ana)

    status, _ = chamar("POST", "/chamados", {"titulo": "Equipamento falso", "descricao": "x", "prioridade": "baixa", "ativo_id": 99999}, token=ana)
    verifica("equipamento inexistente -> 404 (conferido no Inventário)", status == 404)

    print("\n4) Permissões")
    verifica("Bruno não vê o chamado da Ana (404)", chamar("GET", f"/chamados/{cid}", token=bruno)[0] == 404)
    _, lista_bruno = chamar("GET", "/chamados", token=bruno)
    verifica("a lista do Bruno não traz o chamado da Ana", all(c["id"] != cid for c in lista_bruno))
    verifica("Ana não atribui chamado (403)", chamar("PATCH", f"/chamados/{cid}/atribuir", {"tecnico_id": id_carla}, token=ana)[0] == 403)
    verifica("Ana não resolve chamado (403)", chamar("PATCH", f"/chamados/{cid}/status", {"status": "em_atendimento"}, token=ana)[0] == 403)

    print("\n5) Atribuir, resolver e fechar (regras de status e SLA)")
    verifica("atribuir a quem não é técnico -> 422 (conferido no serviço de Usuários)",
             chamar("PATCH", f"/chamados/{cid}/atribuir", {"tecnico_id": id_ana}, token=carla)[0] == 422)
    status, c = chamar("PATCH", f"/chamados/{cid}/atribuir", {"tecnico_id": id_carla}, token=carla)
    verifica("Carla atribui a si mesma -> em_atendimento", status == 200 and c["status"] == "em_atendimento", c)
    verifica("transição inválida (em_atendimento -> fechado) -> 422",
             chamar("PATCH", f"/chamados/{cid}/status", {"status": "fechado"}, token=carla)[0] == 422)
    status, c = chamar("PATCH", f"/chamados/{cid}/status", {"status": "resolvido"}, token=carla)
    verifica("Carla resolve -> resolvido", status == 200 and c["status"] == "resolvido", c)
    status, _ = chamar("POST", f"/chamados/{cid}/comentarios", {"texto": "Troquei a fonte."}, token=carla)
    verifica("Carla comenta -> 201", status == 201)
    status, c = chamar("PATCH", f"/chamados/{cid}/status", {"status": "fechado"}, token=ana)
    verifica("Ana confirma e fecha o próprio chamado -> fechado", status == 200 and c["status"] == "fechado", c)
    verifica("chamado fechado não recebe comentário (422)",
             chamar("POST", f"/chamados/{cid}/comentarios", {"texto": "ainda aqui"}, token=ana)[0] == 422)

    status, painel = chamar("GET", "/chamados/painel", token=carla)
    verifica("painel responde com totais", status == 200 and painel["total"] >= 1 and "por_status" in painel, painel)

    print("\n6) Notificações por evento (bônus: Chamados -> Redis -> Notificações)")
    def avisos_da_ana():
        _, avisos = chamar("GET", "/notificacoes", token=ana)
        tipos = {a["tipo"] for a in avisos} if isinstance(avisos, list) else set()
        return {"ChamadoAberto", "ChamadoResolvido"} <= tipos
    verifica("Ana recebeu ChamadoAberto e ChamadoResolvido", bool(esperar(avisos_da_ana)))
    def aviso_da_carla():
        _, avisos = chamar("GET", "/notificacoes", token=carla)
        return isinstance(avisos, list) and any(a["tipo"] == "ChamadoAtribuido" for a in avisos)
    verifica("Carla recebeu ChamadoAtribuido", bool(esperar(aviso_da_carla)))
    _, avisos_bruno = chamar("GET", "/notificacoes", token=bruno)
    verifica("Bruno não vê as notificações da Ana",
             isinstance(avisos_bruno, list) and all(f"#{cid} " not in a["mensagem"] for a in avisos_bruno))


def falha_do_inventario() -> None:
    print("\n7) Falha de um serviço: docker compose stop inventario")
    carla, _ = entrar("carla@empresa.com")
    ana, _ = entrar("ana@empresa.com")
    docker_compose("stop", "inventario")
    try:
        verifica("/saude mostra o Inventário fora do ar", esperar(lambda: servicos_no_ar().get("inventario") == "fora do ar", 10) is not None)
        verifica("lista de usuários continua funcionando (200)", chamar("GET", "/usuarios", token=ana)[0] == 200)
        verifica("lista de chamados continua funcionando (200)", chamar("GET", "/chamados", token=ana)[0] == 200)
        status, corpo = chamar("POST", "/chamados", {"titulo": "Com equipamento", "descricao": "x", "prioridade": "baixa", "ativo_id": 1}, token=ana)
        verifica("abrir chamado COM equipamento -> 503 com mensagem clara", status == 503 and "Inventário" in str(corpo), (status, corpo))
        status, _ = chamar("POST", "/chamados", {"titulo": "Sem equipamento", "descricao": "x", "prioridade": "baixa"}, token=ana)
        verifica("abrir chamado SEM equipamento continua funcionando (201)", status == 201)
        verifica("listar equipamentos -> 503 (e não trava)", chamar("GET", "/ativos", token=carla)[0] == 503)
    finally:
        print("   ... docker compose start inventario")
        docker_compose("start", "inventario")
    verifica("o Inventário volta ao ar", esperar(lambda: servicos_no_ar().get("inventario") == "ok", 60, 1) is not None)
    status, _ = chamar("POST", "/chamados", {"titulo": "Depois da volta", "descricao": "x", "prioridade": "baixa", "ativo_id": 1}, token=ana)
    verifica("abrir chamado com equipamento volta a funcionar (201)", status == 201)


def main() -> None:
    if not servicos_no_ar():
        sys.exit(f"O gateway não respondeu em {BASE}. Suba o sistema com: docker compose up --build")
    fluxo_completo()
    if "--falha" in sys.argv:
        falha_do_inventario()
    print()
    if falhas:
        print(f"✗ {len(falhas)} verificação(ões) falharam:")
        for f in falhas:
            print("   -", f)
        sys.exit(1)
    print("✓ Tudo certo.")


if __name__ == "__main__":
    main()
