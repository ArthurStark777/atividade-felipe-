"""Serviço de Chamados do HelpDesk TI: abrir, atribuir, acompanhar e resolver chamados.

Fala com os serviços de Usuários e de Inventário pela rede (HTTP) e avisa o resto do
sistema por eventos (Redis Streams). Não acessa o banco de nenhum outro serviço.
"""
