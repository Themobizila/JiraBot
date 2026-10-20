"""
Modulo de configuracao e definicao de perfis de turno do JiraBot.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


def get_default_config_dir() -> Path:
    """Retorna o diretorio padrao de configuracao do JiraBot no perfil do usuario."""
    home = Path(os.environ.get("USERPROFILE") or Path.home())
    config_dir = home / ".jirabot"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


@dataclass
class TimeWindow:
    """Define uma janela de horario (hora:minuto inicio e hora:minuto fim)."""
    start_str: str
    end_str: str

    @property
    def start_time(self) -> time:
        h, m = map(int, self.start_str.split(":"))
        return time(h, m)

    @property
    def end_time(self) -> time:
        h, m = map(int, self.end_str.split(":"))
        return time(h, m)

    def contains(self, target_time: time) -> bool:
        """Verifica se o horario fornecido esta contido dentro da janela."""
        t_start = self.start_time
        t_end = self.end_time

        if t_start <= t_end:
            return t_start <= target_time <= t_end
        else:
            return target_time >= t_start or target_time <= t_end

    def to_dict(self) -> Dict[str, str]:
        return {"start": self.start_str, "end": self.end_str}

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> TimeWindow:
        return cls(start_str=data.get("start", "00:00"), end_str=data.get("end", "23:59"))


def build_window(target_hm: str, tolerance_minutes_before: int = 15, tolerance_minutes_after: int = 15) -> TimeWindow:
    """Cria uma TimeWindow em torno de um horario alvo aplicando as margens de folga/tolerancia."""
    try:
        h, m = map(int, target_hm.split(":"))
        dt = datetime(2000, 1, 1, h, m)
        dt_start = dt - timedelta(minutes=tolerance_minutes_before)
        dt_end = dt + timedelta(minutes=tolerance_minutes_after)
        return TimeWindow(dt_start.strftime("%H:%M"), dt_end.strftime("%H:%M"))
    except Exception:
        return TimeWindow(target_hm, target_hm)


CALCULATOR_HM_KEYS = ("entry_hm", "lunch_start_hm", "lunch_end_hm", "exit_hm")
CALCULATOR_MIN_KEYS = (
    "entry_before", "entry_after",
    "lunch_start_before", "lunch_start_after",
    "lunch_end_before", "lunch_end_after",
    "exit_before", "exit_after",
)


def sanitize_calculator(raw: Any) -> Dict[str, Any]:
    """Filtra os parametros da Calculadora de Janelas: apenas chaves conhecidas, HH:MM valido e folgas 0-240 min."""
    if not isinstance(raw, dict):
        return {}
    clean: Dict[str, Any] = {}
    for key in CALCULATOR_HM_KEYS:
        val = str(raw.get(key) or "").strip()
        try:
            datetime.strptime(val, "%H:%M")
            clean[key] = val
        except ValueError:
            continue
    for key in CALCULATOR_MIN_KEYS:
        try:
            num = int(raw.get(key))
        except (TypeError, ValueError):
            continue
        clean[key] = max(0, min(240, num))
    return clean


@dataclass
class ShiftProfile:
    """Perfil de turno de trabalho com janelas para cada momento do dia."""
    name: str
    target_hours: float
    entry_window: TimeWindow
    lunch_start_window: TimeWindow
    lunch_end_window: TimeWindow
    exit_window: TimeWindow
    description: str = ""
    calculator: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "name": self.name,
            "target_hours": self.target_hours,
            "entry_window": self.entry_window.to_dict(),
            "lunch_start_window": self.lunch_start_window.to_dict(),
            "lunch_end_window": self.lunch_end_window.to_dict(),
            "exit_window": self.exit_window.to_dict(),
            "description": self.description,
        }
        if self.calculator:
            data["calculator"] = dict(self.calculator)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ShiftProfile:
        return cls(
            name=data.get("name", "custom"),
            target_hours=float(data.get("target_hours", 8.0)),
            entry_window=TimeWindow.from_dict(data.get("entry_window", {})),
            lunch_start_window=TimeWindow.from_dict(data.get("lunch_start_window", {})),
            lunch_end_window=TimeWindow.from_dict(data.get("lunch_end_window", {})),
            exit_window=TimeWindow.from_dict(data.get("exit_window", {})),
            description=data.get("description", ""),
            calculator=sanitize_calculator(data.get("calculator")),
        )


def make_custom_profile(
    name: str,
    target_hours: float,
    entry_hm: str,
    lunch_start_hm: str,
    lunch_end_hm: str,
    exit_hm: str,
    tolerance_minutes: Optional[int] = None,
    entry_tol_before: int = 20,
    entry_tol_after: int = 20,
    lunch_start_tol_before: int = 20,
    lunch_start_tol_after: int = 20,
    lunch_end_tol_before: int = 10,
    lunch_end_tol_after: int = 15,
    exit_tol_before: int = 15,
    exit_tol_after: int = 30,
    description: str = "",
) -> ShiftProfile:
    """Fabrica um ShiftProfile personalizado com definicao individualizada de folgas antes e depois."""
    if tolerance_minutes is not None:
        entry_tol_before = entry_tol_after = tolerance_minutes
        lunch_start_tol_before = lunch_start_tol_after = tolerance_minutes
        lunch_end_tol_before = lunch_end_tol_after = tolerance_minutes
        exit_tol_before = exit_tol_after = tolerance_minutes

    return ShiftProfile(
        name=name,
        target_hours=target_hours,
        entry_window=build_window(entry_hm, entry_tol_before, entry_tol_after),
        lunch_start_window=build_window(lunch_start_hm, lunch_start_tol_before, lunch_start_tol_after),
        lunch_end_window=build_window(lunch_end_hm, lunch_end_tol_before, lunch_end_tol_after),
        exit_window=build_window(exit_hm, exit_tol_before, exit_tol_after),
        description=description or f"Turno Personalizado {target_hours}h (Entrada {entry_hm}, Retorno {lunch_end_hm}, Saida {exit_hm})",
    )


def get_default_profiles() -> Dict[str, ShiftProfile]:
    """Retorna os perfis padrao pre-configurados."""
    return {
        "8h": ShiftProfile(
            name="8h",
            target_hours=8.0,
            entry_window=TimeWindow("07:15", "08:15"),       # Alvo: 07:42
            lunch_start_window=TimeWindow("11:30", "12:30"), # Pausa almoco
            lunch_end_window=TimeWindow("12:55", "13:30"),   # Retorno almoco para 8h (12:55 a 13:30)
            exit_window=TimeWindow("17:25", "18:30"),        # Saida 8h
            description="Turno de 8 horas (Entrada ~07:42, Almoco 11:30/12:55-13:30, Saida ~17:30-18:10)"
        ),
        "6h_0745": ShiftProfile(
            name="6h_0745",
            target_hours=6.0,
            entry_window=TimeWindow("07:15", "08:15"),       # Alvo: 07:45
            lunch_start_window=TimeWindow("11:30", "12:30"), # Pausa almoco
            lunch_end_window=TimeWindow("13:20", "13:40"),   # Retorno almoco para 6h (13:20 a 13:40)
            exit_window=TimeWindow("15:05", "16:00"),        # Saida 6h
            description="Turno de 6 horas cedo (Entrada ~07:45, Retorno Almoco 13:20-13:40, Saida ~15:15-15:30)"
        ),
        "6h_0800": ShiftProfile(
            name="6h_0800",
            target_hours=6.0,
            entry_window=TimeWindow("07:35", "08:30"),       # Alvo: 08:00
            lunch_start_window=TimeWindow("11:30", "12:30"), # Pausa almoco
            lunch_end_window=TimeWindow("13:20", "13:40"),   # Retorno almoco para 6h (13:20 a 13:40)
            exit_window=TimeWindow("15:15", "16:00"),        # Saida 15:30
            description="Turno de 6 horas padrao (Entrada ~08:00, Retorno Almoco 13:20-13:40, Saida ~15:30)"
        ),
        "custom": ShiftProfile(
            name="custom",
            target_hours=6.0,
            entry_window=TimeWindow("07:15", "08:30"),
            lunch_start_window=TimeWindow("11:30", "12:30"),
            lunch_end_window=TimeWindow("13:20", "13:40"),
            exit_window=TimeWindow("15:05", "16:30"),
            description="Turno Personalizado pelo Usuario"
        ),
    }


@dataclass
class JiraConfig:
    """Credenciais e parametros de conexao com a API REST do Jira."""
    base_url: str = "https://consisanet.atlassian.net"
    email: str = ""
    api_token: str = ""
    auth_type: str = "auto"
    default_issue: str = "ATIVDIV-32"
    default_comment: str = "Lancamento automatico de expediente via JiraBot"

    def get_clean_url(self) -> str:
        return self.base_url.strip().rstrip("/")

    def get_clean_base_url(self) -> str:
        return self.get_clean_url()

    def get_clean_email(self) -> str:
        return self.email.strip()

    def get_clean_token(self) -> str:
        return self.api_token.strip()

    def to_dict(self) -> Dict[str, str]:
        return {
            "base_url": self.get_clean_url(),
            "email": self.get_clean_email(),
            "api_token": self.get_clean_token(),
            "auth_type": self.auth_type,
            "default_issue": self.default_issue.strip().upper(),
            "default_comment": self.default_comment,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> JiraConfig:
        return cls(
            base_url=data.get("base_url", "https://consisanet.atlassian.net").strip().rstrip("/"),
            email=data.get("email", "").strip(),
            api_token=data.get("api_token", "").strip(),
            auth_type=data.get("auth_type", "auto"),
            default_issue=data.get("default_issue", "ATIVDIV-32").strip().upper(),
            default_comment=data.get("default_comment", "Lancamento automatico de expediente via JiraBot"),
        )


@dataclass
class BotConfig:
    """Configuracao geral da aplicacao (armazenada individualmente em ~/.jirabot/config.json)."""
    active_profile: str = "6h_0745"
    profiles: Dict[str, ShiftProfile] = field(default_factory=get_default_profiles)
    jira: JiraConfig = field(default_factory=JiraConfig)
    intermediate_lock_mode: str = "ignore"
    notifications_enabled: bool = True
    auto_log_on_exit: bool = True
    min_log_minutes: int = 15
    theme: str = "dark"
    update_source: str = ""
    auto_update_on_start: bool = False

    def get_current_profile(self) -> ShiftProfile:
        return self.profiles.get(self.active_profile, self.profiles["6h_0745"])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "active_profile": self.active_profile,
            "profiles": {k: v.to_dict() for k, v in self.profiles.items()},
            "jira": self.jira.to_dict(),
            "intermediate_lock_mode": self.intermediate_lock_mode,
            "notifications_enabled": self.notifications_enabled,
            "auto_log_on_exit": self.auto_log_on_exit,
            "min_log_minutes": self.min_log_minutes,
            "theme": self.theme,
            "update_source": self.update_source,
            "auto_update_on_start": self.auto_update_on_start,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BotConfig:
        raw_profiles = data.get("profiles", {})
        profiles: Dict[str, ShiftProfile] = {}
        for name, p_data in raw_profiles.items():
            try:
                profiles[name] = ShiftProfile.from_dict(p_data)
            except Exception:
                pass

        default_profs = get_default_profiles()
        for k, v in default_profs.items():
            if k not in profiles:
                profiles[k] = v

        return cls(
            active_profile=data.get("active_profile", "6h_0745"),
            profiles=profiles,
            jira=JiraConfig.from_dict(data.get("jira", {})),
            intermediate_lock_mode=data.get("intermediate_lock_mode", "ignore"),
            notifications_enabled=data.get("notifications_enabled", True),
            auto_log_on_exit=data.get("auto_log_on_exit", True),
            min_log_minutes=int(data.get("min_log_minutes", 15)),
            theme=data.get("theme", "dark"),
            update_source=data.get("update_source", ""),
            auto_update_on_start=bool(data.get("auto_update_on_start", False)),
        )

    def save(self, filepath: Optional[Path] = None) -> None:
        path = filepath or (get_default_config_dir() / "config.json")
        temp_path = path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        if temp_path.exists():
            temp_path.replace(path)

    @classmethod
    def load(cls, filepath: Optional[Path] = None) -> BotConfig:
        path = filepath or (get_default_config_dir() / "config.json")
        if not path.exists():
            cfg = cls()
            cfg.save(path)
            return cfg

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return cls.from_dict(data)
        except Exception:
            cfg = cls()
            cfg.save(path)
            return cfg
