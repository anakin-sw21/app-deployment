import json
from pywebpush import webpush, WebPushException

from web.backend.app.utils import enforce_types, get_raw_token


@enforce_types
class NotificationService:
    def __init__(self, private_key = None, claims = None):
        self.__VAPID_PRIVATE_KEY = private_key
        self.__VAPID_CLAIMS = claims
        self.__subscriptions = dict()

    def subscribe(self, request):
        data = request.json
        subscription = data['subscription']
        message = data.get('message', 'Hello from Flask!')

        token = get_raw_token(request.headers.get('Authorization'))
        print(token)
        if token is not None:
            self.__subscriptions[token] = subscription

        notification = {
            "title": "Angular App",
            "body": message,
            "icon": "/assets/images/success.png",
            "badge": "/assets/images/success.png"
        }

        self.send_push_notification(
            notification,
            subscription
        )

    def send_push_notification(self, notification, subscription):
        webpush(
            subscription_info=subscription,
            data=
            json.dumps(
                {
                    "notification": notification
                }
            ),
            vapid_private_key=self.__VAPID_PRIVATE_KEY,
            vapid_claims={
                "sub": "mailto:"+self.__VAPID_CLAIMS
            },
            ttl=1
        )

    def get_subscription(self, token):
        return self.__subscriptions[token] if token in self.__subscriptions else None

    def set_private_key(self, private_key):
        self.__VAPID_PRIVATE_KEY = private_key

    def set_claims(self, claims):
        self.__VAPID_CLAIMS = claims