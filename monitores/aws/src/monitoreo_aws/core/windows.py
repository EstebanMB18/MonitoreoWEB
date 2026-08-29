from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as datetime_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


@dataclass(frozen=True)
class Ventana:
    corte: int | str
    nombre: str
    inicio: datetime
    fin: datetime

    @property
    def texto(self) -> str:
        return f"{self.inicio:%Y-%m-%d %H:%M} a {self.fin:%Y-%m-%d %H:%M}"


def resolver_corte_automatico(ahora: datetime) -> int:
    """Selecciona uno de los tres cortes operativos diarios.

    - Antes de las 13:00: corte 1 (18:00 anterior a 09:00).
    - Desde las 13:00 y antes de las 17:00: corte 2 (09:00 a 13:00).
    - Desde las 17:00: corte 3 (13:00 a 17:00).
    """
    if ahora.hour < 13:
        return 1
    if ahora.hour < 17:
        return 2
    return 3



def construir_ventana_acumulada_hoy(ahora: datetime) -> Ventana:
    inicio = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    return Ventana("DIA", "Acumulado del día · 00:00 a hora actual", inicio, ahora)


def construir_ventana_rango(fecha_base: datetime, hora_inicio: str, hora_fin: str) -> Ventana:
    try:
        hi_h, hi_m = [int(x) for x in hora_inicio.split(":", 1)]
        hf_h, hf_m = [int(x) for x in hora_fin.split(":", 1)]
    except Exception as exc:
        raise ValueError("Las horas deben tener formato HH:MM") from exc

    inicio = fecha_base.replace(hour=hi_h, minute=hi_m, second=0, microsecond=0)
    fin = fecha_base.replace(hour=hf_h, minute=hf_m, second=59, microsecond=999999)
    if fin <= inicio:
        raise ValueError("La hora final debe ser mayor que la hora inicial.")
    etiqueta = f"Rango histórico · {hora_inicio} a {hora_fin}"
    return Ventana("RANGO", etiqueta, inicio, fin)

def construir_ventana(corte: int, fecha_base: datetime) -> Ventana:
    base = fecha_base.replace(hour=0, minute=0, second=0, microsecond=0)
    if corte == 1:
        inicio = (base - timedelta(days=1)).replace(hour=18)
        fin = base.replace(hour=9)
        nombre = "Corte 1 · 18:00 anterior a 09:00"
    elif corte == 2:
        inicio = base.replace(hour=9)
        fin = base.replace(hour=13)
        nombre = "Corte 2 · 09:00 a 13:00"
    elif corte == 3:
        inicio = base.replace(hour=13)
        fin = base.replace(hour=17)
        nombre = "Corte 3 · 13:00 a 17:00"
    else:
        raise ValueError("El corte debe ser 1, 2 o 3")
    return Ventana(corte, nombre, inicio, fin)


def obtener_ventana(corte: str, fecha: str | None, timezone: str, hora_inicio: str = "00:00", hora_fin: str = "23:59") -> Ventana:
    try:
        tz = ZoneInfo(timezone)
    except ZoneInfoNotFoundError:
        if timezone == "America/Bogota":
            tz = datetime_timezone(timedelta(hours=-5), name="America/Bogota")
        else:
            raise RuntimeError(
                f"No se encontró la zona horaria {timezone!r}. "
                "Ejecute: python -m pip install tzdata"
            )
    ahora = datetime.now(tz)
    if fecha:
        base = datetime.strptime(fecha, "%Y-%m-%d").replace(tzinfo=tz)
    else:
        base = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    if corte == "dia":
        return construir_ventana_acumulada_hoy(ahora)
    if corte == "rango":
        if not fecha:
            raise ValueError("El rango histórico requiere --fecha.")
        return construir_ventana_rango(base, hora_inicio, hora_fin)
    numero = resolver_corte_automatico(ahora) if corte == "auto" else int(corte)
    return construir_ventana(numero, base)
