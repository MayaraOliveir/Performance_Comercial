# SUPERVISOR DE VENDAS

Documentacao tecnica curta da V1 da figura `SUPERVISOR DE VENDAS`.

## Arquivos criados

- `src/pipeline/staging/estrutura_supervisor_vendas.py`
- `src/pipeline/staging/pesos_supervisor_vendas.py`
- `src/pipeline/figures/supervisor_vendas.py`
- `src/pipeline/runners/run_supervisor_vendas.py`
- `src/pipeline/validation/supervisor_vendas.py`
- `src/pipeline/runners/run_validacao_supervisor_vendas.py`

## Fontes usadas

- Gabarito: `data/raw/gabarito_validacao/Variavel no Gabarito 18 de Junho.xlsx`
- Aba materializada de base: `Estrutura Supervisor Vendas`
- Aba final de validacao: `SUPERVISOR DE VENDAS`
- Pesos: aba `Apoio Sup. Vendas`
- Escalonada: aba `Escalonada`
- Auditoria de realizados: `data/processed/staging/stg_indicadores.csv`
- Auditoria de metas: `data/processed/staging/stg_metas.csv`
- Aderencia RED: `data/processed/staging/stg_aderencia_red.csv`

## Regra de calculo

- Chave final da figura: `Centro + Supervisao`.
- Base de calculo fiel ao gabarito: valores materializados na aba `Estrutura Supervisor Vendas`.
- KPIs considerados: `MKO`, `MKR`, `MKD`, `MCN`, `RED`, `FRD`, `EFV`.
- Performance por KPI: `Realizado / Meta`, quando ambos existem e a meta permite calculo.
- Atingimento por KPI: `Performance * Peso`.
- Atingimento total: soma dos atingimentos finais dos KPIs calculados.
- Status da performance: derivado da escala atingida aplicada ao atingimento total.

## Regra de aderencia RED/FRD

Para `RED` e `FRD`, existe gatilho pela aderencia RED:

- Se `AderenciaRED` for numerica e `< 0.85`:
  - `AtingimentoRED = 0`
  - `AtingimentoFRD = 0`
  - `StatusGatilhoRED = "Zerado por aderencia RED < 85%"`
- Se `AderenciaRED` for numerica e `>= 0.85`:
  - calcular normalmente `Performance * Peso`.
- Se `AderenciaRED` for nula, `"-"`, erro Excel ou nao numerica:
  - calcular normalmente `Performance * Peso`;
  - `StatusGatilhoRED = "Sem aderencia numerica - gabarito calcula normalmente"`.

O diagnostico explicito mantem:

- `AderenciaRED`
- `AderenciaREDNumerica`
- `StatusAderenciaRED`
- `StatusGatilhoRED`

## Pesos

Os pesos da figura sao extraidos da aba `Apoio Sup. Vendas`.

A chave de peso depende do tipo de supervisor identificado a partir do texto de `Supervisao` e do KPI. Os pesos sao aplicados por KPI na etapa de calculo, mantendo status de auditoria quando o peso e encontrado ou ausente.

## Escalonada

A figura usa o bloco da aba `Escalonada` identificado como:

`OPERADOR DE EXECUCAO E VENDAS / VENDEDOR/ SUP. VENDAS`

A escala e aplicada ao `AtingimentoTotal` para obter:

- `EscalaAtingida`
- `StatusPerformance`

## Saidas geradas

Fatos:

- `data/processed/facts/fat_supervisor_vendas_base.csv`
- `data/processed/facts/fat_supervisor_vendas_calculo.csv`
- `data/processed/facts/fat_supervisor_vendas_final.csv`

Staging:

- `data/processed/staging/stg_estrutura_supervisor_vendas.csv`
- `data/processed/staging/stg_pesos_supervisor_vendas.csv`

Validacao e auditoria:

- `data/processed/validation/auditoria_supervisor_vendas_realizados.csv`
- `data/processed/validation/auditoria_supervisor_vendas_metas.csv`
- `data/processed/validation/resumo_supervisor_vendas.csv`
- `data/processed/validation/stg_gabarito_supervisor_vendas.csv`
- `data/processed/validation/validacao_supervisor_vendas_gabarito.csv`
- `data/processed/validation/resumo_validacao_supervisor_vendas.csv`
- `data/processed/validation/diferencas_criticas_supervisor_vendas.csv`

## Validacao contra gabarito

Resultado da validacao contra a aba final `SUPERVISOR DE VENDAS`:

- Linhas no gabarito: `409`
- Linhas na pipeline: `409`
- Chaves comparaveis: `404`
- Excecoes por `#N/D` no centro: `5`
- `AtingimentoTotal`: `100%`
- `StatusPerformance`: `100%`
- Divergencias criticas: `0`

As 5 excecoes por erro Excel no centro sao classificadas como:

- `ExcecaoCentroErroExcel = true`
- `StatusComparacaoChave = "Nao comparavel por erro Excel no centro"`

## Ressalva

As metas usadas no calculo fiel ao gabarito vem da aba materializada `Estrutura Supervisor Vendas`.

A origem externa das metas ajustadas por `Rota Sup`/Supervisor ainda esta pendente de identificacao. As bases `014 - Metas` e `stg_metas.csv` nao explicaram as metas da estrutura com confianca suficiente para substituir a fonte materializada.

## Pergunta para negocio

Qual fonte ou processo gera as metas ajustadas por `Rota Sup`/Supervisor usadas na `Estrutura Supervisor Vendas`?
