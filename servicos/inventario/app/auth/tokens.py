"""Conferência dos tokens JWT emitidos pelo serviço de Usuários."""
from typing import NamedTuple

import jwt

from app.config import JWT_ALGORITMO, JWT_EMISSOR, JWT_SEGREDO

PERFIS = {"solicitante", "tecnico", "admin"}


class TokenInvalido(Exception):
    pass


class Identidade(NamedTuple):
    usuario_id: int
    perfil: str


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
