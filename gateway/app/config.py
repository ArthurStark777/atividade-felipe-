"""Configurações lidas das variáveis de ambiente."""
import os


def _env(nome: str, padrao: str) -> str:
    return os.getenv(nome) or padrao


# Endereços dos serviços. Dentro do Docker Compose usa-se o NOME do serviço, não localhost.
SERVICOS = {
    "usuarios": _env("USUARIOS_URL", "http://usuarios:8000"),
    "inventario": _env("INVENTARIO_URL", "http://inventario:8000"),
    "chamados": _env("CHAMADOS_URL", "http://chamados:8000"),
    "notificacoes": _env("NOTIFICACOES_URL", "http://notificacoes:8000"),
}

NOMES = {"usuarios": "Usuários", "inventario": "Inventário", "chamados": "Chamados", "notificacoes": "Notificações"}

# Tabela de rotas: começo do caminho -> serviço. Só o que está aqui é encaminhado.
ROTAS = (
    ("/auth", "usuarios"),
    ("/usuarios", "usuarios"),
    ("/ativos", "inventario"),
    ("/chamados", "chamados"),
    ("/notificacoes", "notificacoes"),
)

# Tempo máximo de espera por um serviço (em segundos) e para conectar
TIMEOUT_SEGUNDOS = float(_env("GATEWAY_TIMEOUT_SEGUNDOS", "10"))
TIMEOUT_CONEXAO_SEGUNDOS = float(_env("GATEWAY_TIMEOUT_CONEXAO_SEGUNDOS", "2"))
TIMEOUT_SAUDE_SEGUNDOS = float(_env("GATEWAY_TIMEOUT_SAUDE_SEGUNDOS", "1.5"))

# Tamanho máximo do corpo de uma requisição (em bytes)
TAMANHO_MAXIMO_REQUISICAO = 64 * 1024
