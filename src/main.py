# iago henrique schlemper
from fastapi import FastAPI
from settings import HOST, PORT, RELOAD
import uvicorn

from routes import FuncionarioRouter
from routes import ClienteRouter
from routes import ProdutoRouter

# cria aplicação
app = FastAPI()

# rota padrão
@app.get("/", tags=["Root"], status_code=200)
def root():
    return {
        "detail": "API Pastelaria",
        "Swagger UI": "http://127.0.0.1:8000/docs",
        "ReDoc": "http://127.0.0.1:8000/redoc"
    }

# inclui rotas
app.include_router(FuncionarioRouter.router)
app.include_router(ClienteRouter.router)
app.include_router(ProdutoRouter.router)

if __name__ == "__main__":
    uvicorn.run("main:app", host=HOST, port=int(PORT), reload=RELOAD)