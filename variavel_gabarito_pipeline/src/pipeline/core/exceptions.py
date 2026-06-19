"""Excecoes especificas da pipeline."""


class PipelineError(Exception):
    """Erro base para falhas controladas da pipeline."""


class ConfigurationError(PipelineError):
    """Erro de configuracao ausente ou invalida."""


class DataReadError(PipelineError):
    """Erro ao ler dados de entrada."""
