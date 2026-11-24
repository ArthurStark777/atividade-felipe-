"""Configurações lidas das variáveis de ambiente."""
import os
from pathlib import Path

DATABASE_URL = os.getenv("DATABASE_URL") or "sqlite:///./inventario.db"


def _carregar_segredo() -> str:
    """Devolve o JWT_SEGREDO: primeiro do ambiente (.env); se vazio, do arquivo JWT_SEGREDO_ARQUIVO.

    É o MESMO segredo do serviço de Usuários (que emite os tokens). Este serviço só confere.
    Sem um segredo válido (32 caracteres ou mais) ele se recusa a iniciar.
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

# Tamanho máximo do corpo de uma requisição (em bytes)
TAMANHO_MAXIMO_REQUISICAO = 64 * 1024

DOCS_ATIVA = (os.getenv("DOCS") or "1") == "1"
