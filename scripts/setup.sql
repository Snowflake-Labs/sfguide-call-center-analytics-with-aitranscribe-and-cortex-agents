/*--
 Call Center Analytics with Snowflake Cortex - Setup Script
 This script creates all necessary objects for the call center analytics solution
--*/

USE ROLE accountadmin;

-- Create custom role for call center analytics
CREATE OR REPLACE ROLE call_center_analytics_role
    COMMENT = 'Role for call center analytics with AI_TRANSCRIBE and Cortex Agents';

-- Create warehouse for call center analytics
CREATE OR REPLACE WAREHOUSE call_center_analytics_wh
    WAREHOUSE_SIZE = 'large'
    WAREHOUSE_TYPE = 'standard'
    AUTO_SUSPEND = 300
    AUTO_RESUME = TRUE
    INITIALLY_SUSPENDED = TRUE
    COMMENT = 'Warehouse for call center analytics with Cortex LLM';

-- Grant warehouse usage to custom role
GRANT USAGE ON WAREHOUSE call_center_analytics_wh TO ROLE call_center_analytics_role;
GRANT OPERATE ON WAREHOUSE call_center_analytics_wh TO ROLE call_center_analytics_role;

USE WAREHOUSE call_center_analytics_wh;

-- assign Query Tag to Session. This helps with performance monitoring and troubleshooting
ALTER SESSION SET query_tag = '{"origin":"sf_sit-is","name":"call_center_analytics_2","version":{"major":1, "minor":0},"attributes":{"is_quickstart":1, "source":"sql"}}';

-- Create database and schemas
CREATE DATABASE IF NOT EXISTS call_center_analytics_db;
CREATE OR REPLACE SCHEMA call_center_analytics_db.analytics;

-- Grant database and schema access to custom role
GRANT USAGE ON DATABASE call_center_analytics_db TO ROLE call_center_analytics_role;
GRANT USAGE ON SCHEMA call_center_analytics_db.public TO ROLE call_center_analytics_role;
GRANT USAGE ON SCHEMA call_center_analytics_db.analytics TO ROLE call_center_analytics_role;

-- Grant create privileges on schemas
GRANT CREATE TABLE ON SCHEMA call_center_analytics_db.public TO ROLE call_center_analytics_role;
GRANT CREATE VIEW ON SCHEMA call_center_analytics_db.public TO ROLE call_center_analytics_role;
GRANT CREATE STAGE ON SCHEMA call_center_analytics_db.public TO ROLE call_center_analytics_role;
GRANT CREATE FILE FORMAT ON SCHEMA call_center_analytics_db.public TO ROLE call_center_analytics_role;
GRANT CREATE FUNCTION ON SCHEMA call_center_analytics_db.public TO ROLE call_center_analytics_role;
GRANT CREATE CORTEX SEARCH SERVICE ON SCHEMA call_center_analytics_db.public TO ROLE call_center_analytics_role;
GRANT CREATE TABLE ON SCHEMA call_center_analytics_db.analytics TO ROLE call_center_analytics_role;
GRANT CREATE VIEW ON SCHEMA call_center_analytics_db.analytics TO ROLE call_center_analytics_role;
GRANT CREATE STAGE ON SCHEMA call_center_analytics_db.analytics TO ROLE call_center_analytics_role;
GRANT CREATE FILE FORMAT ON SCHEMA call_center_analytics_db.analytics TO ROLE call_center_analytics_role;
GRANT CREATE FUNCTION ON SCHEMA call_center_analytics_db.analytics TO ROLE call_center_analytics_role;
GRANT CREATE CORTEX SEARCH SERVICE ON SCHEMA call_center_analytics_db.analytics TO ROLE call_center_analytics_role;
GRANT CREATE STREAMLIT ON SCHEMA call_center_analytics_db.analytics TO ROLE call_center_analytics_role;

-- Grant CORTEX_USER role for Cortex functions access
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE call_center_analytics_role;

-- role hierarchy
GRANT ROLE call_center_analytics_role TO ROLE sysadmin;

-- Start additional setup
ALTER ACCOUNT SET CORTEX_ENABLED_CROSS_REGION = 'ANY_REGION';

-- Start Streamlit setup
GRANT CREATE STREAMLIT ON SCHEMA call_center_analytics_db.analytics TO ROLE call_center_analytics_role;

-- Create stages for data and audio files
CREATE OR REPLACE STAGE call_center_analytics_db.analytics.audio_files
    DIRECTORY = (ENABLE = TRUE)
    ENCRYPTION = (TYPE = 'SNOWFLAKE_SSE')
    COMMENT = 'Stage for call center audio files';

-- Grant stage access to custom role
GRANT READ ON STAGE call_center_analytics_db.analytics.audio_files TO ROLE call_center_analytics_role;
GRANT WRITE ON STAGE call_center_analytics_db.analytics.audio_files TO ROLE call_center_analytics_role;

GRANT READ ON STAGE call_center_analytics_db.analytics.audio_files TO ROLE call_center_analytics_role;
GRANT WRITE ON STAGE call_center_analytics_db.analytics.audio_files TO ROLE call_center_analytics_role;

-- Grant SELECT privileges on all tables for Cortex Analyst semantic models
GRANT SELECT ON ALL TABLES IN SCHEMA call_center_analytics_db.public TO ROLE call_center_analytics_role;
GRANT SELECT ON ALL TABLES IN SCHEMA call_center_analytics_db.analytics TO ROLE call_center_analytics_role;
GRANT SELECT ON FUTURE TABLES IN SCHEMA call_center_analytics_db.public TO ROLE call_center_analytics_role;
GRANT SELECT ON FUTURE TABLES IN SCHEMA call_center_analytics_db.analytics TO ROLE call_center_analytics_role;

-- Grant SELECT privileges on all views for Cortex Analyst semantic models
GRANT SELECT ON ALL VIEWS IN SCHEMA call_center_analytics_db.public TO ROLE call_center_analytics_role;
GRANT SELECT ON ALL VIEWS IN SCHEMA call_center_analytics_db.analytics TO ROLE call_center_analytics_role;
GRANT SELECT ON FUTURE VIEWS IN SCHEMA call_center_analytics_db.public TO ROLE call_center_analytics_role;
GRANT SELECT ON FUTURE VIEWS IN SCHEMA call_center_analytics_db.analytics TO ROLE call_center_analytics_role;



-- Display next steps
SELECT '1.' AS step,
       'Upload mp3 files to audio_files stage' AS instruction
UNION ALL
SELECT '2.', 'Upload and run ai_transcribe_analytics.ipynb notebook'
UNION ALL
SELECT '3.', 'Upload and run cortex_analyst_setup.ipynb notebook'
UNION ALL
SELECT '4.', 'Deploy Streamlit application with Modern_Call_Center_App.py';
