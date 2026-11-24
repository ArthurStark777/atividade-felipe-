"""Do evento ao aviso: quem é avisado, o que diz a mensagem e a proteção contra repetição."""
import pytest

from app.notificacoes import servico
from tests.conftest import evento


def test_chamado_aberto_avisa_o_solicitante(sessao):
    with sessao() as db:
        aviso = servico.tratar_evento(db, evento("ChamadoAberto", {
            "chamado_id": 7, "solicitante_id": 2, "prazo_sla": "2026-11-20T15:30:00"}))
        assert aviso.tipo == "ChamadoAberto" and aviso.destinatario_id == 2
        assert aviso.mensagem == "Seu chamado #7 foi aberto. Prazo: 20/11 15:30."


def test_chamado_atribuido_avisa_o_tecnico(sessao):
    with sessao() as db:
        aviso = servico.tratar_evento(db, evento("ChamadoAtribuido", {"chamado_id": 7, "tecnico_id": 4}))
        assert aviso.destinatario_id == 4 and aviso.mensagem == "O chamado #7 foi atribuído a você."


def test_chamado_resolvido_avisa_o_solicitante(sessao):
    with sessao() as db:
        aviso = servico.tratar_evento(db, evento("ChamadoResolvido", {"chamado_id": 7, "solicitante_id": 2}))
        assert aviso.destinatario_id == 2
        assert aviso.mensagem == "Seu chamado #7 foi resolvido. Confirme se está tudo certo."


def test_o_mesmo_evento_nao_gera_dois_avisos(sessao):
    with sessao() as db:
        e = evento("ChamadoAtribuido", {"chamado_id": 7, "tecnico_id": 4}, id="repetido")
        assert servico.tratar_evento(db, e) is not None
        assert servico.tratar_evento(db, e) is None
        assert len(servico.listar(db)) == 1


def test_eventos_diferentes_geram_avisos_diferentes(sessao):
    with sessao() as db:
        servico.tratar_evento(db, evento("ChamadoAtribuido", {"chamado_id": 7, "tecnico_id": 4}, id="a"))
        servico.tratar_evento(db, evento("ChamadoAtribuido", {"chamado_id": 8, "tecnico_id": 4}, id="b"))
        assert len(servico.listar(db, destinatario_id=4)) == 2


def test_tipo_desconhecido_e_ignorado(sessao):
    with sessao() as db:
        assert servico.tratar_evento(db, evento("ChamadoExcluido", {"chamado_id": 1})) is None
        assert servico.listar(db) == []


@pytest.mark.parametrize("bruto", [
    {}, {"tipo": "ChamadoAberto"}, ["lista"], "texto",
    {"id": "x", "tipo": "ChamadoAberto", "ocorrido_em": "ontem", "dados": {}},
])
def test_envelope_invalido_e_rejeitado(sessao, bruto):
    with sessao() as db, pytest.raises(servico.EventoInvalido):
        servico.tratar_evento(db, bruto)


def test_dados_invalidos_sao_rejeitados(sessao):
    with sessao() as db, pytest.raises(servico.EventoInvalido):
        servico.tratar_evento(db, evento("ChamadoAtribuido", {"chamado_id": "abc"}))
    with sessao() as db:
        assert servico.listar(db) == []
