"""A leak-free `PelicanFileSystem`.

pelicanfs reaches the Pelican cache over WebDAV (via `aiowebdav2`) for every
`exists`/`info`/`ls` call, and `aiowebdav2.Client` hands back a bare
`aiohttp.ClientResponse` that nobody ever reads or releases:

    # aiowebdav2/client.py
    async def check(self, remote_path=DEFAULT_ROOT) -> bool:
        response = await self.execute_request(action="check", path=urn.path())
        return 200 <= int(response.status) < 300   # body never read, connection never released

`execute_request` does the same on its 401/403/404/405/423/507 paths: it raises
without releasing. aiohttp returns a connection to the pool on its own once the
response body reaches EOF, so short replies get away with it -- but a PROPFIND
multistatus that has not fully arrived by the time the response is garbage
collected leaves `Connection._protocol` set, and `Connection.__del__` logs

    Unclosed connection
    client_connection: Connection<ConnectionKey(host='...-pelican-cache...', port=8443, ...)>

One per leaked call. Resolving thousands of `pelican://` data files -- what
`datasets.load_dataset(..., data_files=[...])` does, one `exists()` per file --
produces the flood of warnings seen in `notebooks/speed_test.ipynb`.

Reading each PROPFIND body as soon as it lands hands the connection back to the
pool and caches the body on the response, so `aiowebdav2`'s own
`await response.read()` in `info`/`list_files` still sees it. Only PROPFIND is
touched, leaving GET downloads streaming as they are.

Fixed upstream in neither pelicanfs 1.4.1 nor aiowebdav2 0.6.2; drop this module
once they release the connections themselves.
"""

import logging
from contextlib import asynccontextmanager
from typing import Any

import aiohttp
from aiowebdav2.client import Client, ClientOptions
from pelicanfs.core import PelicanFileSystem

logger = logging.getLogger(__name__)

# The only WebDAV verb pelicanfs uses for metadata: `check`, `info` and `list` all
# map to PROPFIND in `aiowebdav2.Client.default_requests`. Keying off the HTTP verb
# rather than the action name keeps this correct as aiowebdav2 renames actions.
_METADATA_METHODS = frozenset({"PROPFIND"})


class _ReleasingSession(aiohttp.ClientSession):
    """A session that buffers metadata replies instead of leaking their connections."""

    async def _request(self, method: str, str_or_url: Any, **kwargs: Any) -> aiohttp.ClientResponse:
        response = await super()._request(method, str_or_url, **kwargs)
        if method.upper() in _METADATA_METHODS:
            # Reading to EOF is what makes aiohttp release the connection; the
            # body is cached on the response for whoever reads it next.
            await response.read()
        return response


@asynccontextmanager
async def releasing_webdav_client(options: dict[str, Any]):
    """Drop-in replacement for `pelicanfs.core.get_webdav_client`."""
    session = _ReleasingSession(headers={"Authorization": f"Bearer {options['token']}"})
    client = Client(
        url=options["hostname"],
        username="",
        password="",
        options=ClientOptions(session=session),
    )
    # aiowebdav2 only closes a session it created itself; pelicanfs sets this
    # flag too, so the session we passed in gets closed on `client.close()`.
    client._close_session = True

    try:
        yield client
    finally:
        await client.close()
        logger.debug("WebDAV client closed")


def get_pelican_filesystem(federation_discovery_url: str, **kwargs: Any) -> PelicanFileSystem:
    """Build a `PelicanFileSystem` that does not leak cache connections."""
    kwargs.setdefault("get_webdav_client", releasing_webdav_client)
    return PelicanFileSystem(federation_discovery_url, **kwargs)
