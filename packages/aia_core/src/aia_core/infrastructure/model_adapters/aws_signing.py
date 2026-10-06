"""SigV4 signing with the instance (or task) role -- and nothing else.

ADR 0010: "there are no static credentials: the adapter signs requests with the
instance role via SigV4". botocore is used **for signing only** (``SigV4Auth`` and
its credential chain); no botocore client is built, so nothing here can retry,
choose an endpoint or call a service on its own. It is imported lazily, like
boto3 in :class:`~aia_core.infrastructure.storage.S3ArtifactStore`, so the package
installs without it; ``make layer_check`` names this file as the one exemption.

**Only a role credential signs.** botocore's default chain would happily use an
``AWS_ACCESS_KEY_ID`` left in the environment or a shared credentials file. For a
route whose approval assumes the host's role, such a key is a different principal
with different permissions and no audit trail tying it to the host, so it is
refused: ``credential_method`` must be one of :data:`ROLE_CREDENTIAL_METHODS`.
"""

from __future__ import annotations

import threading
from collections.abc import Mapping
from typing import Any, Final

from .bedrock import BEDROCK_SIGNING_SERVICE, SigningUnavailable

__all__ = ["ROLE_CREDENTIAL_METHODS", "InstanceRoleSigner"]

#: botocore's ``Credentials.method`` for the EC2 instance profile and the ECS task role.
ROLE_CREDENTIAL_METHODS: Final = frozenset({"iam-role", "container-role"})


class InstanceRoleSigner:
    """:class:`~aia_core.infrastructure.model_adapters.bedrock.BedrockSigner` over botocore.

    Credentials are resolved on first use and refreshed by botocore before they
    expire; nothing is fetched at construction, so building a worker's registry
    touches no network.

    ``service`` is the SigV4 signing name: Bedrock by default; Athena's
    (``athena``) for the Common Crawl URL index (plan chunk 18). One signer signs
    for one service in one region.
    """

    def __init__(self, *, region: str, service: str = BEDROCK_SIGNING_SERVICE) -> None:
        if not region.strip():
            raise ValueError("a signer needs a region")
        if not service.strip():
            raise ValueError("a signer needs a service name")
        self._region = region
        self._service = service
        self._lock = threading.Lock()
        self._credentials: Any = None

    def _resolve(self) -> Any:
        with self._lock:
            if self._credentials is None:
                try:
                    from botocore.session import get_session
                except ImportError as exc:  # pragma: no cover - the image installs it
                    raise SigningUnavailable("botocore is not installed") from exc
                credentials = get_session().get_credentials()
                if credentials is None:
                    raise SigningUnavailable("no AWS credentials are available to this process")
                method = str(getattr(credentials, "method", "") or "")
                if method not in ROLE_CREDENTIAL_METHODS:
                    raise SigningUnavailable(
                        f"{self._service} requests are signed only with an instance or "
                        f"container role; "
                        f"the available credential comes from {method or 'an unknown source'!r}"
                    )
                self._credentials = credentials
            return self._credentials

    def sign(
        self, *, method: str, url: str, headers: Mapping[str, str], body: bytes
    ) -> dict[str, str]:
        from botocore.auth import SigV4Auth
        from botocore.awsrequest import AWSRequest

        frozen = self._resolve().get_frozen_credentials()
        aws_request = AWSRequest(method=method, url=url, data=body, headers=dict(headers))
        SigV4Auth(frozen, self._service, self._region).add_auth(aws_request)
        return {k.lower(): str(v) for k, v in aws_request.headers.items()}
