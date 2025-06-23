import json
from queue import Queue
import cv2
import secrets
import threading
from pywebpush import webpush, WebPushException
from ultralytics import YOLO
from werkzeug.datastructures.file_storage import FileStorage

from web.backend.app.services.notification_service import NotificationService
from web.backend.app.store import config, in_memory_store
from web.backend.app.utils import enforce_types, get_bounding_boxes, unparse_image, parse_image, parse_file, \
    unparse_video


@enforce_types
class MLService:
    def __init__(self):
        self.__model_path = config["model"]["path"]
        self.__model = YOLO(self.__model_path, verbose=False)
        self.queue = Queue()
        self.running = True
        threading.Thread(target=self.generate_prediction, daemon=True).start()

    def predict(self, file:FileStorage, index:str):
        obj_to_predict, fps, media_type = parse_file(file)

        results = self.__model(obj_to_predict)
        if not index in in_memory_store:
            index = secrets.token_hex(12)

        in_memory_store[index] = {"results": results}

        return_value = get_bounding_boxes(results, index)

        if media_type == "image":
            # Draw results on image
            annotated_frame = results[0].plot()
            media = [unparse_image(annotated_frame)]
        elif media_type == "video":
            new_frames = []
            in_memory_store[index]["fps"] = fps
            for result in results:
                new_frames.append(result.plot())
            media = unparse_video(new_frames, fps)
            print(f"Frame Per Second: {fps}")
        else:
            return {"error": "unrecognized media type"}
        return {"image": media, "results": return_value, "index": index, "fps" : fps}

    def generate_prediction(self):
        while self.running:
            item = self.queue.get()
            if item is None:
                continue
            frame_unparsed, language, subscription, notif_service, callback = item
            frame = parse_image(frame_unparsed)
            results = self.__model(frame, verbose=False)
            message_warning = "detected\nCoordinates"
            title = "Crime Object Detected!!"
            if language == "fr":
                title = "Objet de Crime Détecté!!"
                message_warning = "détecté(e)\nCoordonnées"
                results[0].names = {0: 'Sang', 1: 'Empreinte', 2: 'Verre', 3: 'Marteau', 4: 'Pistolet', 5: 'Corps Humain',
                            6: 'Cheveux Humain', 7: 'Mains Humain', 8: 'Couteau', 9: 'Fusil de chasse',
                            10: 'Empreinte de Chaussure'}

            frame_b64 = unparse_image(results[0].plot())
            return_value = get_bounding_boxes(results)
            for box in results[0].boxes:
                index = int(box.cls[0].item())
                if index in [0, 3, 4, 8, 9]:
                    notification = {
                        "title": title,
                        "body": f"{results[0].names[index]} {message_warning} : ({box.xywhn[0][0].item()}, {box.xywhn[0][1].item()}, {box.xywhn[0][2].item()}, {box.xywhn[0][3].item()})",
                        "icon": f"/assets/icons/crime_object_{index}.png",
                        "tag" : results[0].names[index]
                    }

                    threading.Thread(
                        target=notif_service.send_push_notification,
                        args=(
                            notification,
                            subscription
                        )
                    ).start()
            # Build metadata
            data = {
                "image": 'data:image/jpeg;base64,'+frame_b64,
                "results": return_value,
            }
            callback(data, results)

    def generate_prediction_rt(self, frame_unparsed, language, subscription, notif_service : NotificationService, callback):
        self.queue.put((frame_unparsed, language, subscription, notif_service, callback))
