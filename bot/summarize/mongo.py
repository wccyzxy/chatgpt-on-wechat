import pymongo

class MongoDB:
    def __init__(self, host='localhost', port=27017, db_name='mydb'):
        # 连接mongoDB
        self.client = pymongo.MongoClient(host=host, port=port)
        # 选择数据库
        self.db = self.client[db_name]

    def insert_one(self, collection_name, data):
        # 插入数据
        self.db[collection_name].insert_one(data)

    def find_one(self, collection_name, query):
        # 查询数据
        return self.db[collection_name].find_one(query)

    def find_many(self, collection_name, query):
        # 查询多条数据
        return self.db[collection_name].find(query)

    def update_one(self, collection_name, query, data):
        # 更新数据
        self.db[collection_name].update_one(query, {'$set': data})

    def delete_one(self, collection_name, query):
        # 删除数据
        self.db[collection_name].delete_one(query)

    def close(self):
        # 关闭连接
        self.client.close()