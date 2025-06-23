from pymongo.synchronous.database import Database
from web.backend.app.services.user_service import UserService
from web.backend.app.utils import enforce_types

@enforce_types
class SUService(UserService):
    def __init__(self, table:Database):
        super().__init__(table)
        self._name = "superusers"