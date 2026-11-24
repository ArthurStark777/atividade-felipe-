from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencias import UsuarioAtual, usuario_atual
from app.chamados import servico
from app.chamados.esquemas import (
    Atribuicao, ChamadoCriar, ChamadoSaida, ComentarioCriar, ComentarioSaida, MudancaStatus, Painel, Status,
)
from app.clientes import ClienteInventario, ClienteUsuarios, get_cliente_inventario, get_cliente_usuarios
from app.database import get_db
from app.eventos import Publicador, get_publicador

router = APIRouter(prefix="/chamados", tags=["Chamados"])


@router.post("", response_model=ChamadoSaida, status_code=201)
def abrir_chamado(dados: ChamadoCriar, usuario: UsuarioAtual = Depends(usuario_atual), db: Session = Depends(get_db),
                  inventario: ClienteInventario = Depends(get_cliente_inventario),
                  eventos: Publicador = Depends(get_publicador)):
    return servico.abrir(db, dados, usuario, inventario, eventos)


@router.get("", response_model=list[ChamadoSaida])
def listar_chamados(status: Status | None = None, tecnico_id: int | None = None,
                    usuario: UsuarioAtual = Depends(usuario_atual), db: Session = Depends(get_db)):
    return servico.listar(db, usuario, status, tecnico_id)


@router.get("/painel", response_model=Painel)
def painel(usuario: UsuarioAtual = Depends(usuario_atual), db: Session = Depends(get_db)):
    return servico.painel(db, usuario)


@router.get("/{chamado_id}", response_model=ChamadoSaida)
def obter_chamado(chamado_id: int, usuario: UsuarioAtual = Depends(usuario_atual), db: Session = Depends(get_db)):
    return servico.obter(db, chamado_id, usuario)


@router.patch("/{chamado_id}/atribuir", response_model=ChamadoSaida)
def atribuir_chamado(chamado_id: int, dados: Atribuicao, usuario: UsuarioAtual = Depends(usuario_atual),
                     db: Session = Depends(get_db), usuarios: ClienteUsuarios = Depends(get_cliente_usuarios),
                     eventos: Publicador = Depends(get_publicador)):
    return servico.atribuir(db, chamado_id, dados.tecnico_id, usuario, usuarios, eventos)


@router.patch("/{chamado_id}/status", response_model=ChamadoSaida)
def mudar_status(chamado_id: int, dados: MudancaStatus, usuario: UsuarioAtual = Depends(usuario_atual),
                 db: Session = Depends(get_db), eventos: Publicador = Depends(get_publicador)):
    return servico.mudar_status(db, chamado_id, dados.status, usuario, eventos)


@router.post("/{chamado_id}/comentarios", response_model=ComentarioSaida, status_code=201)
def comentar(chamado_id: int, dados: ComentarioCriar, usuario: UsuarioAtual = Depends(usuario_atual),
             db: Session = Depends(get_db)):
    return servico.comentar(db, chamado_id, dados, usuario)
