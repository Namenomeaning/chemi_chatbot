from fastapi import APIRouter, Depends

from app.api.deps import check_rate_limit, get_env, get_settings
from app.schemas.query import QueryRequest, QueryResponse
from app.services.query import answer_query

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def query(
    request: QueryRequest,
    env=Depends(get_env),
    settings=Depends(get_settings),
    principal=Depends(check_rate_limit),
):
    return await answer_query(request, settings, env, principal)
