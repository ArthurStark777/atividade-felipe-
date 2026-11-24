"""Publicação de eventos (bônus): o serviço de Chamados AVISA, o de Notificações REAGE.

Os eventos vão para um Redis Stream. Diferente de um simples "publicar/assinar", o stream
guarda as mensagens: se o serviço de Notificações estiver fora do ar, os avisos esperam na
fila e são entregues quando ele voltar.

Publicar nunca derruba o chamado: se o Redis estiver fora do ar, o erro vai para o log
e o chamado já salvo continua valendo (limitação conhecida: aquele evento se perde;
a solução completa seria o padrão "outbox", descrito no README).

Formato (uma entrada do stream, campo "evento" com JSON):
    {"id": "<uuid>", "tipo": "ChamadoAberto", "ocorrido_em": "<ISO 8601 UTC>", "dados": {...}}
"""
import json
import logging
import uuid
from datetime import datetime, timezone

from app import config

log = logging.getLogger("helpdesk.chamados")


class Publicador:
    def __init__(self, url: str, stream: str, tamanho_maximo: int = 10000):
        self.url = url
        self.stream = stream
        self.tamanho_maximo = tamanho_maximo
        self._redis = None

    def _conexao(self):
        if self._redis is None:
            import redis  # importado aqui: os testes não precisam da biblioteca nem de um Redis

            # Timeouts curtos: o Redis fora do ar não pode travar a abertura de chamados.
            self._redis = redis.Redis.from_url(self.url, socket_connect_timeout=1, socket_timeout=1)
        return self._redis

    def publicar(self, tipo: str, dados: dict) -> bool:
        """Publica um evento. Devolve True se entrou na fila; nunca lança erro."""
        evento = {
            "id": uuid.uuid4().hex, "tipo": tipo,
            "ocorrido_em": datetime.now(timezone.utc).isoformat(), "dados": dados,
        }
        try:
            self._conexao().xadd(
                self.stream, {"evento": json.dumps(evento, default=str)},
                maxlen=self.tamanho_maximo, approximate=True,
            )
            log.info("Evento %s publicado no stream %s", tipo, self.stream)
            return True
        except Exception as erro:  # qualquer falha da fila: o chamado já foi salvo e segue valendo
            log.warning("Evento %s não foi publicado (%s: %s)", tipo, type(erro).__name__, erro)
            return False


_publicador: Publicador | None = None


def get_publicador() -> Publicador:
    global _publicador
    if _publicador is None:
        _publicador = Publicador(config.REDIS_URL, config.STREAM_EVENTOS, config.STREAM_TAMANHO_MAXIMO)
    return _publicador
