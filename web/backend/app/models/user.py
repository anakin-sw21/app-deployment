from web.backend.app.utils import enforce_types
from datetime import datetime

@enforce_types
class User:
    def __init__(self,_id:int, first_name:str, last_name:str, timestamp_created : datetime, timestamp_edited : datetime=None,  password:str="", email:str="", phone:str="", photo:str=""):
        self.__nic =_id
        self.__first_name = first_name
        self.__last_name = last_name
        self.__phone = phone
        self.__password = password
        self.__email = email
        self.__photo = photo
        self.__timestamp_created = timestamp_created
        self.__timestamp_edited = timestamp_edited