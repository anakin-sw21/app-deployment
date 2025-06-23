# works with both python 2 and 3
from __future__ import print_function

import africastalking

class SMS:
    def __init__(self):
        self.username = "sandbox"
        self.api_key = "atsk_6aa6c0b11b64fc256015f2dcec362709e3746781b0336d8d0416febecf4c9b0a6e1ca359"

        # Initialize the SDK
        africastalking.initialize(self.username, self.api_key)

        # Get the SMS service
        self.sms = africastalking.SMS

    def send(self):
            # Set the numbers you want to send to in international format
            recipients = ["+21654942449"]

            # Set your message
            message = "Hello Mejd"

            # Set your shortCode or senderId
            sender = "shortCode or senderId"
            try:
                response = self.sms.send(message, recipients, sender)
                print (response)
            except Exception as e:
                print ('Encountered an error while sending: %s' % str(e))

if __name__ == '__main__':
    SMS().send()