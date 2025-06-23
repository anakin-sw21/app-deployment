from flask import Blueprint
from flask_jwt_extended import verify_jwt_in_request

class JWTBlueprint(Blueprint):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Apply JWT verification to all routes in this blueprint
        @self.before_request
        def protect():
            verify_jwt_in_request()