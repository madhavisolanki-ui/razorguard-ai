"""Application configuration settings for RazorGuard AI."""

import os
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = DATA_DIR / "models"
SYNTHETIC_DIR = DATA_DIR / "synthetic"
CONFIGS_DIR = BASE_DIR / "configs"

DATA_DIR.mkdir(exist_ok=True, parents=True)
MODELS_DIR.mkdir(exist_ok=True, parents=True)
SYNTHETIC_DIR.mkdir(exist_ok=True, parents=True)


class VelocityRuleConfig(BaseModel):
    max_user_requests_per_minute: int = 5
    max_user_requests_per_5_minutes: int = 15
    max_ip_requests_per_minute: int = 20
    max_ip_requests_per_5_minutes: int = 60
    max_device_requests_per_minute: int = 10
    max_device_requests_per_5_minutes: int = 30
    min_checkout_duration_sec: float = 1.5


class FailureRuleConfig(BaseModel):
    high_ip_failure_ratio_threshold: float = 0.60
    high_user_failure_ratio_threshold: float = 0.50
    min_transactions_for_failure_ratio: int = 3


class ConcentrationRuleConfig(BaseModel):
    max_unique_accounts_per_ip_1h: int = 4
    max_unique_devices_per_ip_1h: int = 5
    max_unique_ips_per_account_24h: int = 4
    max_unique_accounts_per_device_24h: int = 3


class PatternRuleConfig(BaseModel):
    max_repeated_amount_ratio_5m: float = 0.70
    min_repeated_count_threshold: int = 4
    micro_transaction_amount_max: float = 50.0
    max_amount_deviation_multiplier: float = 5.0


class MerchantSpikeConfig(BaseModel):
    spike_volume_multiplier: float = 3.0
    flash_sale_min_entropy: float = 0.65
    flash_sale_min_success_rate: float = 0.75


class GraphRuleConfig(BaseModel):
    max_accounts_per_device: int = 3
    max_accounts_per_ip: int = 5
    max_devices_per_account: int = 4
    max_ips_per_account: int = 5
    max_shared_card_accounts: int = 2
    min_ring_cycle_length: int = 3
    max_ring_cycle_length: int = 6
    suspicious_cluster_density_threshold: float = 0.40
    suspicious_cluster_min_size: int = 4
    graph_window_max_nodes: int = 50000
    campus_or_corporate_min_entropy: float = 0.70


class RulesConfig(BaseModel):
    velocity: VelocityRuleConfig = Field(default_factory=VelocityRuleConfig)
    failure_rates: FailureRuleConfig = Field(default_factory=FailureRuleConfig)
    concentration: ConcentrationRuleConfig = Field(default_factory=ConcentrationRuleConfig)
    patterns: PatternRuleConfig = Field(default_factory=PatternRuleConfig)
    merchant_spike: MerchantSpikeConfig = Field(default_factory=MerchantSpikeConfig)
    graph: GraphRuleConfig = Field(default_factory=GraphRuleConfig)


class Settings(BaseSettings):
    """Application Settings with environment variable and config override support."""

    # App Info
    APP_NAME: str = "RazorGuard AI"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 1

    # Database
    DATABASE_URL: str = Field(
        default=f"sqlite:///{DATA_DIR / 'razorguard.db'}",
        description="SQLAlchemy Database URL (PostgreSQL or SQLite)",
    )
    DB_ECHO_SQL: bool = False
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # Risk Engine Rules & Thresholds
    RULES: RulesConfig = Field(default_factory=RulesConfig)

    THRESHOLD_ALLOW_MAX: float = 30.0
    THRESHOLD_MONITOR_MAX: float = 65.0
    THRESHOLD_STEP_UP_MAX: float = 85.0
    # Score > 85.0 -> RATE_LIMIT

    # AI Agent Configuration
    LLM_PROVIDER: str = "gemini"  # "gemini", "openai", "fallback"
    OPENAI_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    AGENT_MODEL_NAME: str = "gemini-2.5-flash"
    AGENT_TEMPERATURE: float = 0.1
    AGENT_MAX_ITERATIONS: int = 5
    AGENT_TIMEOUT_SECONDS: float = 8.0
    AGENT_FALLBACK_DETERMINISTIC: bool = True

    # Paths
    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = DATA_DIR
    MODELS_DIR: Path = MODELS_DIR
    SYNTHETIC_DIR: Path = SYNTHETIC_DIR
    CONFIGS_DIR: Path = CONFIGS_DIR

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )


settings = Settings()
