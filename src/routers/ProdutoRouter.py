#Iago Henrique Schelmper
from fastapi import APIRouter, Depends, HTTPException, status, Request
from infra.rate_limit import limiter, get_rate_limit
from slowapi.errors import RateLimitExceeded
from sqlalchemy.orm import Session
from typing import List
from services.AuditoriaService import AuditoriaService

# Domain Schemas
from domain.schemas.ProdutoSchema import (
ProdutoCreate,
ProdutoUpdate,
ProdutoResponse
)
from domain.schemas.AuthSchema import FuncionarioAuth

# Infra
from infra.orm.ProdutoModel import ProdutoDB
from infra.database import get_db
from infra.dependencies import get_current_active_user
from infra.dependencies import require_group

router = APIRouter()

@router.get("/produto/publico", response_model=List[ProdutoResponse], tags=["Produto"], status_code=status.HTTP_200_OK)
@limiter.limit(get_rate_limit("moderate"))
async def get_produto_publico(request: Request, db: Session = Depends(get_db)):
    """Listar todos – pública"""
    try:
        produtos = db.query(ProdutoDB).all()
        return produtos
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar produtos: {str(e)}"
        )

@router.get("/produto/", response_model=List[ProdutoResponse], tags=["Produto"], status_code=status.HTTP_200_OK)
@limiter.limit(get_rate_limit("moderate"))
async def get_produto(
    request: Request,
    db: Session = Depends(get_db),
    current_user: FuncionarioAuth = Depends(get_current_active_user)
):
    """Listar todos – protegida"""
    try:
        produtos = db.query(ProdutoDB).all()
        return produtos
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar produtos: {str(e)}"
        )

@router.get("/produto/{id}", response_model=ProdutoResponse, tags=["Produto"], status_code=status.HTTP_200_OK)
@limiter.limit(get_rate_limit("moderate"))
async def get_produto(request: Request, id: int, db: Session = Depends(get_db),
    current_user: FuncionarioAuth = Depends(get_current_active_user)):
    """Retorna um produto específico pelo ID"""
    try:
        produto = db.query(ProdutoDB).filter(ProdutoDB.id == id).first()
        if not produto:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado")
        return produto
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar produto: {str(e)}"
        )

@router.post("/produto/", response_model=ProdutoResponse, status_code=status.HTTP_201_CREATED, tags=["Produto"])
@limiter.limit(get_rate_limit("default"))
async def post_produto(request: Request, produto_data: ProdutoCreate, db: Session = Depends(get_db),
    current_user: FuncionarioAuth = Depends(require_group([1]))):
    """Cria um novo produto"""
    try:
        # Verifica se já existe produto com este código
        #existing_produto = db.query(ProdutoDB).filter(ProdutoDB.codigo == produto_data.codigo).first()
        #if existing_produto:
        #    raise HTTPException(
        #    status_code=status.HTTP_400_BAD_REQUEST, detail="Já existe um produto com este código"
        #    )
        # Cria o novo produto
        novo_produto = ProdutoDB(
            id=None, # Será auto-incrementado
            nome=produto_data.nome,
            descricao=produto_data.descricao,
            valor_unitario=produto_data.valor_unitario,
            foto=produto_data.foto
        )
        db.add(novo_produto)
        db.commit()
        db.refresh(novo_produto)

        # ✅ dados novos
        dados_novos = {
            "id": novo_produto.id,
            "nome": novo_produto.nome,
            "descricao": novo_produto.descricao,
            "valor_unitario": float(novo_produto.valor_unitario),
            "foto": novo_produto.foto
        }

        AuditoriaService.registrar_acao(
            db=db,
            funcionario_id=current_user.id,
            acao="CREATE",
            recurso="PRODUTO",
            recurso_id=novo_produto.id,
            dados_antigos=None,
            dados_novos=dados_novos,
            request=request
        )

        return novo_produto
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao criar produto: {str(e)}"
        )

@router.put("/produto/{id}", response_model=ProdutoResponse, tags=["Produto"], status_code=status.HTTP_200_OK)
@limiter.limit(get_rate_limit("default"))
async def put_produto(request: Request, id: int, produto_data: ProdutoUpdate, db: Session = Depends(get_db),
    current_user: FuncionarioAuth = Depends(require_group([1]))):
    """Atualiza um produto existente"""
    try:
        produto = db.query(ProdutoDB).filter(ProdutoDB.id == id).first()
        if not produto:
            raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado"
            )
        # Verifica se está tentando atualizar para um código que já existe
        #if produto_data.codigo and produto_data.codigo != produto.codigo:
        #    existing_produto = db.query(ProdutoDB).filter(ProdutoDB.codigo == produto_data.codigo).first()
        #    if existing_produto:
        #        raise HTTPException(
        #            status_code=status.HTTP_400_BAD_REQUEST, detail="Já existe um produto com este código"
        #        )
        # Atualiza apenas os campos fornecidos
        update_data = produto_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(produto, field, value)
        # ✅ dados antigos
        dados_antigos = {
            "id": produto.id,
            "nome": produto.nome,
            "descricao": produto.descricao,
            "valor_unitario": float(produto.valor_unitario),
            "foto": produto.foto
        }

        # Atualiza campos
        update_data = produto_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(produto, field, value)

        db.commit()
        db.refresh(produto)

        # ✅ dados novos
        dados_novos = {
            "id": produto.id,
            "nome": produto.nome,
            "descricao": produto.descricao,
            "valor_unitario": float(produto.valor_unitario),
            "foto": produto.foto
        }

        # ✅ auditoria
        AuditoriaService.registrar_acao(
            db=db,
            funcionario_id=current_user.id,
            acao="UPDATE",
            recurso="PRODUTO",
            recurso_id=produto.id,
            dados_antigos=dados_antigos,
            dados_novos=dados_novos,
            request=request
        )

        return produto
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao atualizar produto: {str(e)}"
        )

@router.delete("/produto/{id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Produto"], summary="Remover produto")
@limiter.limit(get_rate_limit("restrictive"))
async def delete_produto(request: Request, id: int, db: Session = Depends(get_db),
    current_user: FuncionarioAuth = Depends(require_group([1]))):
    """Remove um produto"""
    try:
        produto = db.query(ProdutoDB).filter(ProdutoDB.id == id).first()
        if not produto:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Produto não encontrado"
            )
        # ✅ dados antes de deletar
        dados_antigos = {
            "id": produto.id,
            "nome": produto.nome,
            "descricao": produto.descricao,
            "valor_unitario": float(produto.valor_unitario),
            "foto": produto.foto
        }

        db.delete(produto)
        db.commit()

        # ✅ auditoria
        AuditoriaService.registrar_acao(
            db=db,
            funcionario_id=current_user.id,
            acao="DELETE",
            recurso="PRODUTO",
            recurso_id=id,
            dados_antigos=dados_antigos,
            dados_novos=None,
            request=request
        )

        return None
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao deletar produto: {str(e)}"
        )