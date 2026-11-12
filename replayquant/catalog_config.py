"""Configuração resolvida schema 6: catálogo explícito e janela de negociação."""
from dataclasses import dataclass
from .catalog import Catalog, Window
from .risk_models import RiskConfig
from .validation import ValidationError


@dataclass(frozen=True)
class CatalogConfig(RiskConfig):
    catalog: Catalog | None = None
    window: Window | None = None

    def __post_init__(self):
        if not isinstance(self.catalog, Catalog) or not isinstance(self.window, Window):
            raise ValidationError('Schema 6 exige Catalog e Window validados')
        super().__post_init__()
        if self.mode != 'STRATEGY' or self.orders:
            raise ValidationError('Schema 6 exige STRATEGY sem roteiro')
        if self.instrument_filters != self.instrument.instrument_filters:
            raise ValidationError('Filtros devem corresponder ao catálogo')

    def _validate_instrument(self):
        self.catalog.resolve(self.source, self.symbol, self.interval)

    @property
    def instrument(self):
        return self.catalog.resolve(self.source, self.symbol, self.interval)

    @property
    def base_asset(self):
        return self.instrument.base_asset

    @property
    def schema_version(self):
        return 6
