from pymongo import MongoClient
import os

# MongoDBの接続情報を環境変数から取得
MONGO_URI = os.getenv("MONGO_URI")

# MongoDBに接続
client = MongoClient(MONGO_URI)
db = client["orsa_db"]  # データベース名
user_profiles = db["user_profiles"]  # コレクション
