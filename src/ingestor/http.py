import logging

import httpx

from ingestor.models import FonteAPI

logger = logging.getLogger(
    __name__
)


async def consultar_api(
    client: httpx.AsyncClient,
    fonte: FonteAPI,
) -> dict | list:
    logger.info(
        "HTTP INICIADO | fonte=%s",
        fonte.nome,
    )

    resposta = await client.get(fonte.url)
    resposta.raise_for_status()
    dados = resposta.json()

    logger.info(
        "HTTP CONCLUÍDO | fonte=%s | status=%d",
        fonte.nome,
        resposta.status_code,
    )

    return dados