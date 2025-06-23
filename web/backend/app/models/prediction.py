from web.backend.app.utils import enforce_types
from web.backend.app.models.user import User

@enforce_types
class Prediction:
    def __init__(
            self,
            _id:str,
            name:str,
            crypted_obj_predict:str,
            timestamp_created:str,
            timestamp_edited:str,
            object_count:list,
            deleted_bboxes:list,
            user:User
    ):
        self.__id = _id
        self.__name = name
        self.__user = user
        self.__crypted_obj_predict = crypted_obj_predict
        self.__deleted_bboxes = deleted_bboxes
        self.__timestamp_created = timestamp_created
        self.__timestamp_edited = timestamp_edited
        self.__object_count = object_count