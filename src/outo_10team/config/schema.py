from .defaults import (
    DEFAULT_BOT_PASSWORD,
    DEFAULT_CHATSERVER_URL,
    DEFAULT_CONTAINER_IMAGE,
    DEFAULT_PROVIDER_API_KEY,
    DEFAULT_PROVIDER_BASE_URL,
    DEFAULT_PROVIDER_MODEL,
)
from pydantic import BaseModel


class ProviderConfig(BaseModel):
    base_url: str = DEFAULT_PROVIDER_BASE_URL
    api_key: str = DEFAULT_PROVIDER_API_KEY
    default_model: str = DEFAULT_PROVIDER_MODEL


class ChatserverConfig(BaseModel):
    url: str = DEFAULT_CHATSERVER_URL
    workspace_id: str = ""
    bot_password: str = DEFAULT_BOT_PASSWORD


class ContainerConfig(BaseModel):
    image: str = DEFAULT_CONTAINER_IMAGE
    mem_limit: str = "512m"
    cpu_shares: int = 512
    pids_limit: int = 100


class AppConfig(BaseModel):
    provider: ProviderConfig = ProviderConfig()
    chatserver: ChatserverConfig = ChatserverConfig()
    containers: ContainerConfig = ContainerConfig()
