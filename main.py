import snowflake.connector
import os
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
import json

#KMKM
# conn = snowflake.connector.connect(
#     user='YOGESWARI',
#     password='Sivanesh@245678',
#     account='PTYRWQT-XG16686',
#     warehouse='COMPUTE_WH',
#     database='HEALTHCARE',
#     schema='CLINICAL',
#     role='ACCOUNTADMIN'
# )

# cursor = conn.cursor()

from typing import TypedDict, List, Dict, Optional
import datetime
import snowflake.connector
from langgraph.graph import StateGraph, END
import getpass
load_dotenv()

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
        password='Sivanesh@245678',
        account='PTYRWQT-XG16686',
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
            if runtime.total_seconds() > 20:  # 15 minutes
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
        prompt = f"""
        You're an SQL expert in optimizing the queries and finding out the incorrect 
        usages of joins or filters in the queries. You'll be provided with queries that 
        are long running for more than 15 mins in snowflake. You have to analyze and identify 
        the performance issues. If the query is well-written and does not contain any clear 
        inefficiencies, you should conclude that the query is likely slow due to large data volume, 
        and no optimization is needed.

        The following are the factors to be considered for performance issues.

        - Cartesian products
        - Missing or incorrect JOINs
        - SELECT * usage
        - Lack of filters or WHERE clause

        Only respond with a performance issue **if** you find one of these problems based on the 
        SQL query. 
        If the query does **not** suffer from any of the above issues, reply:
        > "✅ The query appears well-structured. The long execution time is likely due to 
        the volume of data processed. No optimization needed."

        SQL: ```{query['QUERY_TEXT']}```


        The following are the DDLs of the tables
        present in Database 'Healthcare' and schema 'Clinical'.

        CREATE TABLE Patients (
            patient_id STRING PRIMARY KEY,
            first_name STRING,
            last_name STRING,
            dob DATE,
            gender STRING,
            phone STRING,
            email STRING,
            address STRING,
            blood_type STRING,
            ethnicity STRING,
            marital_status STRING,
            emergency_contact STRING,
            registration_date DATE
        );


        CREATE TABLE Providers (
            provider_id STRING PRIMARY KEY,
            first_name STRING,
            last_name STRING,
            specialty STRING,
            phone STRING,
            email STRING,
            department_id STRING,
            license_number STRING,
            years_of_experience NUMBER,
            availability_status STRING
        );

        CREATE TABLE Departments (
            department_id STRING PRIMARY KEY,
            name STRING,
            floor NUMBER,
            head_provider_id STRING,
            contact_number STRING,
            open_hours STRING
        );

        CREATE TABLE Rooms (
            room_id STRING PRIMARY KEY,
            room_number STRING,
            floor NUMBER,
            room_type STRING,
            occupancy_status STRING,
            bed_count NUMBER
        );

        CREATE TABLE Appointments (
            appointment_id STRING PRIMARY KEY,
            patient_id STRING,
            provider_id STRING,
            appointment_date DATE,
            appointment_time TIME,
            status STRING,
            reason_for_visit STRING,
            room_id STRING
        );

        CREATE TABLE Visits (
            visit_id STRING PRIMARY KEY,
            patient_id STRING,
            provider_id STRING,
            department_id STRING,
            visit_date DATE,
            visit_type STRING,
            chief_complaint STRING,
            discharge_date DATE,
            room_id STRING
        );

        CREATE TABLE Diagnoses (
            diagnosis_id STRING PRIMARY KEY,
            visit_id STRING,
            icd10_code STRING,
            diagnosis_name STRING,
            diagnosis_type STRING,
            diagnosis_date DATE
        );

        CREATE TABLE Procedures (
            procedure_id STRING PRIMARY KEY,
            visit_id STRING,
            cpt_code STRING,
            procedure_name STRING,
            procedure_date DATE,
            performed_by STRING,
            notes STRING
        );

        CREATE TABLE Medications (
            medication_id STRING PRIMARY KEY,
            visit_id STRING,
            drug_name STRING,
            dosage STRING,
            route STRING,
            frequency STRING,
            start_date DATE,
            end_date DATE,
            prescribed_by STRING
        );

        CREATE TABLE Lab_Results (
            lab_result_id STRING PRIMARY KEY,
            visit_id STRING,
            test_name STRING,
            test_code STRING,
            sample_collected_date DATE,
            result_date DATE,
            result_value STRING,
            normal_range STRING,
            units STRING,
            abnormal_flag BOOLEAN
        );

        CREATE TABLE Allergies (
            allergy_id STRING PRIMARY KEY,
            patient_id STRING,
            allergen STRING,
            reaction STRING,
            severity STRING,
            status STRING,
            recorded_date DATE
        );

        CREATE TABLE Vital_Signs (
            vital_sign_id STRING PRIMARY KEY,
            visit_id STRING,
            recorded_date DATE,
            height_cm NUMBER,
            weight_kg NUMBER,
            temperature_c NUMBER,
            heart_rate NUMBER,
            blood_pressure STRING,
            respiratory_rate NUMBER,
            oxygen_saturation NUMBER
        );

        CREATE TABLE Insurance (
            insurance_id STRING PRIMARY KEY,
            patient_id STRING,
            provider_name STRING,
            policy_number STRING,
            coverage_start DATE,
            coverage_end DATE,
            plan_type STRING,
            copay_amount NUMBER,
            status STRING
        );

        CREATE TABLE Billing (
            billing_id STRING PRIMARY KEY,
            visit_id STRING,
            insurance_id STRING,
            total_cost NUMBER,
            patient_payable_amount NUMBER,
            billing_date DATE,
            payment_status STRING,
            due_date DATE,
            paid_date DATE
        );

        CREATE TABLE Devices (
            device_id STRING PRIMARY KEY,
            name STRING,
            department_id STRING,
            purchase_date DATE,
            last_maintenance_date DATE,
            status STRING,
            used_in_procedure_id STRING
        );

        For examples:

        Example 1:

        SQL_QUERY: 
        SELECT * FROM APPOINTMENTS
        JOIN PATIENTS;

        The query is missing a join condition and it would result in a cartesian product. 

        At the end, return the following JSON object on a new line. The confidence score
        is your confidence in the accuracy of this analysis. 

        {{
        "issues_found": true,        // true if performance or logic issues are found
        "confidence_score": 0–100    // your confidence in the accuracy of this analysis
        }}

        """
        result = llm.predict(prompt)
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


# 6️⃣ Node: Notify the user

def notify_user(state: State) -> State:
    notifications: List[Notification] = []
    for item in state.get("flagged_queries", []):
        user = item["query"]["USER_NAME"]
        query_id = item["query"]["QUERY_ID"]
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
