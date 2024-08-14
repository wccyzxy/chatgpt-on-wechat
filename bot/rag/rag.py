import requests


class RAG:
    def __init__(self):
        self.base_url = 'http://127.0.0.1:8000'

    def query(self, query):
        url = f"{self.base_url}/api/query"

        payload = {
            'query': query
        }
        response = requests.post(url, json=payload)
        resp_json = response.json()
        if len(resp_json['documents']) > 0:
            return resp_json['documents']
        return []

    def queryAnswer(self, query):
        url = f"{self.base_url}/api/query/answer"

        payload = {
            'query': query
        }
        response = requests.post(url, json=payload)
        resp_json = response.json()
        return resp_json['system']



if __name__ == '__main__':
    rag = RAG()
    print(rag.query("你好"))
