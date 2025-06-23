import importlib
from abc import ABC
import datetime
from typing import List

from bson import ObjectId
from gridfs.synchronous.grid_file import GridFS
from pymongo.synchronous.database import Database
from web.backend.app.utils import enforce_types, get_required_fields, convert_objectid_to_str


class DefaultService(ABC):
    def __init__(self, table:Database, index_str: str = None):
        if type(self) is DefaultService:
            raise TypeError("Base is not instantiable directly")
        self._table = table
        self._name = None
        self._cls = None
        self._index_str = index_str

    def create_index(self, index_name: str = None):
        index_name = index_name or self._table["index_name"]
        if index_name is not None:
            self._table["users"].create_index({index_name: 1}, unique=True)

    def create_instance(self, *args:tuple, **kwargs: dict):
        instance = self._cls(*args, **kwargs)
        self._table[self._name.lower()].insert_one(instance.__dict__)

    def create_instance_from_dict(self, data:dict, required_fields:List[str]):
        if all(field in data for field in required_fields):
            self._table[self._name.lower()].insert_one(data)

    def update_instance_from_dict(self, data:dict, unset:dict = None):
        _id = data["_id"]
        superuser_id = data["superuser"]["_id"]
        data["timestamp_edited"] = datetime.datetime.now()

        return self._table[self._name.lower()].update_one({"_id": _id, "superuser._id": superuser_id}, {"$set": data, "$unset": unset})

    def find_instance_by_field(self, filter:dict, *args:tuple, **kwargs: dict):
        # self._table[self._name.lower()].update_many({}, {"$set": {"superuser_id": 12345}})
        # self._table["superusers"].update_many({}, {"$rename" : {"name": "first_name"}})
        # self._table["users"].update_many({}, {"$set": {"last_name": "", "phone" : "0"}})
        # self._table["superusers"].update_many({}, {"$set": {"last_name": "", "phone" : 0}})

        return self._table[self._name.lower()].find_one(filter, *args, **kwargs)

        # filter = dict()
        # or_conditions = []
        # for element in query:
        #     if element=="_id":
        #         _id = query["_id"]
        #         or_conditions.append({"_id": _id})
        #         or_conditions.append({"_id": ObjectId(_id)})
        #     else:
        #         filter[element] = query[element]
        #
        # filter["$or"] = or_conditions
    def delete_instance_by_fields(self, query):
        return self._table[self._name.lower()].delete_one(
            query
        )
    def delete_instances_by_fields(self, query):
        return self._table[self._name.lower()].delete_many(
            query
        )

    def is_valid_instance(self, instance:dict):
        for field in instance:
            if field.endswith("_id") and field!="_id":
                table_name = field[:field.rfind("_id")]
                if self._table[table_name + "s"].find_one({"_id": instance[field]}) is None:
                    return False
        return True

    def is_valid_field(self, field, instance:dict):
        query = dict()
        if isinstance(field, list):
            for elt in field:
                query[elt] = instance[elt]
        else:
            query[field] = instance[field]

        return self._table[self._name.lower()].find_one(query) is None

    from bson import ObjectId

    def is_valid_objectid(self, id_str):
        try:
            ObjectId(id_str)
            return True
        except:
            return False

    def find_one(self, query, fs:GridFS=None, filter: dict = None):

        # Add int _id if possible
        try:
            if "_id" in query:
                query["_id"] = int(query["_id"])
        except ValueError:
            pass
        or_conditions = [query]
        id = query["_id"]

        # Add ObjectId _id only if valid
        if isinstance(id, str) and self.is_valid_objectid(id):
            or_conditions.append({"_id": ObjectId(id)})

        if filter is None:
            obj = self._table[self._name.lower()].find_one(
                {"$or": or_conditions}
            )
        else:
            obj = self._table[self._name.lower()].find_one(
                {"$or": or_conditions},
                filter
            )
        obj = convert_objectid_to_str(obj)
        return obj

    def find_all(self, query:dict = None, projection:dict = None):
        predictions_cursor = list(self._table[self._name.lower()].find(query, projection))

        predictions = []
        for p in predictions_cursor:

            self._table["crimes"].update_one({"_id": ObjectId("682fb4c0288a7883b0be962b")}, {"$unset": {"crime_id": ""}, "$push": {"predictions": p}})
            if "_id" in p:
                p["_id"] = str(p["_id"])
            #     p["id"] = str(p["_id"])
            #     del p["_id"]
            if "crime_id" in p:
                p["crime_id"] = str(p["crime_id"])


            predictions.append(p)

        return predictions

    def find_all_aggregate(
            self,
            query: dict = None,
            projection: dict = None,
            column: str = "photo",
            sort_by: str = "_id",
            sort_order: str = None,
            added_column_name: str = "",
            page : int = 1,
            page_size = 1,
            search_value: str = None,
            or_columns : List[str] = None,
            pipeline=None,
        ) -> dict:

        if pipeline is None:
            pipeline = []

        if or_columns is None:
            or_columns = []

        # Step 1: Unset the element at index 2
        if query:
            pipeline.insert(0, {"$match": query})

        pipeline.append({
            "$lookup": {
                "from": "crimes.predictions.files",
                "localField": "_id",
                "foreignField": "_id",
                "as": "matched_file"
            }
        })

        pipeline.append({
            "$addFields": {
                column: {
                    "$cond": [
                        {
                            "$or": [
                                {"$ifNull": [f"${column}", False]},
                                {"$gt": [{"$size": "$matched_file"}, 0]}
                            ]
                        },
                        "true",
                        "false"
                    ]
                }
            }
        })

        if added_column_name!="":
            pipeline.append({
                "$set": {
                    added_column_name: f"${column}"
                }
            })

            pipeline.append({
                "$unset": column
            })


        pipeline+=[
            {
                "$set": {
                    "timestamp_edited": {
                        "$ifNull": ["$timestamp_edited", "$timestamp_created"]
                    }
                }
            },
            {
                "$addFields": {
                    "_id_str": {"$toString": "$_id"},
                    "timestamp_created_fmt": {
                        "$dateToString": {
                            "format": "%d/%m/%Y %H:%M:%S",
                            "date": "$timestamp_created"
                        }
                    },
                    "timestamp_edited_fmt": {
                        "$dateToString": {
                            "format": "%d/%m/%Y %H:%M:%S",
                            "date": "$timestamp_edited"
                        }
                    }
                }
            }]

        or_conditions = [
            {"_id_str": {"$regex" : search_value, "$options": "i"}}
        ]

        for column in or_columns:
            or_conditions.append(
                {column: {"$regex": search_value, "$options": "i"}}
            )

        or_conditions+=[
            {"timestamp_edited_fmt": {"$regex" : search_value, "$options": "i"}},
            {"timestamp_created_fmt": {"$regex" : search_value, "$options": "i"}},
        ]

        if search_value is not None:
            pipeline += [{
                "$match" : {
                    "$or" : or_conditions
                }
            }]

        pipeline+=[{
                "$unset": [
                    "_id_str",
                    "timestamp_edited_fmt",
                    "timestamp_created_fmt"
                ]
            }
        ]

        if projection and projection!={}:
            projection.update({"matched_file": 0})
        else:
            projection = {"matched_file": 0}
        pipeline.append({"$project": projection})

        sort_order = -1 if sort_order=="-1" else 1
        sort = {sort_by: sort_order} if sort_by!="first_name" else {"first_name": sort_order, "last_name": sort_order}

        if page_size is not None:
            page_size = int(page_size) * 5
            pipeline += [
                {
                    "$facet": {
                        "data": [
                            {"$sort": sort},
                            {"$skip": (page - 1) * page_size},
                            {"$limit": page_size}
                        ],
                        "totalCount": [
                            {"$count": "count"}
                        ]
                    }
                },
            ]
        else:
            pipeline += [
                {
                    "$facet": {
                        "data": [
                            {"$sort": sort}
                        ],
                        "totalCount": [
                            {"$count": "count"}
                        ]
                    }
                },
            ]


        # self._table["crimes"].update_many({}, {"$unset": {"superuser_id": ""}})

        query_execution = list(self._table[self._name.lower()].aggregate(pipeline, collation={'locale': 'en', 'strength': 1}))[0]
        records_cursor = query_execution["data"]
        total_count = query_execution["totalCount"][0]["count"] if query_execution["totalCount"] else 0
        max_pages = (total_count + page_size - 1) // page_size if page_size is not None else 1
        sizes = (total_count - 1)// 5
        records = []

        for p in records_cursor:
            p = convert_objectid_to_str(p)
            records.append(p)

        return {"results" : records, "page" : page, "max_pages" : max_pages, "sizes" : sizes}

        #
        # users = self._table["users"]
        #
        # # Clear old embedded data to avoid duplication (optional)
        # users.update_many({}, {"$set": {"crimes": []}})
        #
        # # Iterate through all crimes
        # for crime in records:
        #     crime_id = crime["id"]
        #     crime_name = crime["name"]
        #
        #     for team_member in crime.get("team", []):
        #         id = team_member["id"]
        #
        #         # Create the embedded crime object
        #         crime_obj = {
        #             "_id": crime_id,
        #             "name": crime_name
        #         }
        #
        #         if "photo" in crime:
        #             crime_obj["photo"] = "true"
        #         else:
        #             crime_obj["photo"] = "false"
        #         crime_obj["timestamp_created"] = crime["timestamp_created"]
        #
        #         if "timestamp_edited" in crime:
        #             crime_obj["timestamp_edited"] = crime["timestamp_edited"]
        #         if "description" in crime:
        #             crime_obj["description"] = crime["description"]
        #
        #         # Add crime to the course's enrolled_students array
        #         users.update_one(
        #             {"_id": id},
        #             {"$addToSet": {"crimes": crime_obj}}  # prevents duplicates
        #         )


        # user = self._table["superusers"].find_one({"_id": 12345678}, {"password" : 0, "timestamp_edited" : 0, "timestamp_created" : 0})
        # pp = [
        #     {
        #         "$lookup": {
        #             "from": "superusers",
        #             "localField": "superuser_id",
        #             "foreignField": "_id",
        #             "as": "superuser"
        #         }
        #     },
        #     {
        #         "$unwind": {
        #             "path": "$superuser",
        #             "preserveNullAndEmptyArrays": True  # Keep users without matching superuser
        #         }
        #     },
        #     {
        #         "$merge": {
        #             "into": "users",  # Overwrite existing users collection with enriched docs
        #             "whenMatched": "merge",
        #             "whenNotMatched": "discard"
        #         }
        #     }
        # ]
        # pp = [
        #     {
        #         "$unset": "superuser.password"
        #     },
        #     {
        #         "$unset": "superuser.timestamp_created"
        #     },
        #     {
        #         "$unset": "superuser.timestamp_edited"
        #     },
        #     {
        #         "$merge": {
        #             "into": "users",  # Overwrite existing users collection with enriched docs
        #             "whenMatched": "merge",
        #             "whenNotMatched": "discard"
        #         }
        #     }
        # ]
        # self._table["users"].aggregate(pp)