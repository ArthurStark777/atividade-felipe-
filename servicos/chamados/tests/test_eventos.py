"""Publicação de eventos no Redis Stream (com um Redis de mentira)."""
import json
from datetime import datetime

from app.eventos import Publicador


class RedisFalso:
    def __init__(self, falhar=False):
        self.falhar = falhar
        self.entradas = []

    def xadd(self, stream, campos, maxlen=None, approximate=None):
        if self.falhar:
            raise ConnectionError("Redis fora do ar")
        self.entradas.append((stream, campos, maxlen, approximate))
        return b"1-0"


def publicador_com(redis_falso):
    p = Publicador("redis://qualquer:6379/0", "chamados.eventos", tamanho_maximo=500)
    p._redis = redis_falso
    return p


def test_publica_evento_no_stream_com_o_formato_combinado():
    r = RedisFalso()
    assert publicador_com(r).publicar("ChamadoAberto", {"chamado_id": 1, "solicitante_id": 2}) is True
    stream, campos, maxlen, aproximado = r.entradas[0]
    assert stream == "chamados.eventos" and maxlen == 500 and aproximado is True
    evento = json.loads(campos["evento"])
    assert set(evento) == {"id", "tipo", "ocorrido_em", "dados"}
    assert evento["tipo"] == "ChamadoAberto" and evento["dados"] == {"chamado_id": 1, "solicitante_id": 2}
    assert datetime.fromisoformat(evento["ocorrido_em"]).tzinfo is not None


def test_cada_evento_tem_um_id_proprio():
    r = RedisFalso()
    p = publicador_com(r)
    p.publicar("ChamadoAberto", {})
    p.publicar("ChamadoAberto", {})
    ids = [json.loads(e[1]["evento"])["id"] for e in r.entradas]
    assert len(set(ids)) == 2


def test_redis_fora_do_ar_nao_lanca_erro():
    assert publicador_com(RedisFalso(falhar=True)).publicar("ChamadoAberto", {"chamado_id": 1}) is False
