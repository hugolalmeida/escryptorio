import logging
import time
from email.utils import parsedate_to_datetime

import requests
from pybit.exceptions import FailedRequestError, InvalidRequestError
from pybit.unified_trading import HTTP

from cryptolab.history.models import HistoryRequest
from cryptolab.history.storage import HistoryError


class HistoryTransportError(HistoryError):
    def __init__(self, code: str, retryable: bool = False, retry_after: float = 0):
        super().__init__(code)
        self.retryable, self.retry_after = retryable, retry_after


def retry_delay(headers: dict | None) -> float:
    headers = {str(k).lower(): v for k, v in (headers or {}).items()}
    delay = 0.0
    try:
        retry = headers.get("retry-after", "0")
        try:
            delay = float(retry)
        except ValueError:
            delay = parsedate_to_datetime(retry).timestamp() - time.time()
        reset = float(headers.get("x-bapi-limit-reset-timestamp", 0))/1000 - time.time()
        delay = max(delay, reset, 0)
    except (ValueError, TypeError, OverflowError):
        pass
    if not 0 <= delay <= 60:
        raise HistoryTransportError("RATE_LIMIT_WAIT_TOO_LONG")
    return delay


class HistoricalBybit:
    """Cliente próprio do processo histórico: um GET público, sem retries ocultos do SDK."""

    def __init__(self):
        logging.getLogger("pybit._http_manager").setLevel(logging.CRITICAL)
        self.__session = HTTP(testnet=False, timeout=6, max_retries=1, retry_delay=0,
            retry_codes={-999999}, force_retry=False, log_requests=False, return_response_headers=True)

    def page(self, request: HistoryRequest) -> dict:
        if request.expected_count > 1000:
            raise HistoryTransportError("PAGE_LIMIT_EXCEEDED")
        try:
            # end na API é inclusivo em ms; o domínio histórico usa fim exclusivo.
            result, _, headers = self.__session.get_kline(category="spot", symbol=request.symbol,
                interval=request.interval, start=request.start_time*1000, end=request.end_time*1000-1,
                limit=1000)
            if result.get("retCode") != 0:
                code = result.get("retCode")
                raise HistoryTransportError(f"BYBIT_CODE_{code}" if isinstance(code, int) else "BYBIT_INVALID_RESPONSE",
                                            code in (10000, 10006, 10016, 429))
            result["_next_delay"] = retry_delay(headers) if str(headers.get("X-Bapi-Limit-Status")) == "0" else 0
            return result
        except HistoryTransportError:
            raise
        except (FailedRequestError, InvalidRequestError) as exc:
            code = exc.status_code
            name = "BYBIT_FORBIDDEN" if code == 403 else f"BYBIT_CODE_{code}"
            raise HistoryTransportError(name, code in (408, 429, 500, 502, 503, 504, 10000, 10006, 10016),
                                        retry_delay(exc.resp_headers)) from None
        except requests.RequestException:
            raise HistoryTransportError("BYBIT_UNAVAILABLE", retryable=True) from None
        except Exception:
            raise HistoryTransportError("BYBIT_INVALID_RESPONSE") from None
