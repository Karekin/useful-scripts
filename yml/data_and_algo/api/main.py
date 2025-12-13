from fastapi import FastAPI
from trino.dbapi import connect
from pydantic import BaseModel

app = FastAPI()

class QueryRequest(BaseModel):
    query: str

@app.get("/")
def read_root():
    return {"Hello": "World", "Service": "Data Platform API"}

@app.get("/tables")
def list_tables():
    conn = connect(
        host="trino",
        port=8080,
        user="admin",
        catalog="demo",
        schema="default",
    )
    cur = conn.cursor()
    cur.execute("SHOW TABLES FROM demo.default")
    rows = cur.fetchall()
    return {"tables": rows}

@app.post("/query")
def execute_query(request: QueryRequest):
    conn = connect(
        host="trino",
        port=8080,
        user="admin",
        catalog="demo",
        schema="default",
    )
    cur = conn.cursor()
    cur.execute(request.query)
    rows = cur.fetchall()
    return {"results": rows}

