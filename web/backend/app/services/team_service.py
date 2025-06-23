from pymongo.synchronous.database import Database
from typing import List
from web.backend.app.services.default_service import DefaultService
from web.backend.app.utils import enforce_types


@enforce_types
class TeamService(DefaultService):
    def __init__(self, table:Database):
        super().__init__(table)
        self._name = "teams"

    def create_instances_from_list_dict(self, data:list, required_fields:List[str]):
        if all(field in data for field in required_fields):
            self._table[self._name.lower()].insert_many(data)