from bson import ObjectId
from gridfs.synchronous.grid_file import GridFS
from pymongo.synchronous.database import Database
from web.backend.app.services.default_service import DefaultService
from web.backend.app.utils import enforce_types
from typing import List

@enforce_types
class CrimeService(DefaultService):
    def __init__(self, table:Database):
        super().__init__(table)
        self._name = "crimes"

    def is_valid_team(self, array:List[int]) -> bool:
        return (self._table["users"].count_documents({"_id": {"$in": array}})
                +(self._table["superusers"].count_documents({"_id": {"$in": array}}))==len(array))

    def delete_instance_by_fields(self, query:dict, fs : GridFS = None):
        crime = self._table["crimes"].find_one(query, {"predictions._id":1})
        if not crime:
            print("Crime not found")
            return

        predictions = crime.get("predictions", [])

        for prediction in predictions:
            prediction_id = prediction["_id"]
            pipeline = [
                {"$unwind": "$predictions"},
                {"$match": {"predictions._id": ObjectId(prediction_id)}},
                {"$replaceRoot": {"newRoot": "$predictions"}}
            ]
            prediction = list(self._table[self._name].aggregate(pipeline))[0]
            if not prediction:
                continue
            if prediction_id:
                try:
                    fs.delete(prediction_id)
                    print(f"Deleted GridFS file: {prediction_id}")
                except Exception as e:
                    print(f"Failed to delete GridFS file {prediction_id}: {e}")


        self._table["teams"].delete_many({"crime._id" : crime["_id"]})
        self._table["crimes"].delete_one(query)
        del crime
        print(f"Deleted crime: {query['_id']}")

    def update_instance_from_dict(self, data:dict, unset:dict = None):
        super().update_instance_from_dict(data, unset)
        # filter = {
        #     "_id": data["_id"]
        # }
        # data = self.find_all(filter, {"predictions" : 0, "team.crimes" : 0})[0]
        # print(list(data))
        # for user in data["team"]:
        #     crime_obj = {
        #         "_id": ObjectId(data["_id"]),
        #         "name": data["name"]
        #     }
        #
        #     if "photo" in data:
        #         crime_obj["photo"] = "true"
        #     else:
        #         crime_obj["photo"] = "false"
        #     print(user["id"])
        #     crime_obj["timestamp_created"] = data["timestamp_created"]
        #
        #     if "timestamp_edited" in data:
        #         crime_obj["timestamp_edited"] = data["timestamp_edited"]
        #     if "description" in data:
        #         crime_obj["description"] = data["description"]
        #
        #     pipeline = [
        #         {
        #             "$set": {
        #                 "crimes": {
        #                     "$filter": {
        #                         "input": "$crimes",
        #                         "as": "crimes",
        #                         "cond": {"$ne": ["$$crimes._id", data["_id"]]}
        #                     }
        #                 }
        #             }
        #         },
        #         {
        #             "$set": {
        #                 # Add embedded_student if this document is the correct course
        #                 "crimes": {
        #                     "$cond": [
        #                         {"$eq": ["$_id", user["id"]]},
        #                         {"$concatArrays": ["$crimes", [crime_obj]]},
        #                         "$crimes"
        #                     ]
        #                 }
        #             }
        #         }
        #     ]
        #
        #     self._table["users"].update_one({"_id" : int(user["id"])}, pipeline)