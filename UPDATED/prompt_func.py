def prompt_fun(qry_text):
    return f"""
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
        SQL query. If the query contains cross join, do not reply as 'well-structured' as it
        would be time consuming for cross joins and fall under potential threat thought it 
        appears to be well strucured. 
        If the query does **not** suffer from any of the above issues, reply:
        > "✅ The query appears well-structured. The long execution time is likely due to 
        the volume of data processed. No optimization needed."

        SQL: ```{qry_text}```


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