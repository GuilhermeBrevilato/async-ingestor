import asyncio
import logging
import time

import httpx

from ingestor.config import (
    FONTES,
    HTTP_TIMEOUT,
    MAX_CONCORRENCIA,
)
from ingestor.ingestion import (
    executar_assincrono,
    executar_sequencial,
)
from ingestor.models import (
    ConcorrenciaTracker,
    ResultadoIngestao,
)

logging.basicConfig(
    level=logging.INFO,
    format=("%(asctime)s | %(levelname)s | %(name)s | %(message)s"),
    datefmt="%H:%M:%S",
)

logger = logging.getLogger(__name__)


def resumir(
    modo: str,
    resultados: list[ResultadoIngestao],
    duracao: float,
    tracker: ConcorrenciaTracker,
) -> None:
    sucessos = sum(resultado.sucesso for resultado in resultados)

    falhas = len(resultados) - sucessos

    logger.info(
        "RESULTADO | modo=%s | tempo=%.2fs | sucessos=%d | falhas=%d | pico_concorrencia=%d",
        modo,
        duracao,
        sucessos,
        falhas,
        tracker.pico,
    )


async def testar_sequencial() -> tuple[
    list[ResultadoIngestao],
    float,
    ConcorrenciaTracker,
]:
    semaforo = asyncio.Semaphore(MAX_CONCORRENCIA)
    tracker = ConcorrenciaTracker()

    inicio = time.perf_counter()

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resultados = await executar_sequencial(
            client,
            semaforo,
            tracker,
            FONTES,
        )

    duracao = time.perf_counter() - inicio

    return resultados, duracao, tracker


async def testar_assincrono() -> tuple[
    list[ResultadoIngestao],
    float,
    ConcorrenciaTracker,
]:
    semaforo = asyncio.Semaphore(MAX_CONCORRENCIA)
    tracker = ConcorrenciaTracker()

    inicio = time.perf_counter()

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resultados = await executar_assincrono(
            client,
            semaforo,
            tracker,
            FONTES,
        )

    duracao = time.perf_counter() - inicio

    return resultados, duracao, tracker


async def main() -> None:
    logger.info("TESTE SEQUENCIAL INICIADO")

    resultados_seq, tempo_seq, tracker_seq = await testar_sequencial()

    resumir("sequencial", resultados_seq, tempo_seq, tracker_seq)

    logger.info("TESTE ASSÍNCRONO INICIADO")

    resultados_async, tempo_async, tracker_async = await testar_assincrono()

    resumir("assincrono", resultados_async, tempo_async, tracker_async)

    if tempo_async > 0:
        ganho = tempo_seq / tempo_async
        logger.info(
            "COMPARAÇÃO | sequencial=%.2fs | assincrono=%.2fs | speedup=%.2fx",
            tempo_seq,
            tempo_async,
            ganho,
        )

    if tracker_async.pico <= MAX_CONCORRENCIA:
        logger.info(
            "RATE LIMIT VALIDADO | limite=%d | pico=%d",
            MAX_CONCORRENCIA,
            tracker_async.pico,
        )
    else:
        logger.error(
            "RATE LIMIT VIOLADO | limite=%d | pico=%d",
            MAX_CONCORRENCIA,
            tracker_async.pico,
        )


if __name__ == "__main__":
    asyncio.run(main())
