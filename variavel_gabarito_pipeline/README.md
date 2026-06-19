# Variavel no Gabarito Pipeline

Pipeline Python para substituir e evoluir a logica de apuracao feita hoje em Power Query/Excel.

## Objetivo desta fase

Esta primeira entrega cria a base do projeto:

- estrutura de pastas por camada;
- configuracao de caminhos em YAML;
- logger estruturado simples;
- utilitario para listar arquivos Excel;
- runner de inventario de arquivos Excel;
- testes basicos.

Os calculos da figura `PROMOTOR DE VENDAS` ainda nao foram implementados.

## Requisitos

- Python 3.11 ou superior
- pandas
- openpyxl
- xlsxwriter
- pyyaml
- pytest

## Instalacao

```powershell
cd variavel_gabarito_pipeline
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
```

## Configuracao

Os caminhos ficam em `config/paths.yaml`.

As fontes brutas devem ser colocadas em:

- `data/raw/metas`
- `data/raw/indicadores`
- `data/raw/agentes`
- `data/raw/supervisores`
- `data/raw/aderencia_red`
- `data/raw/pesos`
- `data/raw/escalonada`
- `data/raw/gabarito_validacao`

## Executar inventario

```powershell
python -m pipeline.runners.run_inventario
```

Saida gerada:

```text
data/processed/inventario_arquivos.csv
```

Colunas do inventario:

- `arquivo`
- `pasta_origem`
- `aba`
- `qtd_linhas`
- `qtd_colunas`
- `colunas_detectadas`

## Executar staging

```powershell
python -m pipeline.runners.run_staging
```

Saidas principais:

- `data/processed/staging/stg_metas.csv`
- `data/processed/staging/stg_indicadores.csv`
- `data/processed/staging/stg_agentes.csv`
- `data/processed/staging/stg_agentes_promotor.csv`
- `data/processed/dimensions/dim_rotas_promotor.csv`
- `data/processed/staging/stg_aderencia_red.csv`
- `data/processed/staging/stg_pesos.csv`
- `data/processed/staging/diag_pesos.csv`
- `data/processed/staging/stg_escalonada_promotor.csv`

## Testes

```powershell
pytest
```

## Arquitetura

- `core`: configuracao, caminhos, logger, excecoes e utilitarios.
- `io`: leitores e escritores de arquivos.
- `staging`: padronizacao inicial das fontes.
- `domain`: regras de negocio reutilizaveis.
- `figures`: orquestracao por figura comercial.
- `validation`: comparacao contra gabaritos e validacoes.
- `runners`: pontos de entrada executaveis.
