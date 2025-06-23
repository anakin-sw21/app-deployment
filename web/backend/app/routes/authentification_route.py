import datetime
import numpy as np
import cv2
import base64
from flask import Blueprint, jsonify, request
from flask_socketio import SocketIO, emit
from pymongo.synchronous.database import Database
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from web.backend.app.models.superuser import Superuser
from web.backend.app.models.user import User
from web.backend.app.services.su_service import SUService
from web.backend.app.services.user_service import UserService
from web.backend.app.utils import enforce_types, encrypt_string, get_required_fields, cast_param, fixIDMongo

@enforce_types
class AuthenticationRoute:
    def __init__(self, database:Database):
        self.__database = database
        self.__blueprint = Blueprint('auth', __name__, url_prefix='/')
        self.__service = None

        @self.__blueprint.post("/register_su")
        def register_su():
            data = request.json
            required_fields = get_required_fields(Superuser, _id=True)

            if not all(field in data for field in required_fields):
                return jsonify({"error": "Missing required fields"}), 400

            if int(data["password"])<6:
                return jsonify({"error": "Invalid password"}), 401

            superuser = {}

            for field in required_fields:
                superuser[field] = cast_param(Superuser, field, data[field] if field != "password" else encrypt_string(encrypt_string(data["password"])))

            try:
                self.__service= SUService(database)
                self.__service.create_instance_from_dict(superuser, required_fields)
                return jsonify({"message": "Superuser added successfully"}), 201
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @self.__blueprint.post("/register")
        def create_user():
            data = request.form
            required_fields = get_required_fields(User, ["photo"], _id=True)


            if not all(field in data for field in required_fields):
                return jsonify({"error": "Missing required fields"}), 400
            if not "id" or "nic" in data:
                return jsonify({"error": "No Identifier Detected"}), 400

            user = dict()

            for field in required_fields:
                user[field] = cast_param(User, field, data[field] if field !="password" else encrypt_string(data["password"]))

            if "photo" in request.form:
                user["photo"] = request.form["photo"]

            user = fixIDMongo(user)
            try:
                self.__service= UserService(database)

                if not self.__service.is_valid_field("_id", user):
                    return jsonify({"error": "Invalid NIC"}), 401
                elif not self.__service.is_valid_field("email", user):
                    return jsonify({"error": "Invalid Email"}), 401
                elif not self.__service.is_valid_instance(user):
                    return jsonify({"error": "Invalid Superuser Id"}), 401
                else:
                    user["timestamp_created"] = datetime.datetime.now()
                    user["timestamp_edited"] = datetime.datetime.now()
                    user["superuser_id"] = int(data["superuser_id"])
                    self.__service.create_instance_from_dict(user, required_fields)
                    return jsonify({"message": "User added successfully"}), 201
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @self.__blueprint.post("/login")
        def login():
            data = request.json

            if all(field in data for field in ["email", "password"]):
                fields = {
                    "email": data["email"].lower(),
                    "password": encrypt_string(data["password"])
                }

            elif all(field in data for field in ["nic", "password"]):
                fields = {
                    "_id": int(data["nic"]),
                    "password": encrypt_string(data["password"])
                }
            else:
                return jsonify({"error": "Email and password or NIC and password required"}), 400

            # Find user by email
            user = UserService(self.__database).find_instance_by_field(fields)
            if not user:
                return jsonify({"error": "Invalid email or password"}), 401

            print(list(user))
            if user:
                returned_user = {
                    "id": user["_id"],
                    "first_name": user["first_name"],
                    "last_name": user["last_name"],
                    "email": user["email"],
                    "phone": user["phone"],
                    "timestamp_created": user["timestamp_created"],
                    "superuser": user["superuser"]
                }
                return {
                    "user" : returned_user,
                    "token": create_access_token(identity=user["_id"])
                }, 200

        @self.__blueprint.post("/login_su")
        def login_su():
            data = request.json

            if all(field in data for field in ["email", "password"]):
                fields = {
                    "email": data["email"].lower(),
                    "password": encrypt_string(data["password"])
                }

            elif all(field in data for field in ["nic", "password"]):
                fields = {
                    "_id": int(data["nic"]),
                    "password": encrypt_string(data["password"])
                }
            else:
                return jsonify({"error": "Email and password or NIC and password required"}), 400

            superuser = SUService(self.__database).find_instance_by_field(fields)
            if not superuser:
                return jsonify({"error": "Invalid email or password"}), 401

            # Authentication successful
            if superuser:
                returned_superuser = {
                    "id": superuser["_id"],
                    "first_name": superuser["first_name"],
                    "last_name": superuser["last_name"],
                    "email": superuser["email"],
                    "phone": superuser["phone"],
                    "timestamp_created": superuser["timestamp_created"],
                    "superuser": None
                }
                return {
                    "user": returned_superuser,
                    "token": create_access_token(identity=superuser["_id"])
                }, 200

    def get_blueprint(self):
        return self.__blueprint
