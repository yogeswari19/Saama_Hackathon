from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
import asyncio
import queue
from main import stream_queues, app as langgraph_app
from langchain.chat_models import init_chat_model
import threading
from db import get_snowflake_connection

app = FastAPI()
templates = Jinja2Templates(directory=".")

# In-memory store for queries for simplicity
queries_store = []




@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "queries": queries_store})

@app.get("/stream/{query_id}")
async def stream(query_id: str):
    if query_id not in stream_queues:
        stream_queues[query_id] = queue.Queue()

    q = stream_queues[query_id]

    async def event_generator():
        while True:
            try:
                data = q.get(timeout=10) # Wait for 10 seconds
                if data == "[DONE]":
                    yield "data: [DONE]\n\n"
                    break
                yield f"data: {data}\n\n"
            except queue.Empty:
                # This allows the connection to stay open if no new data is available
                yield ": keep-alive\n\n"
            await asyncio.sleep(0.1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/queries")
async def get_queries():
    return {"queries": queries_store}

def run_agent(state):
    # This is a simplified way to run your agent's logic.
    # In a real-world scenario, you might want a more robust way to schedule this.
    while True:
        output = langgraph_app.invoke(state)
        # output = langgraph_app.invoke({})
        if output.get("long_running_queries"):
            for query in output["long_running_queries"]:
                # Avoid adding duplicate queries
                if not any(q['QUERY_ID'] == query['QUERY_ID'] for q in queries_store):
                    queries_store.insert(0, query) # Insert at the beginning to show the latest on top
        # Sleep for a while before the next run
        threading.Event().wait(60) # Wait for 60 seconds

@app.on_event("startup")
async def startup_event():
    # Run the agent in a separate thread
    global llm, base_state
    llm = init_chat_model("llama-3.1-8b-instant", model_provider="groq")
    snowflake_conn = get_snowflake_connection()
    base_state = {
        "snowflake_conn": snowflake_conn,
        "llm": llm,
        "running_queries": [],
        "long_running_queries": []
    }
    
    agent_thread = threading.Thread(target=run_agent,args=(base_state,), daemon=True)
    agent_thread.start()
