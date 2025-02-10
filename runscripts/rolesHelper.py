from dal import db_utils

# Set up the Mongo connection.
mongo_client = db_utils.create_mongo_client()
licco_db = mongo_client["lineconfigdb"]

# create admins
licco_db["roles"].insert_one({
    "app": "Licco", 
    "name": "admin",
    "privileges" : [
        "read",
        "write",
        "edit",
        "approve"
    ],
    "players" : [
        "uid:xxxxxx"
    ]
    })

# create supperapprovers
licco_db["roles"].insert_one({
    "app" : "Licco",
    "name" : "superapprover",
    "privileges" : [
        "read",
        "approve"
    ],
    "players" : [
        "uid:yyyyy"
    ]
    })


