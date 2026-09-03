# async-ingestor

Ingestor assíncrono que consulta múltiplas APIs públicas de forma concorrente, controlando o número de requisições executadas ao mesmo tempo.

Projeto de consolidação de uma semana de estudo aprofundado de `asyncio`.

## O que faz

* Consulta 5 fontes públicas (BrasilAPI, IBGE e Open-Meteo) de forma concorrente.
* Compara execução sequencial vs. assíncrona, medindo o tempo total de execução de cada abordagem.
* Limita a concorrência e persiste os dados brutos em `data/bronze/`.

## Conceitos aplicados

* `asyncio.gather` para executar múltiplas corrotinas concorrentemente e aguardar a conclusão de todas.
* `Semaphore` para limitar quantas operações podem acessar simultaneamente o trecho controlado da ingestão.
* Retry com backoff exponencial para repetir requisições que falharam sem realizar novas tentativas imediatamente.
* `httpx.AsyncClient` com connection pooling para reutilizar conexões HTTP entre as requisições.
* I/O de arquivo assíncrono com `aiofiles` para evitar bloquear o event loop durante a persistência.
* Hierarquia de exceções customizadas para separar e propagar erros das diferentes etapas do pipeline.

## Como rodar

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cd src
python -m ingestor.main
```

## Estrutura

```text
src/ingestor/
├── models.py      # dataclasses de domínio
├── exceptions.py  # hierarquia de erros do pipeline
├── config.py      # configuração e fontes
├── http.py        # uma chamada HTTP
├── storage.py     # persistência assíncrona
├── ingestion.py   # orquestração: retry, semaphore, gather
└── main.py        # ponto de entrada e medição
```

## O que observar

Na execução assíncrona, as fontes podem avançar durante os períodos de espera de I/O umas das outras, reduzindo o tempo total em comparação com a execução sequencial. O `Semaphore` mantém o pico de concorrência dentro do limite definido, enquanto cada resultado obtido com sucesso é persistido na camada `bronze`.

Como o projeto utiliza apenas cinco fontes e algumas requisições possuem tempos de resposta relativamente curtos, o ganho de desempenho não precisa ser muito grande. O objetivo da comparação é demonstrar o efeito da concorrência em operações predominantemente de I/O e, principalmente, mostrar como controlar essa concorrência de forma previsível.
