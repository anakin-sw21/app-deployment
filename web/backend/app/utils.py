import os
import cv2
import copy
import gzip
import json
import gridfs
import base64
import pickle
import inspect
import hashlib
import tempfile
import numpy as np
from datetime import datetime
from bson import ObjectId
from typing import List, Union
from dotenv import load_dotenv
from pymongo import MongoClient
from ultralytics.utils.plotting import Colors
from typing import get_type_hints, get_origin, get_args
from werkzeug.datastructures.file_storage import FileStorage
from web.backend.app.store import in_memory_store

def convert_objectid_to_str(obj):
    if isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, dict):
        return {k if k!='_id' else 'id': convert_objectid_to_str(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_objectid_to_str(item) for item in obj]
    else:
        return obj

def get_raw_token(auth_header):
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.split(" ")[1]
    return None


def get_current_datetime():
    return datetime.now()

def string_to_datetime(date_string: str)->datetime:
    return datetime.strptime(date_string, "%a, %d %b %Y %H:%M:%S GMT")

def obj_prediction_encryption(obj_results):
    for result in obj_results:
        success, buffer = cv2.imencode(".jpg", result.orig_img)  # or ".png", ".webp", etc.
        if success:
            result.orig_img = buffer.tobytes()
    return gzip.compress(pickle.dumps(obj_results))

def obj_prediction_decryption(file):
    obj_results = pickle.loads(gzip.decompress(file.read()))
    for result in obj_results:
        result.orig_img = cv2.imdecode(np.frombuffer(result.orig_img, np.uint8), cv2.IMREAD_COLOR)
    return obj_results
# def obj_prediction_decryption(base64_encoded):
#     return pickle.loads(base64.b64decode(base64_encoded))

def parse_image_from_bytes(image_bytes:bytes):
    return cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)

def parse_image_from_file(image_file:FileStorage):
    return parse_image_from_bytes(image_file.read())

def parse_video_from_frames(frames, fps=20, output_format=".mp4"):
    if not frames:
        return None, "No frames to write."

    height, width, _ = frames[0].shape
    fourcc = cv2.VideoWriter_fourcc(*'H264')  # Or 'XVID', 'avc1', etc.

    with tempfile.NamedTemporaryFile(delete=False, suffix=output_format) as tmp_video:
        video_path = tmp_video.name

    out = cv2.VideoWriter(video_path, fourcc, fps, (width, height))

    for frame in frames:
        out.write(frame)

    out.release()
    return video_path, "video"

def parse_video_from_bytes(video_bytes:bytes):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_video:
        temp_video.write(video_bytes)
        temp_video_path = temp_video.name

    # return temp_video_path, "video"

    # Now use OpenCV to read video frames
    cap = cv2.VideoCapture(temp_video_path)

    if not cap.isOpened():
        return 'Could not open video'

    frames = []

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frames.append(frame)

    fps = cap.get(cv2.CAP_PROP_FPS)

    cap.release()

    return frames, fps, "video"

def parse_video_from_file(video_file:FileStorage):
    return parse_video_from_bytes(video_file.read())

def parse_file(file:FileStorage):
    content_type = file.content_type
    if content_type.startswith("image") and content_type!= "image/gif":
        return parse_image_from_file(file), 1, "image"
    elif content_type.startswith("video") or content_type== "image/gif":
        return parse_video_from_file(file)

def parse_image(serialized_image:str):
    image_bytes = base64.b64decode(serialized_image)
    return parse_image_from_bytes(image_bytes)

def unparse_image(image):
    _, buffer = cv2.imencode('.jpg', image)
    return base64.b64encode(buffer.tobytes()).decode('utf-8')

def unparse_video(frames, fps=30):
    if not frames:
        return b''

    height, width, _ = frames[0].shape
    fourcc = cv2.VideoWriter_fourcc(*'H264')
    # Create temporary file to write video
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_video:
        video_path = temp_video.name

    out = cv2.VideoWriter(video_path, fourcc, fps, (width, height))

    for frame in frames:
        out.write(frame)

    out.release()
    # Read the written video file back as bytes
    with open(video_path, 'rb') as f:
        video_bytes = f.read()

    return base64.b64encode(video_bytes).decode('utf-8')

