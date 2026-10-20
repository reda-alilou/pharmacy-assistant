from pharmacy_infrastructure.migrations import run
from pharmacy_core.storage.postgres.models import metadata

run("core", metadata)
