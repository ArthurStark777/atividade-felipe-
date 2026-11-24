"""API Gateway do HelpDesk TI: único ponto de entrada (porta 8000).

Entrega a tela e encaminha cada rota para o serviço certo. Não conhece o segredo dos tokens
e não decide permissões: cada serviço confere o token por conta própria.
"""
