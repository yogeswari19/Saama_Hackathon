import snowflake.connector
import os
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
import json
from prompt_func import prompt_fun
from plyer import notification
import requests

from email.message import EmailMessage
from typing import TypedDict, List, Dict, Optional
import datetime
import snowflake.connector
import smtplib
from langgraph.graph import StateGraph, END
import getpass
load_dotenv()

USER_EMAIL_MAP = {
    "YOGESWARI": "yogeswariyrsk@gmail.com",
    "BOB": "bob@example.com",
}

# 1️⃣ Define TypedDict-based State

class QueryRecord(TypedDict):
    QUERY_ID: str
    QUERY_TEXT: str
    START_TIME: datetime.datetime
    USER_NAME: str
    EXECUTION_STATUS: str

class QueryAnalysis(TypedDict):
    query: QueryRecord
    analysis: str

class Notification(TypedDict):
    user: str
    query_id: str
    message: str

class State(TypedDict, total=False):
    running_queries: List[QueryRecord]
    long_running_queries: List[QueryRecord]
    analyses: List[QueryAnalysis]
    flagged_queries: List[QueryAnalysis]
    notifications_sent: List[Notification]

# 2️⃣ Node: Fetch running queries from Snowflake

def fetch_queries(state: State) -> State:
    conn = snowflake.connector.connect(
        user='YOGESWARI',
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        warehouse='COMPUTE_WH',
        database='HEALTHCARE',
        schema='CLINICAL',
        role='ACCOUNTADMIN'
    )
    cur = conn.cursor()
    query = """
    SELECT QUERY_ID, QUERY_TEXT, START_TIME, USER_NAME, EXECUTION_STATUS
    FROM TABLE(INFORMATION_SCHEMA.QUERY_HISTORY())
    WHERE EXECUTION_STATUS = 'RUNNING'
    """
    cur.execute(query)
    rows = cur.fetchall()
    running = [
        {
            "QUERY_ID": row[0],
            "QUERY_TEXT": row[1],
            "START_TIME": row[2],
            "USER_NAME": row[3],
            "EXECUTION_STATUS": row[4]
        }
        for row in rows
    ]
    state["running_queries"] = running
    return state

# 3️⃣ Node: Filter long-running queries (>15 min)

seen_file = "last_seen.json"
if not os.path.exists(seen_file):
    with open(seen_file, "w") as f:
        json.dump([], f)

def filter_long_running(state: State) -> State:
   
    now = datetime.datetime.now(datetime.timezone.utc)

    if os.path.exists(seen_file):
        with open(seen_file, "r") as f:
            seen_ids = set(json.load(f))

    fresh_long_running = []
    for q in state.get("running_queries", []):
        if q["EXECUTION_STATUS"] == "RUNNING":
            runtime = now - q["START_TIME"]
            if runtime.total_seconds() > 10:  # 15 minutes
                if q["QUERY_ID"] not in seen_ids:
                    fresh_long_running.append(q)

    # Update the last seen file
    seen_ids.update(q["QUERY_ID"] for q in fresh_long_running)
    with open(seen_file, "w") as f:
        json.dump(list(seen_ids), f)

    state["long_running_queries"] = fresh_long_running
    return state


# 4️⃣ Node: Analyze with LLM

if not os.environ.get("GROQ_API_KEY"):
  os.environ["GROQ_API_KEY"] = getpass.getpass("Enter API key for Groq: ")

llm = init_chat_model("llama-3.1-8b-instant", model_provider="groq")

def analyze_query(state: State) -> State:
    analyses: List[QueryAnalysis] = []
    for query in state.get("long_running_queries", []):
        prompt=prompt_fun(query["QUERY_TEXT"])
        result=llm.invoke(prompt).content
        analyses.append({"query": query, "analysis": result})
    state["analyses"] = analyses
    return state

# 5️⃣ Node: Check for flagged queries

