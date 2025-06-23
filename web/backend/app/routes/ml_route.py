import json

from flask_socketio import SocketIO, join_room

from flask import jsonify, request, session, current_app
from pywebpush import WebPushException

from web.backend.app.routes.jwt_route import JWTBlueprint
from web.backend.app.services.ml_service import MLService
from web.backend.app.services.notification_service import NotificationService
from web.backend.app.utils import enforce_types, delete_bboxes_images, get_raw_token


@enforce_types
class MLRoute:
    def __init__(self, socket_io:SocketIO):
        self.__blueprint = JWTBlueprint('machinelearning', __name__, url_prefix='/api/predict')
        self.__socket_io = socket_io
        self.__service= MLService()
        self.__notif_service = NotificationService()

        @self.__blueprint.post("")
        def predict():
            if 'image' not in request.files:
                return {'error': 'No file part'}, 400

            image = request.files['image']
            index = request.form['index']
            return jsonify(self.__service.predict(image, index)), 200

        @self.__blueprint.post("update")
        def reload_predicted_image():
            raw = request.get_data(as_text=True)
            try:
                data = json.loads(raw)
                return jsonify(delete_bboxes_images(data)), 200
            except json.JSONDecodeError:
                return jsonify({'error': 'Invalid JSON'}), 400

        @self.__socket_io.on('connect')
        def on_connect(header):

            token = get_raw_token(header.get("Authorization"))
            print("Token received:", token)

            if not token:
                return False

            session['token'] = token
            join_room(token)

        # @self.__blueprint.get('/rt/<language>')
        @self.__socket_io.on("frame")
        def video_feed(data):
            frame_unparsed = data['image'].split(',')[1]
            language = data['language']
            token = data.get("token")
            subscription = self.__notif_service.get_subscription(token)

            def respond(data, _):
                socket_io.emit("processed_frame", data, to=token)
                # handle optional notifications here

            self.__service.generate_prediction_rt(
                frame_unparsed, language, subscription, self.__notif_service, respond
            )

        @self.__blueprint.post('subscribe')
        def subscribe():
            self.__notif_service.set_private_key(
                current_app.config.get("PRIVATE_KEY")
            )

            self.__notif_service.set_claims(
                current_app.config.get("CLAIMS")
            )
            try:
                self.__notif_service.subscribe(request)
                return jsonify({"success": True}), 201
            except WebPushException as ex:
                print("Push failed:", repr(ex))
                return jsonify({"success": False, "error": str(ex)}), 500

    def get_blueprint(self):
        return self.__blueprint