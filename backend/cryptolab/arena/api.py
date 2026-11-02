from threading import BoundedSemaphore

from fastapi import APIRouter, Depends, HTTPException

from cryptolab.arena.models import ArenaConfig, ExecuteRequest
from cryptolab.arena.service import ArenaError, ArenaService
from cryptolab.history.api import local_research_write
from cryptolab.history.storage import HistoryError, HistoryStore
from cryptolab.research.service import ResearchError


def arena_router(store: HistoryStore, gate: BoundedSemaphore) -> APIRouter:
    router = APIRouter(prefix="/api/v1/arena", tags=["Arena histórica offline"])
    service = ArenaService(store)

    def checked(fn, *args):
        if not gate.acquire(blocking=False):
            raise HTTPException(429, "Pesquisa ocupada; aguarde a execução local.")
        try:
            return fn(*args)
        except (ArenaError, ResearchError, HistoryError) as exc:
            raise HTTPException(409, str(exc)) from None
        except ValueError:
            raise HTTPException(409, "Experimento, resultado ou configuração inválida.") from None
        finally:
            gate.release()

    @router.post("/experiments", dependencies=[Depends(local_research_write)])
    def create(config: ArenaConfig):
        return checked(service.create, config)

    @router.get("/experiments")
    def list_experiments():
        return {"experiments": service.experiments()}

    @router.get("/experiments/{identifier}")
    def experiment(identifier: str):
        return checked(service.experiment, identifier)

    @router.post("/execute", dependencies=[Depends(local_research_write)])
    def execute(request: ExecuteRequest):
        return checked(service.execute, request.experiment_id)

    @router.get("/experiments/{identifier}/result")
    def result(identifier: str):
        return checked(service.result, identifier)

    return router