def check_for_issues(state: State) -> State:
    flagged: List[QueryAnalysis] = []
    for a in state.get("analyses", []):
        try:
            # Try to parse the structured JSON at the end of the analysis
            last_line = a["analysis"].strip().splitlines()[-1]
            meta = json.loads(last_line)
            confidence = meta.get("confidence_score", 0)
            issues = meta.get("issues_found", False)
            
            # Flag only if LLM says there are issues AND confidence is reasonably high
            if issues and confidence >= 70:
                flagged.append(a)

        except Exception:
            # Fallback for old behavior: check keywords
            lower = a["analysis"].lower()
            if any(term in lower for term in ["cartesian", "missing join", "select *", "inefficient", "full scan"]):
                flagged.append(a)

    state["flagged_queries"] = flagged
    return state

def send_email(subject:str,body:str,to:str):
    try:
        msg=EmailMessage()
        msg["Subject"]=subject
        msg["From"]=os.getenv("SMTP_SENDER")
        msg["To"]=to

        msg.set_content(body)
        with smtplib.SMTP("smtp.gmail.com",587) as smtp:
            smtp.starttls()
            smtp.login(os.getenv("SMTP_USERNAME"),os.getenv("SMTP_PASSWORD"))
            smtp.send_message(msg)
    except Exception as e:
        print("Email error:",e)



def send_slack_notification(message: str, webhook_url: str):
    payload = {"text": message}
    headers = {"Content-Type": "application/json"}
    response = requests.post(webhook_url, json=payload, headers=headers)
    
    if response.status_code != 200:
        raise ValueError(f"Slack notification failed: {response.status_code}, {response.text}")


# 6️⃣ Node: Notify the user

def notify_user(state: State) -> State:
    notifications: List[Notification] = []
    for item in state.get("flagged_queries", []):
        user = item["query"]["USER_NAME"]
        query_id = item["query"]["QUERY_ID"]
        mail_id=USER_EMAIL_MAP[user]
        print("mail_id",mail_id)
        message = f"""
        🚨 Long-running query flagged for potential issues:
        User: {user}
        Query ID: {query_id}
        Problem: {item['analysis']}
        """
        print("NOTIFY:", message)  # Replace with Slack or email integration
        notifications.append({
            "user": user,
            "query_id": query_id,
            "message": message.strip()
        })
        send_email("Query Alert",message,mail_id)
        
        send_slack_notification(
    "🚨 Query issue detected",
    webhook_url="https://hooks.slack.com/services/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"
)

    state["notifications_sent"] = notifications
    return state

def summarize_results(state: State) -> State:
    total = len(state.get("long_running_queries", []))
    flagged = len(state.get("flagged_queries", []))
    correct = total - flagged

    summary = f"""
    ===== Summary of Query Analysis =====
    🟡 Total long-running queries (>15 min): {total}
    ✅ Queries that appear optimized: {correct}
    ❌ Queries flagged with issues: {flagged}

    ✅ + ❌ = Total: {correct + flagged}
    ======================================
    """
    print(summary.strip())
    return state


# 7️⃣ LangGraph Graph Assembly

graph = StateGraph(State)
graph.add_node("fetch_queries", fetch_queries)
graph.add_node("filter_long_running", filter_long_running)
graph.add_node("analyze_query", analyze_query)
graph.add_node("check_for_issues", check_for_issues)
graph.add_node("notify_user", notify_user)
graph.add_node("summarize_results", summarize_results)

graph.set_entry_point("fetch_queries")
graph.add_edge("fetch_queries", "filter_long_running")
graph.add_edge("filter_long_running", "analyze_query")
graph.add_edge("analyze_query", "check_for_issues")
graph.add_edge("check_for_issues", "notify_user")
graph.add_edge("notify_user", "summarize_results")
graph.add_edge("summarize_results", END)

# 8️⃣ Run It!

app = graph.compile()

# You can invoke it manually or set it on a schedule
output = app.invoke({})
