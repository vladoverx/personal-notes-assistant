from __future__ import annotations

from functools import lru_cache

from supabase import Client, create_client
from supabase.lib.client_options import ClientOptions

from app.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def get_supabase_admin_client() -> Client:
    """Return a cached Supabase admin client using the service role key.

    This client is intended for background tasks with elevated privileges.
    """
    logger.debug("Initializing Supabase admin client")
    if not settings.supabase_service_role_key:
        raise RuntimeError("supabase_service_role_key is required for admin client")
    key = settings.supabase_service_role_key
    return create_client(
        settings.supabase_url,
        key,
        options=ClientOptions(auto_refresh_token=False, persist_session=False),
    )


def create_request_supabase_client(bearer_token: str | None = None) -> Client:
    """Create a request-scoped Supabase client using the anon key.

    If a JWT is provided, set it as the PostgREST bearer so that RLS policies
    are enforced for all table/rpc operations in this request.
    """
    logger.debug("Creating request-scoped Supabase client")
    anon_key = settings.supabase_anon_key
    if not anon_key:
        raise RuntimeError("supabase_anon_key is required for request client")

    client = create_client(
        settings.supabase_url,
        anon_key,
        options=ClientOptions(auto_refresh_token=False, persist_session=False),
    )
    if bearer_token:
        client.postgrest.auth(bearer_token)
    return client

