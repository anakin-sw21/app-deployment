import datetime
from typing import List
from bson import ObjectId
from gridfs.synchronous.grid_file import GridFS

from web.backend.app.store import in_memory_store
from pymongo.synchronous.database import Database

from web.backend.app.utils import obj_prediction_decryption, unparse_image,get_bounding_boxes, delete_bboxes_images
from web.backend.app.services.default_service import DefaultService


class PredictionService(DefaultService):
    def __init__(self, table:Database):
        super().__init__(table)
        self._name = "crimes"

    def find_one(self, query, fs:GridFS, filter: dict = None):
        # p =self._table[self._name].find_one({
        #     "_id" : ObjectId("682fb4c0288a7883b0be962b"),
        #     "predictions._id": ObjectId(_id)
        # },
        # {
        #     "predictions.$": 1  # Project only the matching prediction
        # })
        # self._table[self._name].update_many(
        #     {},
        #     {"$unset": {"predictions.$[elem].crime_id": ""}},
        #     array_filters=[{"elem.crime_id": {"$exists": True}}]
        # )
        pipeline = [
            # {"$match": {"_id": ObjectId("682fb4c0288a7883b0be962b")}},
            {"$unwind": "$predictions"},
            {"$match": {"predictions._id": ObjectId(query)}},
            {"$replaceRoot": {"newRoot": "$predictions"}}
        ]
        p = list(self._table[self._name].aggregate(pipeline))[0]
        prediction = {}
        if p:
            results = obj_prediction_decryption(fs.find_one({"_id": ObjectId(query)}))
            if "deleted_bboxes" in p:
                indexes = p["deleted_bboxes"]
                for i, result in enumerate(results):
                    frame_indexes = [y for x, y in indexes if x == i]
                    result.boxes = result.boxes[[i for i in range(len(result.boxes)) if i not in frame_indexes]]
            #
            # if len(results)>1:
            #     # Draw results on video
            #     new_frames = []
            #     for result in results:
            #         new_frames.append(result.plot())
            #     media = unparse_video(new_frames, len(results))
            # else:
            #     # Draw results on image
            #     annotated_frame = results[0].plot()
            #     media = unparse_image(annotated_frame)
            annotated_frame = results[0].plot()
            media = unparse_image(annotated_frame)
            prediction["image"] = media

        return prediction

    def get_prediction_result(self, _id, fs:GridFS, proj_dict: dict = None):
        pipeline = [
            # {"$match": {"_id": ObjectId("682fb4c0288a7883b0be962b")}},
            {"$unwind": "$predictions"},
            {"$match": {"predictions._id": ObjectId(_id)}},
            {"$replaceRoot": {"newRoot": "$predictions"}}
        ]
        p = list(self._table[self._name].aggregate(pipeline))[0]

        prediction = dict()
        if p:
            # if "crypted_obj_predict" in p:
                # results = obj_prediction_decryption(p["crypted_obj_predict"])
            results = obj_prediction_decryption(fs.find_one({"_id": ObjectId(_id)}))

            if "id" in p:
                prediction["index"] = str(p["id"])
            if "_id" in p:
                prediction["index"] = str(p["_id"])
            if "name" in p:
                prediction["name"] = p["name"]
            print(prediction["index"])
            if "deleted_bboxes" in p:
                prediction["deleted_bboxes"] = p["deleted_bboxes"]
            else:
                prediction["deleted_bboxes"] = list(list())
            prediction["timestamp_created"] = p["timestamp_created"]

            in_memory_store[prediction["index"]] = {"results": results}
            if "fps" in p:
                in_memory_store[prediction["index"]]["fps"] = p["fps"]
                prediction["fps"] = p["fps"]

            prediction.update(delete_bboxes_images([prediction["index"]]+prediction["deleted_bboxes"]))

            return_value = get_bounding_boxes(results, prediction["index"])
            prediction["results"] = return_value

        return prediction


    def create_instance_from_dict(self, data:dict, required_fields:List[str]):
        if all(field in data for field in required_fields):
            print("done")
            crime_id = data["crime_id"]
            del data["crime_id"]
            self._table["crimes"].update_one({"_id" : crime_id}, {"$push" : {"predictions" : data}})

    def update_instance_from_dict(self, data:dict, unset:dict = None):
        _id = data["_id"]
        user_id = data["user"]["_id"]
        data["timestamp_edited"] = datetime.datetime.now()

        self._table["crimes"].update_one({
                "predictions._id": ObjectId(_id),
                "predictions.user._id": int(user_id),
            },
            {
                "$set": {
                    "predictions.$[pred]": data
                }
            },
            array_filters=[{"pred._id": _id}]
        )
        return str(self._table["crimes"].find_one({
                "predictions._id": ObjectId(_id),
                "predictions.user._id": int(user_id),
            })["_id"])
    def delete_instance_by_fields(self, query : dict):
        crime_id = str(self._table["crimes"].find_one({
                "predictions._id": query["_id"],
                "predictions.user._id": query["user._id"],
            })["_id"])

        self._table["crimes"].update_many(
            {},
            {
                "$pull": {
                    "predictions": query
                }
            }
        )
        return crime_id

    def find_all_aggregate(
            self,
            query: dict = None,
            projection: dict = None,
            column: str = "photo",
            sort_by: str = "_id",
            sort_order: str = None,
            added_column_name: str = "",
            page : int = 1,
            page_size = 1,
            search_value: str = None,
            or_columns : List[str] = None,
            pipeline=None
        ) -> dict:

        initial_pipeline = [{"$unwind": "$predictions"},
                {"$replaceRoot": {"newRoot": "$predictions"}}]

        if pipeline is None:
            pipeline = initial_pipeline
        else:
            pipeline = pipeline + initial_pipeline
        return super().find_all_aggregate(
            query,
            projection,
            column,
            sort_by,
            sort_order,
            added_column_name,
            page,
            page_size,
            search_value,
            or_columns,
            pipeline
        )

    def get_class_id(self, id):
        print(id)
        if self._table["crimes"].count_documents({"_id": ObjectId(id)})==1:
            return "crime"
        elif self._table["crimes"].count_documents({"predictions._id": ObjectId(id)})==1:
            return "prediction"
        else:
            return "Error"