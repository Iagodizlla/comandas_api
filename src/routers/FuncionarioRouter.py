#Iago Henrique Schelmper
from fastapi import APIRouter, Depends, HTTPException, status, Request
from infra.rate_limit import limiter, get_rate_limit
from slowapi.errors import RateLimitExceeded
from sqlalchemy.orm import Session
from typing import List
from services.AuditoriaService import AuditoriaService

# Domain Schemas
from domain.schemas.FuncionarioSchema import (
FuncionarioCreate,
FuncionarioUpdate,
FuncionarioResponse
)
from domain.schemas.AuthSchema import FuncionarioAuth

# Infra
from infra.orm.FuncionarioModel import FuncionarioDB
from infra.database import get_db
from infra.security import get_password_hash
from infra.dependencies import get_current_active_user, require_group

router = APIRouter()

@router.get("/funcionario/", response_model=List[FuncionarioResponse], tags=["Funcionário"], status_code=status.HTTP_200_OK)
@limiter.limit(get_rate_limit("moderate"))
async def get_funcionario(request: Request, db: Session = Depends(get_db),
    current_user: FuncionarioAuth = Depends(require_group([1]))):
    """Retorna todos os funcionários"""
    try:
        funcionarios = db.query(FuncionarioDB).all()
        return funcionarios
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar funcionários: {str(e)}"
        )

@router.get("/funcionario/{id}", response_model=FuncionarioResponse, tags=["Funcionário"], status_code=status.HTTP_200_OK)
@limiter.limit(get_rate_limit("low"))
async def get_funcionario(request: Request, id: int, db: Session = Depends(get_db),
    current_user: FuncionarioAuth = Depends(get_current_active_user)):
    """Retorna um funcionário específico pelo ID"""
    try:
        funcionario = db.query(FuncionarioDB).filter(FuncionarioDB.id == id).first()
        if not funcionario:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Funcionário não encontrado")
        return funcionario
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar funcionário: {str(e)}"
        )

@router.post("/funcionario/", response_model=FuncionarioResponse, status_code=status.HTTP_201_CREATED, tags=["Funcionário"], summary="Criar novo funcionário - protegida por JWT e grupo 1")
@limiter.limit(get_rate_limit("restrictive"))
async def post_funcionario(request: Request, funcionario_data: FuncionarioCreate, db: Session = Depends(get_db), current_user: FuncionarioAuth = Depends(require_group([1]))):
    try:
        # Validar se o grupo informado é válido
        if funcionario_data.grupo not in [1, 2, 3]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Grupo inválido. Apenas grupos 1 (Admin), 2 (Atendimento Balcão) ou 3 (Atendimento Caixa) são permitidos." )
        # Verifica se já existe funcionário com este CPF
        existing_funcionario = db.query(FuncionarioDB).filter(FuncionarioDB.cpf == funcionario_data.cpf).first()
        if existing_funcionario:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Já existe um funcionário com este CPF")
        # Hash da senha
        hashed_password = get_password_hash(funcionario_data.senha)
        # Cria o novo funcionário
        novo_funcionario = FuncionarioDB(id=None, nome=funcionario_data.nome, matricula=funcionario_data.matricula, cpf=funcionario_data.cpf, telefone=funcionario_data.telefone, grupo=funcionario_data.grupo, senha=hashed_password )
        db.add(novo_funcionario)
        db.commit()
        db.refresh(novo_funcionario) # Depois de tudo executado e antes do return, registra a ação na auditoria
        AuditoriaService.registrar_acao(
            db=db,
            funcionario_id=current_user.id,
            acao="CREATE",
            recurso="FUNCIONARIO",
            recurso_id=novo_funcionario.id,
            dados_antigos=None,
            dados_novos=novo_funcionario,
            request=request
        )
        return novo_funcionario
    except RateLimitExceeded:
        # Propagar exceção original para o handler personalizado
        raise
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao criar funcionário: {str(e)}")

@router.put("/funcionario/{id}", response_model=FuncionarioResponse, tags=["Funcionário"], status_code=status.HTTP_200_OK)
@limiter.limit(get_rate_limit("restrictive"))  # ✅ corrigido
async def put_funcionario(
    request: Request,
    id: int,
    funcionario_data: FuncionarioUpdate,
    db: Session = Depends(get_db),
    current_user: FuncionarioAuth = Depends(require_group([1]))
):
    try:
        funcionario = db.query(FuncionarioDB).filter(FuncionarioDB.id == id).first()

        if not funcionario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Funcionário não encontrado"
            )

        # ✅ COPIA DOS DADOS ANTIGOS (ANTES DE ALTERAR)
        dados_antigos = {
            "id": funcionario.id,
            "nome": funcionario.nome,
            "cpf": funcionario.cpf,
            "matricula": funcionario.matricula,
            "grupo": funcionario.grupo
        }

        # Verifica CPF duplicado
        if funcionario_data.cpf and funcionario_data.cpf != funcionario.cpf:
            existing_funcionario = db.query(FuncionarioDB).filter(
                FuncionarioDB.cpf == funcionario_data.cpf
            ).first()

            if existing_funcionario:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Já existe um funcionário com este CPF"
                )

        # Hash da senha
        if funcionario_data.senha:
            funcionario_data.senha = get_password_hash(funcionario_data.senha)

        # Atualiza campos
        update_data = funcionario_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(funcionario, field, value)

        db.commit()
        db.refresh(funcionario)

        # ✅ DADOS NOVOS (DEPOIS DO UPDATE)
        dados_novos = {
            "id": funcionario.id,
            "nome": funcionario.nome,
            "cpf": funcionario.cpf,
            "matricula": funcionario.matricula,
            "grupo": funcionario.grupo
        }

        # ✅ AUDITORIA
        AuditoriaService.registrar_acao(
            db=db,
            funcionario_id=current_user.id,
            acao="UPDATE",
            recurso="FUNCIONARIO",
            recurso_id=funcionario.id,
            dados_antigos=dados_antigos,
            dados_novos=dados_novos,
            request=request
        )

        return funcionario

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao atualizar funcionário: {str(e)}"
        )

@router.delete("/funcionario/{id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Funcionário"])
@limiter.limit(get_rate_limit("critical"))
async def delete_funcionario(
    request: Request,
    id: int,
    db: Session = Depends(get_db),
    current_user: FuncionarioAuth = Depends(require_group([1]))
):
    try:
        funcionario = db.query(FuncionarioDB).filter(FuncionarioDB.id == id).first()

        if not funcionario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Funcionário não encontrado"
            )

        # ✅ SALVA OS DADOS ANTES
        dados_antigos = {
            "id": funcionario.id,
            "nome": funcionario.nome,
            "cpf": funcionario.cpf,
            "matricula": funcionario.matricula,
            "grupo": funcionario.grupo
        }

        db.delete(funcionario)
        db.commit()

        # ✅ AGORA REGISTRA
        AuditoriaService.registrar_acao(
            db=db,
            funcionario_id=current_user.id,
            acao="DELETE",
            recurso="FUNCIONARIO",
            recurso_id=id,
            dados_antigos=dados_antigos,
            dados_novos=None,
            request=request
        )

    except RateLimitExceeded:
        raise
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao deletar funcionário: {str(e)}"
        )