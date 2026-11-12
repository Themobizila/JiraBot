"""Datas recorrentes do calendário brasileiro para os lotes de trabalho."""

from contextlib import closing
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
import sqlite3
from typing import NamedTuple


FIRST_YEAR = 2000
LAST_YEAR = 2100


class CalendarEvent(NamedTuple):
    day: date
    name: str
    blocks_batch: bool


def _easter_sunday(year: int) -> date:
    """Calcula a Páscoa pelo algoritmo gregoriano de Meeus/Jones/Butcher."""
    lunar_cycle = year % 19
    century, year_in_century = divmod(year, 100)
    leap_centuries, century_remainder = divmod(century, 4)
    correction = (century - (century + 8) // 25 + 1) // 3
    moon = (19 * lunar_cycle + century - leap_centuries - correction + 15) % 30
    leap_years, year_remainder = divmod(year_in_century, 4)
    weekday = (32 + 2 * century_remainder + 2 * leap_years - moon - year_remainder) % 7
    adjustment = (lunar_cycle + 11 * moon + 22 * weekday) // 451
    month, day = divmod(moon + weekday - 7 * adjustment + 114, 31)
    return date(year, month, day + 1)


@lru_cache(maxsize=101)
def calendar_events(year: int) -> tuple[CalendarEvent, ...]:
    fixed = [
        (1, 1, "Confraternização Universal"),
        (4, 21, "Tiradentes"),
        (5, 1, "Dia do Trabalho"),
        (9, 7, "Independência do Brasil"),
        (10, 12, "Nossa Senhora Aparecida"),
        (11, 2, "Finados"),
        (11, 15, "Proclamação da República"),
        (12, 25, "Natal"),
    ]
    if year >= 2024:
        fixed.append((11, 20, "Dia Nacional de Zumbi e da Consciência Negra"))
    events = [CalendarEvent(date(year, month, day), name, True) for month, day, name in fixed]
    easter = _easter_sunday(year)
    events.extend(
        CalendarEvent(easter + timedelta(days=offset), name, blocks_batch)
        for offset, name, blocks_batch in (
            (-48, "Carnaval (segunda-feira)", False),
            (-47, "Carnaval (terça-feira)", False),
            (-46, "Quarta-feira de Cinzas", False),
            (-2, "Paixão de Cristo", True),
            (0, "Páscoa", False),
            (60, "Corpus Christi", False),
        )
    )
    return tuple(sorted(events))


def load_calendar_absences(base_dir: Path) -> dict[str, str]:
    database = base_dir / "calendar.sqlite3"
    if not database.is_file():
        return {}
    with closing(sqlite3.connect(f"{database.resolve().as_uri()}?mode=ro", uri=True)) as connection:
        return dict(connection.execute("SELECT day, title FROM absences"))


def save_calendar_absence(base_dir: Path, day: date, title: str) -> None:
    """Registra uma ausência de dia inteiro. Um título vazio remove o evento."""
    with closing(sqlite3.connect(base_dir / "calendar.sqlite3")) as connection, connection:
        connection.execute("CREATE TABLE IF NOT EXISTS absences (day TEXT PRIMARY KEY, title TEXT NOT NULL)")
        if title:
            connection.execute(
                "INSERT INTO absences (day, title) VALUES (?, ?) "
                "ON CONFLICT(day) DO UPDATE SET title = excluded.title",
                (day.isoformat(), title),
            )
        else:
            connection.execute("DELETE FROM absences WHERE day = ?", (day.isoformat(),))
