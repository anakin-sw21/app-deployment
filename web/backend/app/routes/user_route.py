import os
import json
import datetime

from flask_jwt_extended import get_jwt_identity
from flask_mail import Mail, Attachment
from flask import jsonify, request, current_app, render_template
from pymongo.synchronous.database import Database
from web.backend.app.models.user import User
from web.backend.app.routes.jwt_route import JWTBlueprint
from web.backend.app.services.user_service import UserService
from web.backend.app.utils import enforce_types, cast_param, get_required_fields, fixIDMongo, encode_image, \
    encrypt_string


@enforce_types
class UserRoute:
    def __init__(self, database:Database, mail:Mail):
        self.__database = database
        self.__blueprint = JWTBlueprint('user', __name__, url_prefix='/api/users')
        self.__service= UserService(database)
        self.__mail = mail

        @self.__blueprint.post("add")
        def create_user():
            data = request.form
            required_fields = get_required_fields(User, ["photo", "timestamp_created", "timestamp_edited"])

            if not all(field in data for field in required_fields):
                return jsonify({"error": "Missing required fields"}), 400

            user = {}

            for field in required_fields:
                user[field] = cast_param(User, field, data[field])
            if "photo" in data:
                user["photo"] = data["photo"]
            user["_id"] = int(data["_id"])
            user["timestamp_created"] = datetime.datetime.now()
            user["timestamp_edited"] = datetime.datetime.now()
            user["superuser"] = json.loads(data["superuser"])
            user["superuser"]["_id"] = json.loads(data["superuser"])["id"]
            del user["superuser"]["id"]
            print(user["password"])
            user["password"] = encrypt_string(encrypt_string(data["password"]))
            # try:
            if not self.__service.is_valid_instance(user) or int(user["superuser"]["_id"])!=int(get_jwt_identity()):
                return jsonify({"error": "Invalid Superuser Id"}), 401
            else:
                self.__service.create_instance_from_dict(user, required_fields)
                return jsonify({"message": "User added successfully"}), 201
            # except Exception as e:
            #     return jsonify({"error": str(e)}), 500

        @self.__blueprint.put("update")
        def update_user():
            data = request.form
            user = dict()
            unset = dict()

            for field in data:
                if field!="timestamp_edited" and field!="timestamp_created":
                    user[field] = cast_param(User, field, data[field])
            if "photo" in request.form:
                if user["photo"] != "":
                    user["photo"] = request.form["photo"]
                else:
                    del user["photo"]
                    unset = {"photo": ""}
            else:
                unset = {"photo": ""}

            user = fixIDMongo(user)

            user["_id"] = int(data["id"])
            user["superuser"] = json.loads(data["superuser"])
            user["superuser"]["id"] = int(user["superuser"]["id"])
            user["superuser"]["_id"] = json.loads(data["superuser"])["id"]
            del user["superuser"]["id"]

            if not self.__service.is_valid_primary_field(["email"], user):
                return jsonify({"error": "Invalid Email"}), 401
            if not self.__service.is_valid_primary_field("email", user):
                return jsonify({"error": "Invalid Email 2"}), 401
            if not self.__service.is_valid_instance(user) or int(user["superuser"]["_id"])!=int(get_jwt_identity()):
                return jsonify({"error": "Invalid Superuser Id"}), 401
            # else:
            self.__service.update_instance_from_dict(user, unset)
            return jsonify({"message": "User updated successfully"}), 201

        @self.__blueprint.delete("delete/<id>")
        def delete_user(id:int):
            filter = dict()

            filter["_id"] = int(id)
            filter["superuser._id"] = int(get_jwt_identity())

            self.__service.delete_instance_by_fields(filter)
            return jsonify({"message": "User deleted successfully"}), 201

        @self.__blueprint.get("all")
        def get_all_users():
            return jsonify(self.__service.find_all({"superuser._id":int(get_jwt_identity())}, {"password": 0, "superuser_id" : 0})), 200

        @self.__blueprint.get("all/no")
        def get_fast_all_users():
            page = request.args.get('page', 1, type=int)
            page_size = request.args.get('size', 1)
            key = request.args.get('sortKey', "_id")
            key = key if key!="name" and key is not None else "first_name"
            keyword = request.args.get('keyword', None)
            order = request.args.get('sortOrder', None)
            return jsonify(self.__service.find_all_aggregate(
                query={"superuser._id": int(get_jwt_identity())},
                projection={"password": 0, "superuser_id": 0, "crimes" : 0},
                page=page,
                page_size=page_size,
                sort_by=key,
                sort_order=order,
                search_value=keyword,
                or_columns=["first_name", "last_name", "email", "phone"])
            ), 200
        @self.__blueprint.get("picture/<id>")
        def get_user_photo(id):
            filter = {
                "_id": id,
                "superuser._id": int(get_jwt_identity())
            }
            return jsonify(self.__service.find_one(filter, {"photo": 1})), 200

        @self.__blueprint.get('/password-forgotten')
        def send_email():
            msg = 'Hello from Flask'
            recipients = ['najetbenhassine25@gmail.com']
            # Path to your image (e.g., static folder or full path)
            html = render_template("forget_pwd_template.html", name="Mejd", logo_id="cid:logo_image")
            filename = "icon.png"
            image_path = os.path.join(current_app.root_path, 'static', filename)

            with open(image_path, 'rb') as img:
                attach = Attachment(
                    filename=filename,
                    content_type="image/png",
                    data=img.read(),
                    disposition='inline',
                    headers={'Content-ID': '<logo_image>'}
                )
            try:
                self.__mail.send_message(html=html, attachments=[attach], recipients=recipients, subject=msg, sender=("SBI CSI Notification Alert", "mejddz21@gmail.com"))
                return jsonify({"message": "Email sent successfully"}), 201
            except Exception as e:
                return jsonify({"error": str(e)}), 401

    def get_blueprint(self):
        return self.__blueprint