# db.py
import os
import snowflake.connector
from dotenv import load_dotenv
load_dotenv()

def get_snowflake_connection():
    # global snowflake_conn
    # if snowflake_conn is None:
    try:
        snowflake_conn = snowflake.connector.connect(
                user='YOGESWARI',
                password=os.getenv("SNOWFLAKE_PASSWORD"),
                account=os.getenv("SNOWFLAKE_ACCOUNT"),
                warehouse='COMPUTE_WH',
                database='HEALTHCARE',
                schema='CLINICAL',
                role='ACCOUNTADMIN'
            )
        print("snowflake connection established")
        return snowflake_conn
    except Exception as e:
        print("Error in establishing the connection")
        raise

