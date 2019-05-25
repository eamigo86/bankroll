from abc import ABC, abstractmethod
from dataclasses import dataclass, InitVar
from datetime import date
from enum import Enum, unique
from decimal import Decimal, ROUND_HALF_EVEN
from functools import total_ordering
from typing import Any, ClassVar, Optional

from .cash import Currency

import re


@dataclass(frozen=True)
@total_ordering
class Instrument(ABC):
    multiplierQuantization: ClassVar[Decimal] = Decimal('0.1')

    symbol: str
    currency: Currency

    @classmethod
    def quantizeMultiplier(cls, multiplier: Decimal) -> Decimal:
        return multiplier.quantize(cls.multiplierQuantization,
                                   rounding=ROUND_HALF_EVEN)

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError('Expected non-empty symbol for instrument')
        if not self.currency:
            raise ValueError('Expected currency for instrument')

    @property
    def multiplier(self) -> Decimal:
        return Decimal(1)

    def __lt__(self, other: 'Instrument') -> bool:
        return self.symbol < other.symbol

    def __format__(self, spec: str) -> str:
        return format(self.symbol, spec)

    def __str__(self) -> str:
        return self.symbol


# Also used for ETFs.
@dataclass(frozen=True)
class Stock(Instrument):
    pass


@dataclass(frozen=True)
class Bond(Instrument):
    regexCUSIP: ClassVar[str] = r'^[0-9]{3}[0-9A-Z]{5}[0-9]$'

    validateSymbol: InitVar[bool] = True

    @classmethod
    def validBondSymbol(cls, symbol: str) -> bool:
        return re.match(cls.regexCUSIP, symbol) is not None

    # Default value needed to match super's type for __post_init__.
    def __post_init__(self, validateSymbol: bool = True) -> None:
        if validateSymbol and not self.validBondSymbol(self.symbol):
            raise ValueError(
                f'Expected symbol to be a bond CUSIP: {self.symbol}')

        super().__post_init__()


@unique
class OptionType(Enum):
    PUT = 'P'
    CALL = 'C'


class Option(Instrument):
    # Matches the multiplicative factor in OCC options symbology.
    strikeQuantization = Decimal('0.001')

    @classmethod
    def quantizeStrike(cls, strike: Decimal) -> Decimal:
        return strike.quantize(cls.strikeQuantization,
                               rounding=ROUND_HALF_EVEN)

    def __init__(self,
                 underlying: str,
                 currency: Currency,
                 optionType: OptionType,
                 expiration: date,
                 strike: Decimal,
                 multiplier: Decimal = Decimal(100),
                 symbol: Optional[str] = None):
        if not underlying:
            raise ValueError('Expected non-empty underlying symbol for Option')
        if not strike.is_finite() or strike <= 0:
            raise ValueError(f'Expected positive strike price: {strike}')
        if not multiplier.is_finite() or multiplier <= 0:
            raise ValueError(f'Expected positive multiplier: {multiplier}')

        self._underlying = underlying
        self._optionType = optionType
        self._expiration = expiration
        self._strike = self.quantizeStrike(strike)
        self._multiplier = self.quantizeMultiplier(multiplier)

        if symbol is None:
            # https://en.wikipedia.org/wiki/Option_symbol#The_OCC_Option_Symbol
            symbol = f"{underlying:6}{expiration.strftime('%y%m%d')}{optionType.value}{(strike * 1000):08.0f}"

        super().__init__(symbol, currency)

    @property
    def underlying(self) -> str:
        return self._underlying

    @property
    def optionType(self) -> OptionType:
        return self._optionType

    @property
    def expiration(self) -> date:
        return self._expiration

    @property
    def strike(self) -> Decimal:
        return self._strike

    @property
    def multiplier(self) -> Decimal:
        return self._multiplier

    def __repr__(self) -> str:
        return f'{type(self)!r}(underlying={self.underlying!r}, optionType={self.optionType!r}, expiration={self.expiration!r}, strike={self.strike!r}, currency={self.currency!r}, multiplier={self.multiplier!r})'


class FutureOption(Option):
    def __init__(self, symbol: str, underlying: str, currency: Currency,
                 optionType: OptionType, expiration: date, strike: Decimal,
                 multiplier: Decimal):
        super().__init__(underlying=underlying,
                         currency=currency,
                         optionType=optionType,
                         expiration=expiration,
                         strike=strike,
                         multiplier=multiplier,
                         symbol=symbol)


class Future(Instrument):
    def __init__(self, symbol: str, currency: Currency, multiplier: Decimal,
                 expiration: date):
        if not multiplier.is_finite() or multiplier <= 0:
            raise ValueError(f'Expected positive multiplier: {multiplier}')

        self._multiplier = self.quantizeMultiplier(multiplier)
        self._expiration = expiration

        super().__init__(symbol, currency)

    @property
    def multiplier(self) -> Decimal:
        return self._multiplier

    @property
    def expiration(self) -> date:
        return self._expiration

    def __repr__(self) -> str:
        return f'{type(self)!r}(symbol={self.symbol!r}, currency={self.currency!r}, multiplier={self.multiplier!r}, expiration={self.expiration!r})'


class Forex(Instrument):
    def __init__(self, baseCurrency: Currency, quoteCurrency: Currency):
        if baseCurrency == quoteCurrency:
            raise ValueError(
                f'Forex pair must be composed of different currencies, got {baseCurrency!r} and {quoteCurrency!r}'
            )

        self._baseCurrency = baseCurrency
        symbol = f'{baseCurrency.name}{quoteCurrency.name}'
        super().__init__(symbol, quoteCurrency)

    @property
    def quoteCurrency(self) -> Currency:
        return self.currency

    @property
    def baseCurrency(self) -> Currency:
        return self._baseCurrency

    def __repr__(self) -> str:
        return f'{type(self)!r}(baseCurrency={self.baseCurrency!r}, quoteCurrency={self.quoteCurrency!r})'