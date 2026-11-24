"""O laço do consumidor, com um Redis de mentira (sem rede): confirma, descarta e tenta de novo."""
import json
import threading

from app.consumidor import Consumidor
from tests.conftest import evento


class RedisFalso:
    """Entrega as leituras na ordem em que foram programadas e registra as confirmações (XACK)."""

    def __init__(self, parar, leituras):
        self.parar = parar
        self.leituras = list(leituras)  # cada item: o que xreadgroup devolve
        self.confirmadas = []
        self.pedidos = []  # (id_leitura, block) de cada xreadgroup

    def xreadgroup(self, grupo, consumidor, streams, count=None, block=None):
        self.pedidos.append((list(streams.values())[0], block))
        if not self.leituras:
            self.parar.set()  # acabou o roteiro: encerra o laço
            return []
        return self.leituras.pop(0)

    def xack(self, stream, grupo, msg_id):
        self.confirmadas.append(msg_id)


def msg(msg_id, e):
    return (msg_id, {"evento": json.dumps(e)})


def consumidor_para(sessao):
    return Consumidor("redis://x", "chamados.eventos", "notificacoes", "teste-1", sessao)


def test_le_pendentes_primeiro_e_depois_as_novas_e_confirma(sessao):
    parar = threading.Event()
    e = evento("ChamadoAtribuido", {"chamado_id": 7, "tecnico_id": 4})
    r = RedisFalso(parar, [
        [["chamados.eventos", []]],                       # nenhuma pendente
        [["chamados.eventos", [msg("1-0", e)]]],          # uma nova
    ])
    consumidor_para(sessao).ler(r, parar)
    assert [p[0] for p in r.pedidos[:2]] == ["0", ">"]    # pendentes antes das novas
    assert r.pedidos[0][1] is None and r.pedidos[1][1] is not None  # só as novas ficam bloqueando
    assert r.confirmadas == ["1-0"]
    from app.notificacoes import servico
    with sessao() as db:
        assert [a.destinatario_id for a in servico.listar(db)] == [4]


def test_mensagem_malformada_e_confirmada_e_descartada(sessao):
    parar = threading.Event()
    r = RedisFalso(parar, [
        [["chamados.eventos", [("1-0", {"evento": "isto não é json"}), ("2-0", {"outro": "campo"}),
                               msg("3-0", {"id": "x", "tipo": "ChamadoAberto"})]]],
    ])
    consumidor_para(sessao).ler(r, parar)
    assert r.confirmadas == ["1-0", "2-0", "3-0"]  # nenhuma fica presa na fila
    from app.notificacoes import servico
    with sessao() as db:
        assert servico.listar(db) == []


def test_falha_passageira_nao_confirma_e_volta_as_pendentes(sessao, monkeypatch):
    parar = threading.Event()
    parar.wait = lambda tempo=None: False  # não espera de verdade nos testes
    e = evento("ChamadoAtribuido", {"chamado_id": 7, "tecnico_id": 4})
    r = RedisFalso(parar, [
        [["chamados.eventos", []]],
        [["chamados.eventos", [msg("1-0", e)]]],          # vai falhar
        [["chamados.eventos", [msg("1-0", e)]]],          # entregue de novo, agora funciona
    ])
    c = consumidor_para(sessao)

    from app.notificacoes import servico
    original = servico.tratar_evento
    chamadas = []

    def instavel(db, bruto):
        chamadas.append(1)
        if len(chamadas) == 1:
            raise RuntimeError("banco indisponível")
        return original(db, bruto)

    monkeypatch.setattr(servico, "tratar_evento", instavel)
    c.ler(r, parar)
    assert r.confirmadas == ["1-0"]                        # só confirmou depois de dar certo
    # pendentes -> novas (falhou) -> volta às pendentes (deu certo) -> pendentes vazias
    assert [p[0] for p in r.pedidos] == ["0", ">", "0", "0"]
    with sessao() as db:
        assert len(servico.listar(db)) == 1


def test_executar_sobrevive_a_redis_fora_do_ar(sessao):
    """Se o Redis não responde, o laço espera e tenta de novo, sem encerrar a thread."""
    parar = threading.Event()
    c = consumidor_para(sessao)
    tentativas = []

    def conectar_com_erro():
        tentativas.append(1)
        if len(tentativas) >= 2:
            parar.set()
        raise ConnectionError("Redis fora do ar")

    c._conectar = conectar_com_erro
    c.espera_reconexao = 0.01
    c.executar(parar)
    assert len(tentativas) >= 2
