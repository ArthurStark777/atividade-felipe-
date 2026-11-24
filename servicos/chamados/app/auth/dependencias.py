"""Dependências do FastAPI para exigir login.

Este serviço não tem banco de usuários: confere a ASSINATURA do token (só o serviço de
Usuários conhece o segredo para assinar) e usa id e perfil que estão dentro dele.
O token inteiro é guardado em `UsuarioAtual.token` para ser REPASSADO aos outros serviços.
"""
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth import tokens

esquema = HTTPBearer(auto_error=False)

NAO_AUTENTICADO = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Faça login para continuar.",
    headers={"WWW-Authenticate": "Bearer"},
)


@dataclass(frozen=True)
class UsuarioAtual:
    id: int
    perfil: str  # "solicitante", "tecnico" ou "admin"
    token: str   # repassado no cabeçalho Authorization ao chamar outros serviços


def usuario_atual(credenciais: HTTPAuthorizationCredentials | None = Depends(esquema)) -> UsuarioAtual:
    if credenciais is None or credenciais.scheme.lower() != "bearer":
        raise NAO_AUTENTICADO
    try:
        identidade = tokens.ler(credenciais.credentials)
    except tokens.TokenInvalido:
        raise NAO_AUTENTICADO
    return UsuarioAtual(id=identidade.usuario_id, perfil=identidade.perfil, token=credenciais.credentials)
