"""Supabase client wrapper for auth, storage and basic DB operations.

This wrapper supports:
- anon-key clients (intended for user-scoped operations with RLS + JWT)
- service-role clients (privileged server-side operations)
"""

from typing import Optional, Any, Dict
import os
from pathlib import Path

from supabase import create_client


class SupabaseClient:
    def __init__(
        self,
        url: Optional[str] = None,
        key: Optional[str] = None,
        *,
        use_service_role: bool = False,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
    ):
        self.url = url or os.environ.get('SUPABASE_URL')

        anon_key = os.environ.get('SUPABASE_ANON_KEY')
        service_key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')

        if key:
            self.key = key
        else:
            self.key = service_key if (use_service_role and service_key) else anon_key

        if not self.url or not self.key:
            raise RuntimeError('SUPABASE_URL and SUPABASE_ANON_KEY (or SUPABASE_SERVICE_ROLE_KEY) must be set')

        self._client = create_client(self.url, self.key)

        try:
            Path('logs').mkdir(exist_ok=True)
        except Exception:
            pass

        # Apply user auth context for PostgREST queries when provided.
        if access_token:
            self.set_access_token(access_token, refresh_token=refresh_token)

    @property
    def client(self):
        return self._client

    # Auth helpers
    def auth_sign_up(self, email: str, password: str) -> Dict[str, Any]:
        res = self._client.auth.sign_up({'email': email, 'password': password})
        return self._normalize_auth_response(res)

    def auth_sign_in(self, email: str, password: str) -> Dict[str, Any]:
        res = self._client.auth.sign_in_with_password({'email': email, 'password': password})
        return self._normalize_auth_response(res)

    def set_access_token(self, access_token: str, refresh_token: Optional[str] = None) -> None:
        """Attach a user JWT to this client for RLS-protected operations."""
        # supabase-py v2 supports postgrest.auth(token)
        try:
            if hasattr(self._client, 'postgrest') and hasattr(self._client.postgrest, 'auth'):
                self._client.postgrest.auth(access_token)
        except Exception:
            pass

        # Some versions support auth.set_session(access, refresh)
        try:
            if refresh_token and hasattr(self._client, 'auth') and hasattr(self._client.auth, 'set_session'):
                self._client.auth.set_session(access_token, refresh_token)
        except Exception:
            pass

    def get_user(self) -> Dict[str, Any]:
        res = self._client.auth.get_user()
        return self._normalize_auth_response(res)

    def _normalize_auth_response(self, res: Any) -> Dict[str, Any]:
        out: Dict[str, Any] = {'user': None, 'session': None, 'raw': res}
        try:
            if hasattr(res, 'get'):
                out['user'] = res.get('user') if res.get('user') is not None else res.get('data')
                out['session'] = res.get('session')
                return out

            if hasattr(res, 'user'):
                out['user'] = getattr(res, 'user')
            if hasattr(res, 'session'):
                out['session'] = getattr(res, 'session')

            if hasattr(res, 'data'):
                data = getattr(res, 'data')
                if isinstance(data, dict):
                    out['user'] = out['user'] or data.get('user')
                    out['session'] = out['session'] or data.get('session')
        except Exception:
            out['raw'] = res
        return out

    # Storage
    def storage_upload(self, bucket: str, path: str, file_bytes: bytes, content_type: Optional[str] = None) -> Dict[str, Any]:
        storage = self._client.storage
        file_ct = content_type or 'application/octet-stream'
        try:
            # supabase-py v2 commonly expects file_options kwarg
            return storage.from_(bucket).upload(path, file_bytes, file_options={'content-type': file_ct})
        except TypeError:
            # Some versions accept options as the 3rd positional arg
            return storage.from_(bucket).upload(path, file_bytes, {'content-type': file_ct})
        except Exception as e:
            try:
                with open('logs/supabase_client.log', 'a', encoding='utf-8') as lf:
                    lf.write('---\n')
                    lf.write('storage_upload failed:\n')
                    lf.write(repr(e) + '\n')
                    lf.write(f'bucket={bucket} path={path} content_type={file_ct}\n')
            except Exception:
                pass
            raise

    def storage_list_buckets(self) -> Any:
        storage = self._client.storage
        if hasattr(storage, 'list_buckets'):
            return storage.list_buckets()
        if hasattr(storage, 'get_buckets'):
            return storage.get_buckets()
        raise RuntimeError('Supabase storage client does not support listing buckets')

    def storage_create_bucket(self, bucket: str, public: bool = False) -> Any:
        """Create a storage bucket if it does not exist.

        Requires service role key in most configurations.
        """
        storage = self._client.storage
        if hasattr(storage, 'create_bucket'):
            # supabase-py commonly expects options dict
            try:
                return storage.create_bucket(bucket, options={'public': public})
            except TypeError:
                return storage.create_bucket(bucket, public=public)
        raise RuntimeError('Supabase storage client does not support bucket creation')

    def storage_get_public_url(self, bucket: str, path: str) -> str:
        res = self._client.storage.from_(bucket).get_public_url(path)
        if isinstance(res, dict):
            return res.get('publicURL') or res.get('publicUrl') or res.get('public_url') or ''
        # Best-effort for SDK object responses
        return getattr(res, 'publicURL', None) or getattr(res, 'publicUrl', None) or getattr(res, 'public_url', None) or ''

    def storage_create_signed_url(self, bucket: str, path: str, expires_in: int = 3600) -> Dict[str, Any]:
        return self._client.storage.from_(bucket).create_signed_url(path, expires_in)

    # Table helpers
    def table_insert(self, table: str, record: Dict[str, Any], returning: str = '*') -> Dict[str, Any]:
        return self._client.table(table).insert(record).execute()

    def table_update(self, table: str, record: Dict[str, Any], eq_field: str, eq_value: Any, returning: str = '*') -> Dict[str, Any]:
        return self._client.table(table).update(record).eq(eq_field, eq_value).execute()

    def table_select(self, table: str, filters: Optional[Dict[str, Any]] = None, limit: Optional[int] = None, returning: str = '*') -> Dict[str, Any]:
        q = self._client.table(table).select()
        if filters:
            for k, v in filters.items():
                q = q.eq(k, v)
        if limit:
            q = q.limit(limit)
        return q.execute()

    def table_delete(self, table: str, eq_field: str, eq_value: Any) -> Dict[str, Any]:
        return self._client.table(table).delete().eq(eq_field, eq_value).execute()
