"""Configurações lidas das variáveis de ambiente."""
import os
from pathlib import Path

DATABASE_URL = os.getenv("DATABASE_URL") or "sqlite:///./notificacoes.db"


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

# Fila de eventos publicada pelo serviço de Chamados
REDIS_URL = os.getenv("REDIS_URL") or "redis://redis:6379/0"
STREAM_EVENTOS = os.getenv("STREAM_EVENTOS") or "chamados.eventos"
GRUPO_CONSUMIDORES = os.getenv("GRUPO_CONSUMIDORES") or "notificacoes"
NOME_CONSUMIDOR = os.getenv("NOME_CONSUMIDOR") or "notificacoes-1"
CONSUMIDOR_ATIVO = (os.getenv("CONSUMIDOR_ATIVO") or "1") == "1"
ESPERA_RECONEXAO_SEGUNDOS = float(os.getenv("ESPERA_RECONEXAO_SEGUNDOS") or "3")

# Tamanho máximo do corpo de uma requisição (em bytes)
TAMANHO_MAXIMO_REQUISICAO = 64 * 1024

DOCS_ATIVA = (os.getenv("DOCS") or "1") == "1"
