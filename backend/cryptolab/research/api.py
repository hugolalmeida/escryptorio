from threading import BoundedSemaphore

from fastapi import APIRouter, Depends, HTTPException

from cryptolab.history.api import local_research_write
from cryptolab.history.storage import HistoryError, HistoryStore
from cryptolab.research.service import ProtocolRequest, ResearchService, RunRequest


def research_router(store: HistoryStore) -> APIRouter:
    router = APIRouter(prefix="/api/v1/research", tags=["Backtests offline, somente simulação"])
    service = ResearchService(store)
    gate = BoundedSemaphore(1)

    def checked(fn, *args):
        if not gate.acquire(blocking=False):
            raise HTTPException(429, "Pesquisa ocupada; aguarde a execução local.")
        try:
            return fn(*args)
        except (ValueError, HistoryError) as exc:
            # Only explicit public errors; Pydantic error payloads never echoed.
            from cryptolab.research.service import ResearchError
            message = str(exc) if isinstance(exc, (ResearchError, HistoryError)) else "Configuração inválida ou warm-up insuficiente."
            raise HTTPException(409, message) from None
        finally:
            gate.release()

    @router.post("/protocols", dependencies=[Depends(local_research_write)])
    def freeze(request: ProtocolRequest):
        return checked(service.freeze, request)

    @router.get("/protocols/{identifier}")
    def protocol(identifier: str):
        return checked(service.protocol, identifier)

    @router.post("/runs", dependencies=[Depends(local_research_write)])
    def run(request: RunRequest):
        return checked(service.run, request)

    @router.get("/runs")
    def runs():
        return {"runs": service.runs()}

    @router.get("/runs/{identifier}")
    def result(identifier: str):
        return checked(service.result, identifier)

    @router.post("/runs/{identifier}/verify", dependencies=[Depends(local_research_write)])
    def verify(identifier: str):
        return checked(service.verify, identifier)

    return router
