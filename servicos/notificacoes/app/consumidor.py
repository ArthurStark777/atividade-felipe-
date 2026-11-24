"""Consumidor dos eventos (Redis Streams, com grupo de consumidores).

Por que um stream com grupo, e não um simples publicar/assinar:
- as mensagens FICAM na fila até serem confirmadas (XACK): se este serviço estiver fora do ar,
  os avisos esperam e são entregues quando ele voltar;
- ao reiniciar, primeiro lê as mensagens que tinha recebido e não confirmou (pendentes);
- a entrega é "pelo menos uma vez", por isso o tratamento é idempotente (veja servico.tratar_evento).

O laço nunca termina por causa de erro: se o Redis cair, espera e tenta de novo.
"""
import json
import logging
import threading

from sqlalchemy.orm import sessionmaker

from app import config
from app.notificacoes import servico

log = logging.getLogger("helpdesk.notificacoes")


class Consumidor:
    def __init__(self, url: str, stream: str, grupo: str, nome: str, sessao: sessionmaker,
                 bloqueio_ms: int = 2000, espera_reconexao: float = 3.0):
        self.url, self.stream, self.grupo, self.nome = url, stream, grupo, nome
        self.sessao = sessao
        self.bloqueio_ms = bloqueio_ms
        self.espera_reconexao = espera_reconexao

    def executar(self, parar: threading.Event) -> None:
        """Laço principal (roda em uma thread). Termina quando `parar` for acionado."""
        while not parar.is_set():
            try:
                r = self._conectar()
                self._garantir_grupo(r)
                log.info("Consumidor %s ligado ao stream %s", self.nome, self.stream)
                self.ler(r, parar)
            except Exception as erro:  # Redis fora do ar, conexão cortada etc.
                log.warning("Fila indisponível (%s: %s); nova tentativa em %.0fs",
                            type(erro).__name__, erro, self.espera_reconexao)
                parar.wait(self.espera_reconexao)

    def _conectar(self):
        import redis  # importado aqui: os testes não precisam da biblioteca nem de um Redis

        # O timeout do socket precisa ser MAIOR que o tempo de bloqueio da leitura
        return redis.Redis.from_url(self.url, decode_responses=True, socket_connect_timeout=2,
                                    socket_timeout=self.bloqueio_ms / 1000 + 5)

    def _garantir_grupo(self, r) -> None:
        import redis

        try:
            # id="0": um grupo novo recebe TAMBÉM os eventos publicados antes de ele existir
            r.xgroup_create(self.stream, self.grupo, id="0", mkstream=True)
        except redis.exceptions.ResponseError as erro:
            if "BUSYGROUP" not in str(erro):  # BUSYGROUP = o grupo já existe (normal)
                raise

    def ler(self, r, parar: threading.Event) -> None:
        # Começa pelas PENDENTES ("0"): recebidas antes e nunca confirmadas. Depois, só as novas (">").
        id_leitura = "0"
        while not parar.is_set():
            resposta = r.xreadgroup(
                self.grupo, self.nome, {self.stream: id_leitura}, count=20,
                block=self.bloqueio_ms if id_leitura == ">" else None,
            )
            mensagens = resposta[0][1] if resposta else []
            if not mensagens:
                id_leitura = ">"
                continue
            todas_ok = True
            for msg_id, campos in mensagens:
                todas_ok = self.tratar(r, msg_id, campos) and todas_ok
            if not todas_ok:
                id_leitura = "0"  # alguma falhou por motivo passageiro: volta às pendentes
                parar.wait(2)

    def tratar(self, r, msg_id: str, campos: dict) -> bool:
        """Trata uma mensagem. Devolve False se deve ser tentada de novo (não foi confirmada)."""
        try:
            bruto = json.loads(campos["evento"])
            with self.sessao() as db:
                servico.tratar_evento(db, bruto)
        except (KeyError, TypeError, ValueError, servico.EventoInvalido) as erro:
            # Mensagem malformada: tentar de novo não adianta. Confirma para não travar a fila.
            log.error("Mensagem %s descartada por estar malformada (%s: %s)", msg_id, type(erro).__name__, erro)
        except Exception:
            log.exception("Falha ao tratar a mensagem %s; ela será tentada de novo", msg_id)
            return False
        r.xack(self.stream, self.grupo, msg_id)
        return True


def criar(sessao: sessionmaker) -> Consumidor:
    return Consumidor(config.REDIS_URL, config.STREAM_EVENTOS, config.GRUPO_CONSUMIDORES, config.NOME_CONSUMIDOR,
                      sessao, espera_reconexao=config.ESPERA_RECONEXAO_SEGUNDOS)
