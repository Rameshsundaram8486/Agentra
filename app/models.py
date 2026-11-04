"""Imports every ORM model so Base.metadata is complete (Alembic autogenerate and tests)."""

from app.infrastructure import job_queue, outbox  # noqa: F401
from app.modules.artifacts import models as artifacts_models  # noqa: F401
from app.modules.audit import models as audit_models  # noqa: F401
from app.modules.decisions import models as decisions_models  # noqa: F401
from app.modules.design import models as design_models  # noqa: F401
from app.modules.executions import models as executions_models  # noqa: F401
from app.modules.identity import models as identity_models  # noqa: F401
from app.modules.oversight import models as oversight_models  # noqa: F401
from app.modules.projects import models as projects_models  # noqa: F401
from app.modules.reporting import models as reporting_models  # noqa: F401
from app.modules.requirements import models as requirements_models  # noqa: F401
from app.modules.workflow import models as workflow_models  # noqa: F401
