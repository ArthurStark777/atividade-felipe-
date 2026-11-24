"""Configurações lidas das variáveis de ambiente."""
import os
from pathlib import Path

DATABASE_URL = os.getenv("DATABASE_URL") or "sqlite:///./usuarios.db"


def _carregar_segredo() -> str:
    """Devolve o JWT_SEGREDO: primeiro do ambiente (.env); se vazio, do arquivo JWT_SEGREDO_ARQUIVO.

    No monólito, sem segredo o sistema criava um aleatório. Em microsserviços isso não serve:
    todos os serviços precisam do MESMO segredo para conferir os tokens. Por isso, sem um
    segredo válido (32 caracteres ou mais) o serviço se recusa a iniciar.
    """
    segredo = (os.getenv("JWT_SEGREDO") or "").strip()
    if not segredo:
        arquivo = os.getenv("JWT_SEGREDO_ARQUIVO") or ""
        if arquivo and Path(arquivo).is_file():
            segredo = Path(arquivo).read_text().strip()
    if len(segredo) < 32:
        raise RuntimeError(
            "JWT_SEGREDO ausente ou com menos de 32 caracteres. Defina no .env "
            "(python -c \"import secrets; print(secrets.token_urlsafe(48))\") ou deixe o "
            "docker compose gerar sozinho."
        )
    return segredo


JWT_SEGREDO = _carregar_segredo()
JWT_ALGORITMO = "HS256"
JWT_EMISSOR = "helpdesk-ti"
TOKEN_MINUTOS = int(os.getenv("TOKEN_MINUTOS") or "60")

# Proteção contra tentativas de adivinhar senhas
LOGIN_MAX_FALHAS = int(os.getenv("LOGIN_MAX_FALHAS") or "5")
LOGIN_JANELA_SEGUNDOS = int(os.getenv("LOGIN_JANELA_SEGUNDOS") or "300")

# Tamanho máximo do corpo de uma requisição (em bytes)
TAMANHO_MAXIMO_REQUISICAO = 64 * 1024

DOCS_ATIVA = (os.getenv("DOCS") or "1") == "1"