def get_bounding_boxes(results, index=None):
    return_value = []
    # print(len(results))
    for result in results:
        # plot_image_yolo(result, image, file)
        current_value = []
        if index and not "object_count" in in_memory_store[index]:
            in_memory_store[index]["object_count"] = [0 for _ in range(len(result.names))]
        for box in result.boxes:
            class_id = int(box.cls[0].item())
            if index:
                in_memory_store[index]["object_count"][class_id] +=1
            color = rgb_to_hex(Colors()(class_id))
            current_value.append([result.names[class_id], color, box.conf[0].item(),
                                [box.xywhn[0][0].item(), box.xywhn[0][1].item(), box.xywhn[0][2].item(),
                                 box.xywhn[0][3].item()]])
        return_value.append(current_value)
    return return_value


def delete_bboxes_images(indexes):
    if len(indexes) >= 1:
        index_predict = indexes.pop(0)
        results = copy.deepcopy(in_memory_store[index_predict]["results"])
        fps = in_memory_store[index_predict]["fps"] if "fps" in in_memory_store[index_predict] else 1
        in_memory_store[index_predict]["deleted_bboxes"] = indexes

        for i, result in enumerate(results):
            frame_indexes = [y for x, y in indexes if x == i]
            result.boxes = result.boxes[[j for j in range(len(result.boxes)) if j not in frame_indexes]]
            # print(result.boxes)
            in_memory_store[index_predict]["object_count"] = [0 for _ in range(len(result.names))]
            for box in result.boxes:
                class_id = int(box.cls[0].item())
                in_memory_store[index_predict]["object_count"][class_id] = \
                in_memory_store[index_predict]["object_count"][class_id] + 1

        if "fps" in in_memory_store[index_predict]:
            # Draw results on video
            new_frames = []
            for result in results:
                new_frames.append(result.plot())
            media = unparse_video(new_frames, fps)
        else:
            # Draw results on image
            annotated_frame = results[0].plot()
            media = unparse_image(annotated_frame)

        return {"image": media}


def get_bounding_boxes_o(index, results):
    returnValue = []
    for result in results:
        if not "object_count" in in_memory_store[index]:
            in_memory_store[index]["object_count"] = [0 for _ in range(len(result.names))]
        for box in result.boxes:
            class_id = int(box.cls[0].item())
            in_memory_store[index]["object_count"][class_id] = in_memory_store[index]["object_count"][
                                                                   class_id] + 1
            color = rgb_to_hex(Colors()(class_id))
            returnValue.append([result.names[class_id], color, box.conf[0].item(),
                                [box.xywhn[0][0].item(), box.xywhn[0][1].item(), box.xywhn[0][2].item(),
                                 box.xywhn[0][3].item()]])
    return returnValue


def delete_bboxes_images_o(indexes):
    if len(indexes) >= 1:
        index_predict = indexes.pop(0)
        results = copy.deepcopy(in_memory_store[index_predict]["results"])
        in_memory_store[index_predict]["deleted_bboxes"] = indexes

        for result in results:
            result.boxes = result.boxes[[i for i in range(len(result.boxes)) if i not in indexes]]
            in_memory_store[index_predict]["object_count"] = [0 for _ in range(len(result.names))]
            for box in result.boxes:
                class_id = int(box.cls[0].item())
                in_memory_store[index_predict]["object_count"][class_id] = \
                in_memory_store[index_predict]["object_count"][class_id] + 1

        # Draw results on image
        annotated_frame = results[0].plot()
        image = unparse_image(annotated_frame)

        return {"image": image}

def cast_param(cls, param_name, value):
    hints = get_type_hints(cls.original_init)
    expected_type = hints.get(param_name)

    if expected_type is None:
        return value

    origin = get_origin(expected_type)
    args = get_args(expected_type)

    # Try JSON or datetime parsing if value is a string
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            try:
                value = string_to_datetime(value)
            except ValueError:
                pass  # fallback to raw string if no parse works

    try:
        # Handle List[int], List[str], etc.
        if origin is list and args:
            return [args[0](item) for item in value]

        # Handle Dict[str, int], etc.
        elif origin is dict and args:
            return {args[0](k): args[1](v) for k, v in value.items()}

        # Handle Union types (e.g. Optional[int])
        elif origin is Union and args:
            for arg in args:
                try:
                    return cast_param_for_type(arg, value)
                except Exception:
                    continue
            raise ValueError(f"Cannot cast {value} to any of {args}")

        # Handle custom classes with original_init
        elif isinstance(value, dict) and hasattr(expected_type, 'original_init'):
            if "id" in value:
                value["_id"] = value.pop("id")
            return expected_type(**value)

        # Fallback: try direct casting if not already correct type
        if isinstance(value, expected_type):
            return value
        return expected_type(value)


    except Exception as e:
        raise ValueError(f"Cannot cast {value} to {expected_type}: {e}")

