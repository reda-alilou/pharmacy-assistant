from pharmacy_infrastructure.migrations import run
from pharmacy_language.storage.postgres.models import metadata

run("language", metadata)
