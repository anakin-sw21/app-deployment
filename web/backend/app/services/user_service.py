from pymongo.synchronous.database import Database
from web.backend.app.services.default_service import DefaultService
from web.backend.app.utils import enforce_types
from typing import List

@enforce_types
class UserService(DefaultService):
    def __init__(self, table:Database):
        super().__init__(table)
        self._name = "users"

    def is_valid_primary_field(self, field, instance:dict):
        query = dict()
        if isinstance(field, list):
            for elt in field:
                query[elt] = instance[elt]
        else:
            query[field] = instance[field]

        query["_id"] = {"$ne": instance["_id"]}
        return self._table[self._name.lower()].find_one(query) is None