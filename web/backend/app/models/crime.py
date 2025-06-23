from web.backend.app.models.prediction import Prediction
from web.backend.app.models.user import User
from web.backend.app.utils import enforce_types
from typing import List

@enforce_types
class Crime:
    def __init__(
            self,
            _id:str,
            name:str,
            description:str, 
            superuser: User,
            predictions:List[Prediction],
            team:List[User]
        ):
        self.__id = _id
        self.__name = name
        self.__description = description
        self.__superuser = superuser
        self.__predictions = predictions
        self.__team = team