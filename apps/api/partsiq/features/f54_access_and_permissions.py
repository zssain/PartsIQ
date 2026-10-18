"""F54 Access & permissions facade (helper ``auth.identity``).

Returns the caller's OWN resolved identity: the verified subject id, the server-trusted roles, an
``is_anonymous`` flag (true for a demo caller) and the active demo session id. It is built ENTIRELY
from the verified :class:`ActorContext` — the roles are the DB-sourced roles the token verifier
resolved, never a client-supplied or JWT-claimed role, so a demo caller sees an empty role list
here no matter what the presentational demo UI shows. This is the single place the frontend learns
what the server will actually authorise, which keeps the role gate and the UI honest. It is
read-only and reveals only the caller's own identity. Access is ``customer``.

No backing store is needed — the identity is the actor — so this returns real data offline too.
"""
from __future__ import annotations

from partsiq.core.api_models import IdentityView
from partsiq.core.contracts import ActorContext
from partsiq.core.dependencies import AppContainer


async def identity(actor: ActorContext, *, container: AppContainer) -> IdentityView:
    """Return the caller's own resolved identity, derived only from the verified actor.

    A demo caller carries no staff role and no persistent account, so it is reported as anonymous
    with its active demo session id; a real account reports its DB-sourced roles.
    """
    # In fixture mode every caller is the anonymous demo actor (no persistent account, no staff
    # role). In DB mode the verifier resolves a real account with its DB-sourced roles.
    is_anonymous = container.is_fixture
    return IdentityView(
        id=actor.user_id,
        roles=list(actor.roles),
        is_anonymous=is_anonymous,
        demo_session_id=actor.session_id,
    )
