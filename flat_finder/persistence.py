"""Import all ORM model modules so their tables register on Base.metadata.

Import this module wherever the full schema must be known up front
(Alembic's env.py, test fixtures that call create_all).
"""

import flat_finder.listings.persistence
import flat_finder.pois.persistence
import flat_finder.users.persistence
import flat_finder.zones.persistence  # noqa: F401
