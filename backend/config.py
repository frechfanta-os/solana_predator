"""Configuration settings for SOLANA PREDATOR."""

import os
import secrets
from typing import List
from pydantic import BaseModel, Field


def _resolve_admin_key() -> str:
    key = os.getenv("ADMIN_API_KEY")
    if key and len(key.strip()) > 0:
        return key.strip()
    env = os.getenv("ENVIRONMENT", "development").lower()
    if env == "production":
        raise ValueError("CRITICAL SECURITY ERROR: ADMIN_API_KEY environment variable MUST be explicitly set in production mode!")
    # Development/Test fallback
    return os.getenv("PREDATOR_DEV_ADMIN_KEY", "predator-admin-auth-token-2026")


class Settings(BaseModel):
    PROJECT_NAME: str = "SOLANA PREDATOR"
    APP_VERSION: str = "1.0.0"
    SECURITY_NOTICE: str = "LIVE MARKET DATA — PAPER TRADING ONLY"
    
    # Environment & Networking
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    ALLOWED_ORIGINS: List[str] = [
        o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()
    ]
    
    # Security Boundary Enforcement
    ALLOW_TRANSACTION_SIGNING: bool = False  # HARDCODED FALSE - INVIOLABLE
    ALLOW_TRANSACTION_SUBMISSION: bool = False  # HARDCODED FALSE - INVIOLABLE
    ALLOW_REAL_FUNDS: bool = False  # HARDCODED FALSE - INVIOLABLE
    
    # Solana Read-Only RPC
    SOLANA_RPC_HTTP: str = os.getenv("SOLANA_RPC_HTTP", "https://api.mainnet-beta.solana.com")
    SOLANA_RPC_WS: str = os.getenv("SOLANA_RPC_WS", "wss://api.mainnet-beta.solana.com")
    SOLANA_COMMITMENT: str = os.getenv("SOLANA_COMMITMENT", "confirmed")
    RPC_TIMEOUT_SECONDS: float = float(os.getenv("RPC_TIMEOUT_SECONDS", "10.0"))
    RPC_MAX_RETRIES: int = int(os.getenv("RPC_MAX_RETRIES", "3"))
    RPC_RECONNECT_MAX_BACKOFF: float = float(os.getenv("RPC_RECONNECT_MAX_BACKOFF", "30.0"))
    
    # DEX Screener API
    DEXSCREENER_BASE_URL: str = os.getenv("DEXSCREENER_BASE_URL", "https://api.dexscreener.com")
    DEXSCREENER_CACHE_TTL_SEC: float = float(os.getenv("DEXSCREENER_CACHE_TTL_SEC", "15.0"))
    
    # Database
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "/root/solana_predator/solana_predator.db")
    
    # Admin API Key for administrative routes (dynamically resolved)
    ADMIN_API_KEY: str = Field(default_factory=_resolve_admin_key)
    
    # Paper Trading Simulator Parameters
    PAPER_INITIAL_CAPITAL: float = float(os.getenv("PAPER_INITIAL_CAPITAL", "10000.0"))
    PAPER_TAKER_FEE_BPS: float = float(os.getenv("PAPER_TAKER_FEE_BPS", "25.0"))  # 0.25%
    PAPER_BASE_SLIPPAGE_BPS: float = float(os.getenv("PAPER_BASE_SLIPPAGE_BPS", "30.0"))  # 0.30%
    PAPER_MAX_POSITION_PCT: float = float(os.getenv("PAPER_MAX_POSITION_PCT", "0.10"))  # Max 10% capital
    PAPER_MAX_OPEN_POSITIONS: int = int(os.getenv("PAPER_MAX_OPEN_POSITIONS", "5"))
    PAPER_MAX_DRAWDOWN_VETO_PCT: float = float(os.getenv("PAPER_MAX_DRAWDOWN_VETO_PCT", "0.15"))  # 15% Max DD
    
    # Market Data Freshness & Queues
    DATA_STALENESS_THRESHOLD_SEC: float = float(os.getenv("DATA_STALENESS_THRESHOLD_SEC", "30.0"))
    EVENT_QUEUE_MAXSIZE: int = int(os.getenv("EVENT_QUEUE_MAXSIZE", "2000"))
    DEDUPLICATION_CACHE_SIZE: int = int(os.getenv("DEDUPLICATION_CACHE_SIZE", "50000"))
    DEDUPLICATION_TTL_SEC: float = float(os.getenv("DEDUPLICATION_TTL_SEC", "600.0"))
    
    # LLM Configuration (OpenAI Chat Completions Compatible - GLM-5.3-Flash)
    LLM_ENABLED: bool = os.getenv("LLM_ENABLED", "false").lower() in ("true", "1", "yes")
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "space_z")
    LLM_API_BASE_URL: str = os.getenv(
        "LLM_API_BASE_URL",
        "https://preview-chat-5b88a64e-2cfd-4430-8a11-8a8190f3f6b2.space-z.ai/api/provider/v1"
    ).rstrip("/")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "glm-5.3-flash")
    LLM_TIMEOUT_SECONDS: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "15.0"))
    LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "3"))
    LLM_MAX_CONCURRENCY: int = int(os.getenv("LLM_MAX_CONCURRENCY", "5"))
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.2"))
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "1024"))
    LLM_STREAM: bool = os.getenv("LLM_STREAM", "false").lower() in ("true", "1", "yes")
    LLM_AUTH_HEADER_STYLE: str = os.getenv("LLM_AUTH_HEADER_STYLE", "bearer")  # bearer, x-api-key, or both
    
    # Whale Tracking Configuration (Tracked public wallets)
    TRACKED_WHALE_WALLETS: List[str] = [
        "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1",  # Raydium Authority
        "wha1e8sF3G5wK8eA9Z8oA2V4dE6mB1nC7xY9uL0kP3r",
        "wha2eN4mX9pQ2vR6tY8uW1zC3bK5dE7gH0jL4mP8sT2",
        "wha3eX7bL1kP4mR9sT2uV5wY8zC0dE3gH6jN9pQ2vW5",
    ]


settings = Settings()
