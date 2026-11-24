from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencias import usuario_atual
from app.auth.tokens import Identidade
from app.database import get_db
from app.notificacoes import servico
from app.notificacoes.esquemas import NotificacaoSaida

router = APIRouter(prefix="/notificacoes", tags=["Notificações"])


@router.get("", response_model=list[NotificacaoSaida])
def minhas_notificacoes(usuario: Identidade = Depends(usuario_atual), db: Session = Depends(get_db)):
    """Cada usuário vê só as próprias notificações (o id vem do token)."""
    return servico.listar(db, usuario.usuario_id)
