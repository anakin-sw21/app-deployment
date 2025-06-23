import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..','..')))


from flask_jwt_extended import JWTManager
from flask_socketio import SocketIO
from flask_cors import CORS
from flask_mail import Mail
from flask import Flask

from web.backend.app.routes.authentification_route import AuthenticationRoute
from web.backend.app.routes.prediction_route import PredictionRoute
from web.backend.app.routes.crime_route import CrimeRoute
from web.backend.app.routes.user_route import UserRoute
from web.backend.app.routes.ml_route import MLRoute
from datetime import timedelta

from web.backend.app.utils import get_db_instance, get_var


def create_app():
    app = Flask(__name__)
    CORS(app)
    try:

        db, fs = get_db_instance("prediction_db")
        with app.app_context():
            app.config['MAIL_SERVER'] = 'smtp.gmail.com'
            app.config['MAIL_PORT'] = 587
            app.config['MAIL_USE_TLS'] = True
            app.config['MAIL_USERNAME'] = get_var("email")
            app.config['MAIL_PASSWORD'] = get_var("password")
            app.config['PRIVATE_KEY'] = get_var("vapor_private_key")
            app.config['CLAIMS'] = get_var("email")
            app.config['MAIL_DEFAULT_SENDER'] = app.config['MAIL_USERNAME']
            mail = Mail(app)

            app.config["JWT_SECRET_KEY"] = get_var("jwt_secret_key")
            app.secret_key = get_var("session_secret_key")
            app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=24)
            JWTManager(app)

            socket_io = SocketIO(app, cors_allowed_origins="*", manage_session=False)

        app.register_blueprint(AuthenticationRoute(db).get_blueprint())
        app.register_blueprint(PredictionRoute(db, fs).get_blueprint())
        app.register_blueprint(CrimeRoute(db, fs).get_blueprint())
        app.register_blueprint(UserRoute(db, mail).get_blueprint())
        app.register_blueprint(MLRoute(socket_io).get_blueprint())
        #
        #     msg = Message('Hello from Flask',
        #                   recipients=['mejdeddine.dorbez@fsb.ucar.tn'])
        #     msg.body = 'This is a test email sent from a Flask app.'
        #     mail.send(msg)
        #     print('Email sent!')
    except Exception as e:
        print("Connection Failed!", str(e))

    return app, socket_io