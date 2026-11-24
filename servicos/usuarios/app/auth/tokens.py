"""Criação (só no serviço de Usuários) e conferência dos tokens JWT."""
from datetime import datetime, timedelta, timezone
from typing import NamedTuple

import jwt

from app.config import JWT_ALGORITMO, JWT_EMISSOR, JWT_SEGREDO, TOKEN_MINUTOS

PERFIS = {"solicitante", "tecnico", "admin"}


class TokenInvalido(Exception):
    pass


class Identidade(NamedTuple):
    usuario_id: int
    perfil: str


def criar(usuario_id: int, perfil: str) -> tuple[str, datetime]:
    agora = datetime.now(timezone.utc)
    expira = agora + timedelta(minutes=TOKEN_MINUTOS)
    dados = {"sub": str(usuario_id), "perfil": perfil, "iat": agora, "exp": expira, "iss": JWT_EMISSOR}
    return jwt.encode(dados, JWT_SEGREDO, algorithm=JWT_ALGORITMO), expira


def ler(token: str) -> Identidade:
    """Confere assinatura, validade e emissor. Devolve quem é o dono do token, ou lança TokenInvalido."""
    try:
        dados = jwt.decode(
            token, JWT_SEGREDO, algorithms=[JWT_ALGORITMO], issuer=JWT_EMISSOR,
            options={"require": ["exp", "iat", "sub", "iss", "perfil"]},
        )
        if dados["perfil"] not in PERFIS:
            raise ValueError("perfil desconhecido")
        return Identidade(int(dados["sub"]), dados["perfil"])
    except (jwt.PyJWTError, ValueError, KeyError, TypeError) as erro:
        raise TokenInvalido() from erro
