import json
import secrets
import datetime

from bson import ObjectId
from flask import jsonify, request
from flask_jwt_extended import get_jwt_identity
from gridfs.synchronous.grid_file import GridFS
from pymongo.synchronous.database import Database
from web.backend.app.models.crime import Crime
from web.backend.app.models.superuser import Superuser
from web.backend.app.models.user import User
from web.backend.app.routes.jwt_route import JWTBlueprint
from web.backend.app.services.crime_service import CrimeService
from web.backend.app.services.team_service import TeamService
from web.backend.app.utils import enforce_types, cast_param, get_required_fields, fixIDMongo, convert_objectid_to_str


@enforce_types
class CrimeRoute:
    def __init__(self, database:Database, fs: GridFS):
        self.__database = database
        self.__blueprint = JWTBlueprint('crime', __name__, url_prefix='/api/crimes')
        self.__service= CrimeService(database)
        self.__team_service= TeamService(database)
        self.__fs = fs

        @self.__blueprint.post("add")
        def create_crime():
            data = request.form
            required_fields = get_required_fields(Crime, ["photo", "team", "description", "predictions", "superuser"])

            # if not all(field in data for field in required_fields):
            #     return jsonify({"error": "Missing required fields"}), 400

            crime = dict()

            for field in required_fields:
                crime[field] = cast_param(Crime, field, data[field])


            if "description" in request.form:
                crime["description"] = request.form["description"]

            required_user_fields = get_required_fields(User, ["password", "timestamp_edited", "photo"], _id=True)

            crime["_id"] = ObjectId(secrets.token_hex(12))
            crime["timestamp_created"] = datetime.datetime.now()

            team = []
            if "team" in request.form:
                team = json.loads(request.form["team"])
                for i, user in enumerate(team):
                    user_team = dict()
                    for field in required_user_fields:
                        user_team[field] = (
                            cast_param(User, field, user[field if field!="_id" else "id"]))
                    team[i] = {"crime" : crime, "user" : user_team}

            if "superuser" in data:
                crime["superuser"] = json.loads(data["superuser"])
                su_crime = dict()
                print(data["superuser"])
                required_superuser_fields = get_required_fields(Superuser, ["password", "timestamp_edited", "photo"], _id=True)

                for field in required_superuser_fields:
                    su_crime[field] = cast_param(Superuser, field, crime["superuser"][field if field!="_id" else "id"])

                crime["superuser"] = su_crime
            else:
                return jsonify({"error": "Superuser Not Specified"}), 401

            if "photo" in request.form:
                crime["photo"] = request.form["photo"]

            # try:
            # if not self.__service.is_valid_team(crime["team"]):
            #     return jsonify({"error": "Invalid team"}), 400
            if not self.__service.is_valid_instance(crime):
                return jsonify({"error": "Invalid Superuser Id"}), 401
            else:
                self.__service.create_instance_from_dict(crime, required_fields)
                if team:
                    self.__team_service.create_instances_from_list_dict(team, [])
                return jsonify({"message": "Crime added successfully"}), 201
            # except Exception as e:
            #     return jsonify({"error": str(e)}), 500

        @self.__blueprint.get("/<id>")
        def get_crime_by_id(id):
            filter = {
                "_id": id,
                "superuser._id": int(get_jwt_identity())
            }
            crime = self.__service.find_one(filter)
            if crime is not None:
                return jsonify(crime), 200
            else:
                return jsonify({"error": "Crime Not Found"}), 404

        @self.__blueprint.put("update")
        def update_crime():
            data = request.form
            crime = dict()
            unset = dict()
            for field in data:
                if field!="team" and field!="superuser":
                    crime[field] = cast_param(Crime, field, data[field])

            if "photo" in request.form:
                if crime["photo"] != "":
                    crime["photo"] = request.form["photo"]
                else:
                    del crime["photo"]
                    unset = {"photo": ""}

            team = []
            required_user_fields = get_required_fields(User, ["password", "timestamp_edited", "photo"], _id=True)

            if "team" in request.form:
                team = json.loads(request.form["team"])
                for i, user in enumerate(team):
                    user_team = dict()
                    for field in required_user_fields:
                        user_team[field] = (
                            cast_param(User, field, user[field if field!="_id" else "id"]))
                    team[i] = {"crime" : crime, "user" : user_team}


            if "superuser" in data:
                crime["superuser"] = json.loads(data["superuser"])
                su_crime = dict()
                print(data["superuser"])
                required_superuser_fields = get_required_fields(Superuser, ["password", "timestamp_edited", "photo"], _id=True)

                for field in required_superuser_fields:
                    su_crime[field] = cast_param(Superuser, field, crime["superuser"][field if field!="_id" else "id"])

                crime["superuser"] = su_crime
            else:
                return jsonify({"error": "Superuser Not Specified"}), 401


            crime = fixIDMongo(crime)
            crime["_id"] = ObjectId(crime["_id"])
            print(list(data))
            # try:
            # if not self.__service.is_valid_team(crime["team"]):
            #     return jsonify({"error": "Invalid team"}), 401
            if not self.__service.is_valid_instance(crime) or int(crime["superuser"]["_id"])!=int(get_jwt_identity()):
                return jsonify({"error": "Invalid Superuser Id"}), 401
            print(crime)
            self.__team_service.delete_instances_by_fields({"crime._id" : crime["_id"]})
            if team:
                self.__team_service.create_instances_from_list_dict(team, [])

            self.__service.update_instance_from_dict(crime, unset)
            return jsonify({"message": "Crime updated successfully"}), 201

        @self.__blueprint.delete("delete/<id>")
        def delete_crime(id:str):
            query = dict()
            query["_id"] = ObjectId(id)
            query["superuser._id"] = int(get_jwt_identity())

            self.__service.delete_instance_by_fields(query, fs=self.__fs)
            return jsonify({"message": "Crime deleted successfully"}), 201

        @self.__blueprint.get("all")
        def get_all_crimes():
            filter = {
                "superuser._id": int(get_jwt_identity())
            }
            return jsonify(self.__service.find_all(filter, {"predictions" : 0, "team.crimes" : 0})), 200

        @self.__blueprint.get("all/no")
        def get_fast_all_crimes():
            page = request.args.get('page', 1, type=int)
            page_size = request.args.get('size', 1)
            key = request.args.get('sortKey', "_id")
            keyword = request.args.get('keyword', None)
            order = request.args.get('sortOrder', None)
            return jsonify(self.__service.find_all_aggregate(
                query={"superuser._id": int(get_jwt_identity())},
                projection={"predictions" : 0, "team.crimes" : 0},
                page=page,
                page_size=page_size,
                sort_by=key,
                sort_order=order,
                search_value=keyword,
                or_columns=["name", "description"],
                pipeline=[
                    {
                        "$lookup": {
                            "from": "teams",
                            "let": { "crime_id": "$_id" },
                            "pipeline": [
                                {
                                    "$match": {
                                        "$expr": { "$eq": [ "$crime._id", "$$crime_id" ] }
                                    }
                                },
                                {
                                    "$replaceWith": "$user"
                                }
                            ],
                            "as": "team"
                        }
                    }
                ]
            )), 200

        @self.__blueprint.get("picture/<id>")
        def get_crime_photo(id):
            filter = {
                "_id": id,
                "superuser._id": int(get_jwt_identity())
            }
            return jsonify(self.__service.find_one(filter, filter={"photo": 1})), 200

    def get_blueprint(self):
        return self.__blueprint