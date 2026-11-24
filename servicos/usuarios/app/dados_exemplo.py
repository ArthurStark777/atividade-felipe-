"""Cria os usuários de exemplo quando o banco está vazio.

Uso apenas em aula: todos têm a mesma senha (variável SENHA_EXEMPLO).
Em produção, rode com DADOS_EXEMPLO=0.

ATENÇÃO: os serviços de Chamados e Inventário criam seus dados de exemplo apontando
para os ids abaixo (Ana=2, Bruno=3, Carla=4). Se mudar a ordem, ajuste lá também.
"""
import os

from sqlalchemy.orm import Session

from app.usuarios import servico as usuarios
from app.usuarios.esquemas import UsuarioCriar


def carregar(db: Session) -> None:
    if usuarios.listar(db):
        return
    senha = os.getenv("SENHA_EXEMPLO") or "Helpdesk2026"
    novo = lambda nome, email, perfil: usuarios.criar(db, UsuarioCriar(nome=nome, email=email, perfil=perfil, senha=senha))
    novo("Admin TI", "admin@empresa.com", "admin")        # id 1
    novo("Ana Souza", "ana@empresa.com", "solicitante")   # id 2
    novo("Bruno Lima", "bruno@empresa.com", "solicitante")  # id 3
    novo("Carla Dias", "carla@empresa.com", "tecnico")    # id 4
    novo("Diego Rocha", "diego@empresa.com", "tecnico")   # id 5
