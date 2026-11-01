from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from cryptolab.history.models import HistoryRequest, parse_utc
from cryptolab.history.reader import DatasetReader
from cryptolab.history.storage import HistoryError, HistoryStore, job_request
from cryptolab.models import Interval, Symbol


def local_research_write(request: Request):
    # Enfileirar coleta é uma mutação local. Cabeçalho não simples impede POST cross-origin de formulário.
    if request.headers.get("x-cryptolab-research") != "1" or request.headers.get("origin", "") not in (
        "", "http://127.0.0.1:3100", "http://localhost:3100"
    ):
        raise HTTPException(403, "Solicitação local de pesquisa inválida.")


def history_router(store: HistoryStore) -> APIRouter:
    router = APIRouter(prefix="/api/v1/history", tags=["Pesquisa histórica pública"])

    def checked_request(symbol, interval, start, end):
        try:
            return HistoryRequest(symbol=symbol, interval=interval, start=start, end=end)
        except ValueError:
            raise HTTPException(422, "Período UTC inválido, desalinhado ou acima de 100.000 candles.") from None

    def checked_job(job_id):
        try:
            return store.job(job_id)
        except HistoryError:
            raise HTTPException(404, "Coleta não encontrada.") from None

    @router.get("/coverage")
    def coverage(symbol: Symbol, interval: Interval, start: str, end: str):
        return store.coverage(checked_request(symbol, interval, start, end))

    @router.get("/jobs")
    def jobs():
        return {"jobs": store.jobs()}

    @router.post("/jobs", dependencies=[Depends(local_research_write)], status_code=202)
    def enqueue(request: HistoryRequest):
        return store.enqueue(request)

    @router.get("/jobs/{job_id}")
    def get_job(job_id: str):
        return checked_job(job_id)

    @router.post("/jobs/{job_id}/{action}", dependencies=[Depends(local_research_write)])
    def control_job(job_id: str, action: Literal["pause", "resume"]):
        job = checked_job(job_id)
        return store.request_pause(job_id) if action == "pause" else store.enqueue(job_request(job))

    @router.get("/datasets")
    def datasets():
        return {"datasets": store.datasets()}

    @router.get("/datasets/{dataset_id}")
    def dataset(dataset_id: str, start: str | None = None, end: str | None = None,
                offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000)):
        try:
            data = DatasetReader(store).read(dataset_id, parse_utc(start) if start else None, parse_utc(end) if end else None)
        except HistoryError as exc:
            status = 404 if str(exc) == "DATASET_NOT_FOUND" else 409
            raise HTTPException(status, str(exc)) from None
        except ValueError:
            raise HTTPException(422, "Recorte UTC inválido.") from None
        return {"reference_hash": data.reference_hash, "manifest": data.manifest, "start_time": data.start_time,
                "end_time": data.end_time, "total_count": len(data.candles), "offset": offset, "limit": limit,
                "candles": [c.model_dump(mode="json") for c in data.candles[offset:offset+limit]]}

    return router
