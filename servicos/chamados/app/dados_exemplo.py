"""Cria chamados de exemplo quando o banco está vazio (só para aula).

Os chamados apontam para ids que os OUTROS serviços criam nos seus próprios dados de exemplo:
  usuários:   Ana = 2 (solicitante), Bruno = 3 (solicitante), Carla = 4 (técnica)
  inventário: 1 = computador, 2 = impressora
Como são dados conhecidos, não há chamadas de rede aqui: assim o serviço sobe mesmo que os
outros ainda estejam iniciando.
"""
from sqlalchemy.orm import Session

from app.auth.dependencias import UsuarioAtual
from app.chamados import repositorio, servico
from app.chamados.esquemas import ChamadoCriar
from app.clientes import ClienteInventario, ClienteUsuarios
from app.eventos import Publicador


class _SemConferencia(ClienteInventario, ClienteUsuarios):
    """Substitui as chamadas HTTP: os dados de exemplo usam ids que sabemos que existem."""

    def __init__(self):
        super().__init__("http://sem-rede")  # nunca usado: os dois métodos abaixo não saem do processo

    def obter_ativo(self, ativo_id: int, token: str) -> dict:
        return {"id": ativo_id}

    def obter_tecnico(self, usuario_id: int, token: str) -> dict:
        return {"id": usuario_id, "perfil": "tecnico"}


def carregar(db: Session, eventos: Publicador) -> None:
    if repositorio.listar(db):
        return
    ana = UsuarioAtual(id=2, perfil="solicitante", token="")
    bruno = UsuarioAtual(id=3, perfil="solicitante", token="")
    carla = UsuarioAtual(id=4, perfil="tecnico", token="")
    fixo = _SemConferencia()

    c1 = servico.abrir(db, ChamadoCriar(titulo="Computador não liga", descricao="Apertei o botão e nada acontece.",
                                        prioridade="alta", ativo_id=1), ana, fixo, eventos)
    servico.abrir(db, ChamadoCriar(titulo="Impressora atolando papel", descricao="Atola a cada 3 folhas.",
                                   prioridade="media", ativo_id=2), bruno, fixo, eventos)
    servico.abrir(db, ChamadoCriar(titulo="Acesso ao sistema de RH", descricao="Preciso de acesso para a nova estagiária.",
                                   prioridade="baixa"), bruno, fixo, eventos)
    servico.atribuir(db, c1.id, 4, carla, fixo, eventos)
