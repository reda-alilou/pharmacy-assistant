"""Safe storage failure without database details or transport dependencies."""


class StorageUnavailable(Exception):
    def __init__(self):
        super().__init__("Le stockage est indisponible. Réessayez dans un instant.")
