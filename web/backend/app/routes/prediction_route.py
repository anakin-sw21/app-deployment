import json
from bson import ObjectId
from flask import Blueprint, jsonify, request
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from gridfs.synchronous.grid_file import GridFS
from pymongo.synchronous.database import Database
from web.backend.app.models.prediction import Prediction
from web.backend.app.services.prediction_service import PredictionService
from web.backend.app.store import in_memory_store
from web.backend.app.utils import enforce_types, \
    obj_prediction_encryption, get_current_datetime, get_required_fields, string_to_datetime


@enforce_types
class PredictionRoute:
    def __init__(self, database:Database, fs:GridFS):
        self.__database = database
        self.__fs = fs
        self.__blueprint = Blueprint('predictions', __name__, url_prefix='/api/predictions')
        self.__service= PredictionService(database)


        @self.__blueprint.before_request
        def protect_all_routes():
            verify_jwt_in_request()

        @self.__blueprint.post("add/<crime_id>")
        def insert_prediction(crime_id):
            index = request.form['index']
            name = request.form['name']
            user = json.loads(request.form['user'])
            required_fields =get_required_fields(Prediction, ["timestamp_edited", "deleted_bboxes", "crypted_obj_predict"], _id=True)

            if index in in_memory_store:
                results = in_memory_store[index]
                crypted_prediction = obj_prediction_encryption(results["results"])

                user["_id"] = user["id"]
                del user["id"]
                id = ObjectId(index)

                prediction = {
                    "_id": id,
                    "name": name,
                    # "crypted_obj_predict": crypted_prediction,
                    "timestamp_created": get_current_datetime(),
                    "user": user,
                }

                if "deleted_bboxes" in request.form:
                    if request.form["deleted_bboxes"] != "[[]]":
                        prediction["deleted_bboxes"] = json.loads(request.form["deleted_bboxes"])

                if "object_count" in results:
                    prediction["object_count"] = results["object_count"]
                if "fps" in in_memory_store[index]:
                    prediction["fps"] = in_memory_store[index]["fps"]

                prediction["crime_id"] = ObjectId(crime_id)

                try:
                    self.__service.create_instance_from_dict(prediction, required_fields+["crime_id"])
                    self.__fs.put(crypted_prediction, _id= id, filename=f"prediction_{index}")
                    return jsonify({"message": "Prediction added successfully"}), 201
                except Exception as e:
                    return jsonify({"error": str(e)}), 500
            else:
                return jsonify({"error": "Not a valid prediction"}), 500

        @self.__blueprint.put("update/<crime_id>")
        def update_prediction(crime_id):
            index = request.form['index']
            name = request.form['name']
            user = json.loads(request.form['user'])
            timestamp = request.form['timestamp_created']

            if index in in_memory_store:
                results = in_memory_store[index]
                user["_id"] = user["id"]
                del user["id"]
                id = ObjectId(index)

                prediction = {
                    "_id": id,
                    "name": name,
                    "timestamp_created" : string_to_datetime(timestamp),
                    # "crypted_obj_predict": crypted_prediction,
                    "user": user,
                }

                unset=dict()

                if "deleted_bboxes" in request.form:
                    if request.form["deleted_bboxes"] != "[[]]":
                        prediction["deleted_bboxes"] = json.loads(request.form["deleted_bboxes"])
                else:
                    unset["deleted_bboxes"] = ""

                if "object_count" in results:
                    prediction["object_count"] = results["object_count"]
                else:
                    unset["object_count"] = ""

                try:
                    crime_id = self.__service.update_instance_from_dict(prediction, unset)
                    # self.__fs.put(crypted_prediction, _id=id, filename=f"prediction_{index}")
                    return jsonify({"message": "Prediction updated successfully", "crime_id" : crime_id}), 201
                except Exception as e:
                    return jsonify({"error": str(e)}), 500
            else:
                return jsonify({"error": "Not a valid prediction"}), 500

        @self.__blueprint.delete("delete/<id>")
        def delete_prediction(id:str):
            query = {
                "_id": ObjectId(id)
                ,
                "user._id": int(get_jwt_identity())
            }
            crime_id = self.__service.delete_instance_by_fields(query)
            self.__fs.delete(ObjectId(id))
            return jsonify({"message": "Prediction deleted successfully", "crime_id" : crime_id}), 201

        @self.__blueprint.get("one/<id>")
        def get_one_prediction(id):
            return jsonify(self.__service.get_prediction_result(id, self.__fs)), 200

        @self.__blueprint.get("all/<id>")
        def get_all_predictions(id):
            return jsonify(self.__service.find_all({"_id" : int(id)}, {"prediction.$" : 1})), 200

        @self.__blueprint.get("all/no/<id>")
        def get_fast_all_predictions(id):
            page = request.args.get('page', 1, type=int)
            page_size = request.args.get('size', 1)
            key = request.args.get('sortKey', "_id")
            keyword = request.args.get('keyword', None)
            order = request.args.get('sortOrder', None)
            X = self.__service.find_all_aggregate(
                query={"_id": ObjectId(id)},
                column="crypted_obj_predict",
                added_column_name="image",
                page=page,
                page_size=page_size,
                sort_by=key,
                sort_order=order,
                or_columns=["name", "description"],
                search_value=keyword)
            print(X)
            return jsonify(X
            ), 200

        @self.__blueprint.get("picture/<id>")
        def get_prediction_image(id):
            return jsonify(self.__service.find_one(id, self.__fs,{"prediction._id" : 1})), 200

        @self.__blueprint.get("type/<id>")
        def get_type_id(id):
            return jsonify(self.__service.get_class_id(id)), 200

    def get_blueprint(self):
        return self.__blueprint