# Helper for Union casting
def cast_param_for_type(expected_type, value):
    origin = get_origin(expected_type)
    args = get_args(expected_type)

    if origin is list and args:
        return [args[0](item) for item in value]
    elif origin is dict and args:
        return {args[0](k): args[1](v) for k, v in value.items()}
    elif isinstance(value, dict) and hasattr(expected_type, 'original_init'):
        return expected_type(**value)
    elif expected_type == datetime and isinstance(value, str):
        return string_to_datetime(value)
    else:
        return expected_type(value)

def get_db_instance(database_name):
    load_dotenv()
    uri = os.getenv("API_KEY")
    client = MongoClient(uri)
    db = client[database_name]
    fs = gridfs.GridFS(db, "crimes.predictions")
    return db, fs

def get_var(var: str):
    load_dotenv()
    return os.getenv(var.upper())

def fixIDMongo(data: dict) -> dict:
    for index in ["id", "nic"]:
        if index in data:
            data["_id"] = data[index]
            del data[index]
            break
    return data

def encode_image(file):
    return base64.b64encode(file.read()).decode('utf-8')

def rgb_to_hex(t):
    r = max(0, min(t[0], 255))
    g = max(0, min(t[1], 255))
    b = max(0, min(t[2], 255))

    ## Convert to hexadecimal and remove '0x' prefix
    hex_color = '#{:02X}{:02X}{:02X}'.format(r, g, b)
    return hex_color

def get_required_fields(cls, exclude: List[str] = None, _id:bool=False):
    exclude = exclude or []
    sig = inspect.signature(cls.original_init)
    return [param for param in sig.parameters if (param != 'self' and (_id or param!="_id")) and param not in exclude]

def get_obj_element_names(obj, exclude_methods=False, exclude_attributes=False):
    result = []
    for name in dir(obj):
        if name.startswith('__') and name.endswith('__'):
            continue  # Skip dunder methods

        attr = getattr(obj, name)

        if exclude_methods and callable(attr):
            continue
        if exclude_attributes and not callable(attr):
            continue

        result.append(name)

    return result

def encrypt_string(hash_string):
    sha_signature = \
        hashlib.sha256(hash_string.encode()).hexdigest()
    return sha_signature

def enforce_types(cls):
    def wrap_function(func):
        sig = inspect.signature(func)
        annotations = get_type_hints(func)

        def wrapper(*args, **kwargs):
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()

            for name, value in bound.arguments.items():
                if name not in annotations:
                    continue

                expected_type = annotations[name]
                origin = get_origin(expected_type)

                if origin is Union:
                    # Handle Union types (e.g., Union[int, str])
                    if not any(isinstance(value, arg) for arg in get_args(expected_type)):
                        raise TypeError(
                            f"Argument '{name}' must be one of {get_args(expected_type)}, got {type(value).__name__}"
                        )
                elif origin:
                    # Handle generics like List[int], Dict[str, int]
                    if not isinstance(value, origin):
                        raise TypeError(
                            f"Argument '{name}' must be of type {origin.__name__}, got {type(value).__name__}"
                        )
                else:
                    if not isinstance(value, expected_type):
                        raise TypeError(
                            f"Argument '{name}' must be of type {expected_type.__name__}, got {type(value).__name__}"
                        )

            result = func(*args, **kwargs)

            # Check return type
            if 'return' in annotations:
                expected_return = annotations['return']
                origin = get_origin(expected_return)

                if origin is Union:
                    if not any(isinstance(result, arg) for arg in get_args(expected_return)):
                        raise TypeError(
                            f"Return value must be one of {get_args(expected_return)}, got {type(result).__name__}"
                        )
                elif origin:
                    if not isinstance(result, origin):
                        raise TypeError(
                            f"Return value must be of type {origin.__name__}, got {type(result).__name__}"
                        )
                else:
                    if not isinstance(result, expected_return):
                        raise TypeError(
                            f"Return value must be of type {expected_return.__name__}, got {type(result).__name__}"
                        )

            return result

        return wrapper

    for attr_name, attr_value in cls.__dict__.items():
        if callable(attr_value) and not attr_name.startswith("__"):
            setattr(cls, attr_name, wrap_function(attr_value))

    if hasattr(cls, "__init__"):
        cls.original_init = cls.__init__
        cls.__init__ = wrap_function(cls.__init__)

    return cls
