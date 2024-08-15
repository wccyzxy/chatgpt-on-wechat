import sqlite3
from sqlite3 import Error


class SQLiteDB:
    def __init__(self, db_file):
        """ 初始化数据库连接 """
        self.connection = None
        try:
            self.connection = sqlite3.connect(db_file)
            self.cursor = self.connection.cursor()
        except Error as e:
            print(e)

    def execute(self, query, parameters=None):
        """ 执行 SQL 查询 """
        try:
            if parameters is None:
                self.cursor.execute(query)
            else:
                self.cursor.execute(query, parameters)
            return True
        except Error as e:
            print(e)
            return False

    def fetchall(self):
        """ 获取所有查询结果 """
        return self.cursor.fetchall()

    def fetchone(self):
        """ 获取单个查询结果 """
        return self.cursor.fetchone()

    def commit(self):
        """ 提交事务 """
        self.connection.commit()

    def close(self):
        """ 关闭数据库连接 """
        if self.connection:
            self.connection.close()


# 使用示例
if __name__ == "__main__":
    # 创建数据库实例
    db = SQLiteDB('example.db')

    # 创建表
    create_table_query = """
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        completed BOOLEAN NOT NULL
    );
    """
    db.execute(create_table_query)

    # 插入数据
    insert_data_query = "INSERT INTO tasks (name, description, completed) VALUES (?, ?, ?)"
    task_data = ("Task 1", "This is the first task", 0)
    db.execute(insert_data_query, task_data)
    db.commit()

    # 查询数据
    select_data_query = "SELECT * FROM tasks"
    db.execute(select_data_query)
    rows = db.fetchall()
    for row in rows:
        print(row)

    # 关闭连接
    db.close()