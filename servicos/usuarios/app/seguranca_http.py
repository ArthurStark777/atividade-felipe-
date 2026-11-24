"""Proteções aplicadas a todas as respostas HTTP do serviço.

Os cabeçalhos voltados ao navegador (CSP, X-Frame-Options...) ficam no gateway,
que é quem entrega a tela. Aqui ficam o limite de tamanho e o cache.
"""
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import TAMANHO_MAXIMO_REQUISICAO


class CabecalhosDeSeguranca(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        tamanho = request.headers.get("content-length")
        if tamanho and (not tamanho.isdigit() or int(tamanho) > TAMANHO_MAXIMO_REQUISICAO):
            return JSONResponse(status_code=413, content={"detail": "Requisição grande demais."})

        resposta = await call_next(request)
        resposta.headers["X-Content-Type-Options"] = "nosniff"
        resposta.headers["Cache-Control"] = "no-store"
        return resposta
