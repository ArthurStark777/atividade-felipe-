"""Erros de negócio deste serviço."""


class NaoEncontrado(Exception):
    """O recurso pedido não existe (ou o usuário não pode vê-lo)."""


class RegraDeNegocio(Exception):
    """A operação viola uma regra do sistema."""


class SemPermissao(Exception):
    """O usuário está logado, mas não pode fazer esta operação."""


class ServicoIndisponivel(Exception):
    """Um serviço de que este depende (Usuários ou Inventário) não respondeu como deveria.

    Vira resposta 503: o erro é claro e o resto do sistema continua funcionando.
    """

    def __init__(self, servico: str, motivo: str = ""):
        self.servico = servico
        self.motivo = motivo  # só para o log; não vai para o cliente
        super().__init__(f"O serviço de {servico} está indisponível no momento. Tente novamente em instantes.")
