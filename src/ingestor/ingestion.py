import asyncio
import logging

import httpx

from ingestor.config import (
    BACKOFFS,
    STATUS_RETRY,
)
from ingestor.exceptions import (
    DataPipelineError,
    ExtractionError,
)
from ingestor.http import consultar_api
from ingestor.models import (
    ConcorrenciaTracker,
    FonteAPI,
    ResultadoIngestao,
)
from ingestor.storage import salvar_json

logger = logging.getLogger(
    __name__
)

def status_permite_retry(
        status: int,
) -> bool:
    return status in STATUS_RETRY


async def extrair_com_retry(
        client: httpx.AsyncClient,
        semaforo: asyncio.Semaphore,
        tracker: ConcorrenciaTracker,
        fonte: FonteAPI,
) -> dict | list:
    total_tentativas = len(BACKOFFS) + 1 

    ultimo_erro: Exception | None = None

    for tentativa in range(total_tentativas):

        numero_tentativa = tentativa + 1

        try:
            async with semaforo:
                tracker.entrar()

                logger.info(
                    "CONCORRÊNCIA | fonte=%s | ativos=%d | pico=%d",
                    fonte.nome,
                    tracker.ativos,
                    tracker.pico,
                )
                try :
                    return await consultar_api(client, fonte)
                finally:
                    tracker.sair()

        except httpx.HTTPStatusError as erro:
            status = erro.response.status_code

            if not status_permite_retry(status):
                raise ExtractionError(
                    f"HTTP {status} não retentável",
                    source=fonte.nome,
                ) from erro

            ultimo_erro = erro

        except (
            httpx.TimeoutException,
            httpx.NetworkError,
        ) as erro:

            ultimo_erro = erro

        except httpx.RequestError as erro:
            raise ExtractionError(
                "Falha HTTP não retentável",
                source=fonte.nome,
            ) from erro

        ultima_tentativa = (
            tentativa == total_tentativas - 1
        )

        if ultima_tentativa:
            break

        espera = BACKOFFS[tentativa]

        logger.warning(
            "RETRY | fonte=%s | tentativa=%d/%d | espera=%.1fs | erro=%s",
            fonte.nome,
            numero_tentativa,
            total_tentativas,
            espera,
            ultimo_erro,
        )

        await asyncio.sleep(espera)

    if ultimo_erro is None:
        raise ExtractionError(
            "Extração falhou sem causa registrada",
            source=fonte.nome,
        )

    raise ExtractionError(
        f"Falha após {total_tentativas} tentativas",
        source=fonte.nome,
    ) from ultimo_erro

async def processar_fonte(
    client: httpx.AsyncClient,
    semaforo: asyncio.Semaphore,
    tracker: ConcorrenciaTracker,
    fonte: FonteAPI,
) -> ResultadoIngestao:
    try:
        dados = await extrair_com_retry(
            client,
            semaforo,
            tracker,
            fonte,
        )

        await salvar_json(
            fonte.arquivo,
            dados,
            fonte=fonte.nome,
        )

        logger.info(
            "FONTE CONCLUÍDA | fonte=%s",
            fonte.nome,
        )

        return ResultadoIngestao(
            fonte=fonte.nome,
            sucesso=True,
            arquivo=fonte.arquivo,
        )
    except DataPipelineError as erro:
        logger.error(
            "FONTE COM FALHA | fonte=%s | erro=%s",
            fonte.nome,
            erro,
        )

        return ResultadoIngestao(
            fonte=fonte.nome,
            sucesso=False,
            erro=str(erro),
        )
    except Exception:
        logger.exception(
            "ERRO INESPERADO | fonte=%s",
            fonte.nome,
        )

        raise 

async def executar_sequencial(
        client: httpx.AsyncClient,
        semaforo: asyncio.Semaphore,
        tracker: ConcorrenciaTracker,
        fontes: list[FonteAPI],
) -> list[ResultadoIngestao]:
    resultados = []

    for fonte in fontes:
        resultado = await processar_fonte(
            client,
            semaforo,
            tracker,
            fonte,
        )

        resultados.append(resultado)

    return resultados

async def executar_assincrono(
        client: httpx.AsyncClient,
        semaforo: asyncio.Semaphore,
        tracker: ConcorrenciaTracker,
        fontes: list[FonteAPI],
) -> list[ResultadoIngestao]:
    coroutines = [
        processar_fonte(
            client,
            semaforo,
            tracker,
            fonte,
        )
        for fonte in fontes
    ]

    return await asyncio.gather(
        *coroutines
    )