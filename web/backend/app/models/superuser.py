from web.backend.app.utils import enforce_types
from web.backend.app.models.user import User
from datetime import datetime

@enforce_types
class Superuser(User):
    def __init__(self,_id:int, first_name:str, last_name:str, password:str, email:str, phone:str, photo:str, timestamp_created:datetime, timestamp_edited:datetime):
        super().__init__(_id, first_name, last_name, timestamp_created, timestamp_edited,  password, email, phone, photo)