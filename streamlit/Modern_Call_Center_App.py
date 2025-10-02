import streamlit as st
import pandas as pd
import numpy as np
import json
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import _snowflake
from snowflake.snowpark.context import get_active_session

# Page configuration
st.set_page_config(
    page_title="AI-Powered Call Center Analytics",
    page_icon="🎧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session
session = get_active_session()

# Configuration - Update these based on your setup
API_ENDPOINT = "/api/v2/cortex/agent:run"
API_TIMEOUT = 50000  # in milliseconds

# Get current database and schema dynamically
current_db = session.get_current_database()
current_schema = session.get_current_schema()

CORTEX_SEARCH_SERVICE = f"{current_db}.{current_schema}.call_center_search"
SEMANTIC_MODEL = f"@{current_db}.{current_schema}.cortex_models/semantic_models/call_center_semantic_model.yaml"

# CSS for modern styling
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        font-weight: bold;
        margin-bottom: 2rem;
    }

    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin: 0.5rem 0;
    }

    .metric-value {
        font-size: 2rem;
        font-weight: bold;
    }

    .metric-label {
        font-size: 1rem;
        opacity: 0.9;
    }

    .insight-box {
        background: var(--background-color, rgba(102, 126, 234, 0.1));
        border-left: 4px solid #667eea;
        padding: 1rem;
        border-radius: 5px;
        margin: 1rem 0;
        border: 1px solid var(--border-color, rgba(102, 126, 234, 0.2));
    }

    /* Dark mode support */
    @media (prefers-color-scheme: dark) {
        .insight-box {
            background: rgba(102, 126, 234, 0.15);
            border: 1px solid rgba(102, 126, 234, 0.3);
        }
    }

    /* Streamlit dark mode class support */
    .stApp[data-theme="dark"] .insight-box,
    [data-testid="stAppViewContainer"][data-theme="dark"] .insight-box {
        background: rgba(102, 126, 234, 0.15);
        border: 1px solid rgba(102, 126, 234, 0.3);
    }

    .stTab {
        font-size: 1.2rem;
    }
</style>
""", unsafe_allow_html=True)

# Helper Functions
@st.cache_data(ttl=1800)  # Cache for 30 minutes
def load_kpis():
    """Load overall KPIs from the view created in setup"""
    try:
        # First try the existing view
        df = session.sql(f"SELECT * FROM {current_db}.{current_schema}.call_center_kpis").to_pandas()
        if len(df) > 0:
            return df.iloc[0]
        else:
            # No data returned from KPIs view
            return create_default_kpis()
    except Exception as e:
        # If view doesn't exist, try to calculate KPIs directly from comprehensive_call_analysis
        # st.info("Loading performance metrics...")
        try:
            query = f"""
            SELECT
                COUNT(*) as TOTAL_CALLS,
                COUNT(DISTINCT agent_name) as UNIQUE_AGENTS,
                ROUND(AVG(sentiment_score), 3) as AVG_SENTIMENT_SCORE,
                ROUND(AVG(agent_performance_score), 1) as AVG_AGENT_PERFORMANCE,
                ROUND(SUM(CASE WHEN issue_resolved = 'yes' THEN 1 ELSE 0 END) / COUNT(*) * 100, 1) as RESOLUTION_RATE_PCT,
                ROUND(SUM(CASE WHEN customer_satisfaction = 'satisfied' THEN 1 ELSE 0 END) / COUNT(*) * 100, 1) as SATISFACTION_RATE_PCT,
                ROUND(SUM(CASE WHEN escalation_required = 'yes' THEN 1 ELSE 0 END) / COUNT(*) * 100, 1) as ESCALATION_RATE_PCT,
                ROUND(SUM(CASE WHEN sentiment_score > 0.1 THEN 1 ELSE 0 END) / COUNT(*) * 100, 1) as POSITIVE_SENTIMENT_PCT,
                MODE(primary_intent) as TOP_CALL_INTENT,
                ROUND(AVG(word_count), 0) as AVG_CALL_LENGTH_WORDS
            FROM {current_db}.{current_schema}.comprehensive_call_analysis
            WHERE agent_name IS NOT NULL
            AND agent_name != 'Not Available'
            """
            result = session.sql(query).to_pandas()
            if not result.empty:
                return result.iloc[0]
            else:
                return create_default_kpis()
        except Exception as e2:
            # Unable to calculate KPIs from data
            return create_default_kpis()

def create_default_kpis():
    """Create default KPI values when no data is available"""
    return pd.Series({
        'TOTAL_CALLS': 0,
        'UNIQUE_AGENTS': 0,
        'AVG_SENTIMENT_SCORE': 0.0,
        'AVG_AGENT_PERFORMANCE': 0.0,
        'RESOLUTION_RATE_PCT': 0.0,
        'SATISFACTION_RATE_PCT': 0.0,
        'ESCALATION_RATE_PCT': 0.0,
        'POSITIVE_SENTIMENT_PCT': 0.0,
        'TOP_CALL_INTENT': 'N/A',
        'AVG_CALL_LENGTH_WORDS': 0
    })

@st.cache_data(ttl=1800)
def load_agent_performance():
    """Load agent performance data"""
    try:
        return session.sql(f"SELECT * FROM {current_db}.{current_schema}.agent_performance_summary").to_pandas()
    except Exception as e:
        # If view doesn't exist, try to calculate agent performance directly
        # Loading agent performance data...
        try:
            query = f"""
            SELECT
                agent_name as AGENT_NAME,
                COUNT(*) as TOTAL_CALLS,
                ROUND(AVG(sentiment_score), 3) as AVG_SENTIMENT,
                ROUND(AVG(agent_performance_score), 1) as AVG_PERFORMANCE_SCORE,

                -- Resolution effectiveness
                SUM(CASE WHEN issue_resolved = 'yes' THEN 1 ELSE 0 END) as RESOLVED_CALLS,
                ROUND(SUM(CASE WHEN issue_resolved = 'yes' THEN 1 ELSE 0 END) / COUNT(*) * 100, 1) as RESOLUTION_RATE,

                -- Customer satisfaction
                SUM(CASE WHEN customer_satisfaction = 'satisfied' THEN 1 ELSE 0 END) as SATISFIED_CUSTOMERS,
                ROUND(SUM(CASE WHEN customer_satisfaction = 'satisfied' THEN 1 ELSE 0 END) / COUNT(*) * 100, 1) as SATISFACTION_RATE,

                -- Escalation patterns
                SUM(CASE WHEN escalation_required = 'yes' THEN 1 ELSE 0 END) as ESCALATIONS,
                ROUND(SUM(CASE WHEN escalation_required = 'yes' THEN 1 ELSE 0 END) / COUNT(*) * 100, 1) as ESCALATION_RATE

            FROM {current_db}.{current_schema}.comprehensive_call_analysis
            WHERE agent_name != 'Not Available' AND agent_name IS NOT NULL
            GROUP BY agent_name
            ORDER BY AVG_PERFORMANCE_SCORE DESC
            """
            return session.sql(query).to_pandas()
        except Exception as e2:
            # Unable to calculate agent performance
            return pd.DataFrame()  # Return empty DataFrame

@st.cache_data(ttl=1800)
def load_call_patterns():
    """Load call pattern analysis"""
    try:
        query = f"""
        SELECT
            primary_intent as PRIMARY_INTENT,
            COUNT(*) as CALL_COUNT,
            ROUND(AVG(sentiment_score), 3) as AVG_SENTIMENT,
            ROUND(SUM(CASE WHEN issue_resolved = 'yes' THEN 1 ELSE 0 END) / COUNT(*) * 100, 1) as RESOLUTION_RATE,
            ROUND(SUM(CASE WHEN customer_satisfaction = 'satisfied' THEN 1 ELSE 0 END) / COUNT(*) * 100, 1) as SATISFACTION_RATE
        FROM {current_db}.{current_schema}.comprehensive_call_analysis
        WHERE primary_intent IS NOT NULL AND primary_intent != 'Not Available'
        GROUP BY primary_intent
        ORDER BY CALL_COUNT DESC
        """
        return session.sql(query).to_pandas()
    except Exception as e:
        # Unable to load call patterns
        return pd.DataFrame()  # Return empty DataFrame

@st.cache_data(ttl=1800)
def load_sentiment_trends():
    """Load sentiment trends over time"""
    try:
        query = f"""
        SELECT
            sentiment_category as SENTIMENT_CATEGORY,
            COUNT(*) as COUNT,
            ROUND(AVG(agent_performance_score), 1) as AVG_PERFORMANCE
        FROM {current_db}.{current_schema}.comprehensive_call_analysis
        WHERE sentiment_category IS NOT NULL
        GROUP BY sentiment_category
        """
        return session.sql(query).to_pandas()
    except Exception as e:
        # Unable to load sentiment trends
        return pd.DataFrame()  # Return empty DataFrame

@st.cache_data(ttl=1800)
def load_pattern_analysis():
    """Load pattern analysis data for heatmap and scatter plot"""
    try:
        # Query for heatmap - grouped by intent and urgency
        heatmap_query = f"""
        SELECT
            primary_intent as PRIMARY_INTENT,
            urgency_level as URGENCY_LEVEL,
            COUNT(*) as CALL_COUNT,
            ROUND(SUM(CASE WHEN issue_resolved = 'yes' THEN 1 ELSE 0 END) / COUNT(*) * 100, 1) as RESOLUTION_RATE
        FROM {current_db}.{current_schema}.comprehensive_call_analysis
        WHERE primary_intent IS NOT NULL AND primary_intent != 'Not Available'
        AND urgency_level IS NOT NULL AND urgency_level != 'Not Available'
        GROUP BY primary_intent, urgency_level
        ORDER BY CALL_COUNT DESC
        """

        # Query for scatter plot - grouped by intent only
        scatter_query = f"""
        SELECT
            primary_intent as PRIMARY_INTENT,
            COUNT(*) as CALL_COUNT,
            ROUND(AVG(sentiment_score), 3) as AVG_SENTIMENT,
            ROUND(SUM(CASE WHEN issue_resolved = 'yes' THEN 1 ELSE 0 END) / COUNT(*) * 100, 1) as RESOLUTION_RATE,
            ROUND(SUM(CASE WHEN escalation_required = 'yes' THEN 1 ELSE 0 END) / COUNT(*) * 100, 1) as ESCALATION_RATE
        FROM {current_db}.{current_schema}.comprehensive_call_analysis
        WHERE primary_intent IS NOT NULL AND primary_intent != 'Not Available'
        GROUP BY primary_intent
        ORDER BY CALL_COUNT DESC
        """

        heatmap_df = session.sql(heatmap_query).to_pandas()
        scatter_df = session.sql(scatter_query).to_pandas()

        return heatmap_df, scatter_df
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame()

@st.cache_data(ttl=1800)
def load_anomaly_detection():
    """Load anomaly detection data"""
    try:
        anomaly_query = f"""
        WITH call_stats AS (
            SELECT
                call_id,
                agent_name,
                sentiment_score,
                agent_performance_score,
                word_count,
                customer_satisfaction,
                PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY sentiment_score) OVER () as sentiment_q1,
                PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY sentiment_score) OVER () as sentiment_q3,
                AVG(sentiment_score) OVER () as avg_sentiment,
                STDDEV(sentiment_score) OVER () as stddev_sentiment
            FROM {current_db}.{current_schema}.comprehensive_call_analysis
            WHERE sentiment_score IS NOT NULL
        )
        SELECT
            call_id as CALL_ID,
            agent_name as AGENT_NAME,
            sentiment_score as SENTIMENT_SCORE,
            agent_performance_score as AGENT_PERFORMANCE_SCORE,
            word_count as WORD_COUNT,
            customer_satisfaction as CUSTOMER_SATISFACTION,
            CASE
                WHEN sentiment_score < (sentiment_q1 - 1.5 * (sentiment_q3 - sentiment_q1)) THEN 'Extremely Low Sentiment'
                WHEN sentiment_score > (sentiment_q3 + 1.5 * (sentiment_q3 - sentiment_q1)) THEN 'Extremely High Sentiment'
                WHEN ABS(sentiment_score - avg_sentiment) > 2 * stddev_sentiment THEN 'Sentiment Outlier'
                ELSE 'Normal'
            END as ANOMALY_TYPE
        FROM call_stats
        WHERE ANOMALY_TYPE != 'Normal'
        ORDER BY ABS(sentiment_score - avg_sentiment) DESC
        LIMIT 20
        """

        return session.sql(anomaly_query).to_pandas()
    except Exception as e:
        return pd.DataFrame()

@st.cache_data(ttl=1800)
def load_recommendations():
    """Load AI-generated recommendations"""
    try:
        recommendations_query = f"""
        WITH summary_metrics AS (
            SELECT
                COUNT(*) as total_calls,
                ROUND(AVG(sentiment_score), 3) as avg_sentiment,
                ROUND(SUM(CASE WHEN issue_resolved = 'yes' THEN 1 ELSE 0 END) / COUNT(*) * 100, 1) as resolution_rate,
                ROUND(SUM(CASE WHEN customer_satisfaction = 'satisfied' THEN 1 ELSE 0 END) / COUNT(*) * 100, 1) as satisfaction_rate,
                MODE(primary_intent) as TOP_INTENT
            FROM {current_db}.{current_schema}.comprehensive_call_analysis
            WHERE agent_name != 'Not Available'
        )
        SELECT
            SNOWFLAKE.CORTEX.COMPLETE(
                'mixtral-8x7b',
                'Based on these call center metrics, provide 5 actionable recommendations in bullet points:
                - Total Calls: ' || total_calls || '
                - Average Sentiment: ' || avg_sentiment || '
                - Resolution Rate: ' || resolution_rate || '%
                - Satisfaction Rate: ' || satisfaction_rate || '%
                - Top Intent: ' || TOP_INTENT
            ) as recommendations
        FROM summary_metrics
        """

        return session.sql(recommendations_query).to_pandas()
    except Exception as e:
        return pd.DataFrame()

def run_snowflake_query(query):
    """Execute a Snowflake query and return results"""
    try:
        # Clean up the query
        clean_query = query.replace(';','').strip()

        # Execute query
        result = session.sql(clean_query)

        return result

    except Exception as e:
        st.error(f"❌ **SQL Error:** {str(e)}")
        return None

def safe_get_column(row, column_name, default='N/A'):
    """Safely get column value handling both uppercase and lowercase column names"""
    # Try lowercase first
    if column_name.lower() in row.index:
        return row[column_name.lower()]
    # Try uppercase
    elif column_name.upper() in row.index:
        return row[column_name.upper()]
    # Try original case
    elif column_name in row.index:
        return row[column_name]
    else:
        return default



def cortex_agent_call(query: str, conversation_history: list = None, limit: int = 10):
    """Make API call to Cortex Agent following official specification with conversation context"""

    # Build messages array with conversation history
    messages = []

    # Add conversation history if provided
    if conversation_history:
        # Limit to last 10 messages to avoid token limits while maintaining context
        recent_history = conversation_history[-10:] if len(conversation_history) > 10 else conversation_history

        for msg in recent_history:
            if msg['role'] == 'user':
                messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": msg['content']
                        }
                    ]
                })
            elif msg['role'] == 'assistant':
                messages.append({
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": msg['content']
                        }
                    ]
                })
    else:
        # If no conversation history, add current query
        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": query
                }
            ]
        })

    payload = {
        "model": "claude-3-5-sonnet",  # Confirmed supported model
        "messages": messages,
        "tools": [
            {
                "tool_spec": {
                    "type": "cortex_analyst_text_to_sql",
                    "name": "data_model"
                }
            },
            {
                "tool_spec": {
                    "type": "cortex_search",
                    "name": "transcript_search"
                }
            }
        ],
        "tool_resources": {
            "data_model": {
                "semantic_model_file": SEMANTIC_MODEL
            },
            "transcript_search": {
                "name": CORTEX_SEARCH_SERVICE,
                "max_results": limit,
                "id_column": "call_id",
                "title_column": "primary_intent"  # Added title column as per spec
            }
        }
    }

    try:
        resp = _snowflake.send_snow_api_request(
            "POST",
            API_ENDPOINT,
            {},
            {},
            payload,
            None,
            API_TIMEOUT,
        )

        if resp["status"] != 200:
            st.error(f"❌ Cortex Agent HTTP Error: {resp['status']} - {resp.get('reason', 'Unknown')}")
            return None

        try:
            response_content = json.loads(resp["content"])
            st.success("✅ Cortex Agent responded successfully!")
            return response_content
        except json.JSONDecodeError as e:
            st.error(f"❌ Failed to parse Cortex Agent response: {str(e)}")
            st.text(f"Raw response: {resp['content'][:500]}...")
            return None

    except Exception as e:
        st.error(f"❌ Cortex Agent request failed: {str(e)}")
        return None

def process_agent_response(response, query=""):
    """Process Cortex Agent response following official API specification"""
    text = ""
    sql = ""
    citations = []
    agent_steps = []

    # Check if this is a search query vs analytical query
    is_search_query = any(word in query.lower() for word in ['show me calls', 'find calls', 'search for calls', 'find transcripts', 'show transcripts'])

    if not response:
        return text, sql, citations
    if isinstance(response, str):
        return text, sql, citations

    try:
        # Handle streaming list response format
        if isinstance(response, list):
            for event in response:
                if isinstance(event, dict):
                    # Check for errors first
                    if event.get('event') == "error":
                        error_data = event.get('data', {})
                        error_message = error_data.get('message', 'Unknown error')

                        if 'semantic model YAML' in error_message:
                            st.error("🔧 **Semantic Model Error**: Your semantic model YAML file has syntax errors.")
                            st.error(f"**Details**: {error_message}")
                            st.info("""
                            **To Fix:**
                            1. Update Cell 6 in cortex_analyst_setup.ipynb with the corrected semantic model
                            2. Use uppercase data types: 'TEXT', 'COUNT', 'AVERAGE', 'SUM'
                            3. Re-run the setup notebook to upload the fixed YAML
                            """)
                        else:
                            st.error(f"Cortex Agent Error: {error_message}")
                        return "", "", []

                    # Handle successful message deltas and content
                    elif event.get('event') == "message.delta":
                        data = event.get('data', {})
                        delta = data.get('delta', {})

                        # Extract content from delta
                        for content_item in delta.get('content', []):
                            content_type = content_item.get('type')

                            # Handle tool results (official format)
                            if content_type == "tool_results":
                                tool_results = content_item.get('tool_results', {})
                                if 'content' in tool_results:
                                    for result in tool_results['content']:
                                        if result.get('type') == 'json':
                                            json_data = result.get('json', {})
                                            text += json_data.get('text', '')
                                            if json_data.get('sql', ''):
                                                sql = json_data.get('sql', '')
                                                if not is_search_query:
                                                    st.success("✅ **Agent Step**: Generated SQL query for data analysis")

                                            # Handle search results
                                            search_results = json_data.get('searchResults', [])
                                            if search_results:
                                                st.success(f"✅ **Agent Step**: Found {len(search_results)} relevant transcript(s) - providing citations")
                                            for search_result in search_results:
                                                citations.append({
                                                    'source_id': search_result.get('source_id', ''),
                                                    'doc_id': search_result.get('doc_id', ''),
                                                    'title': search_result.get('title', '')
                                                })

                            # Handle tool use (when agent is calling tools)
                            elif content_type == "tool_use":
                                tool_use = content_item.get('tool_use', {})
                                tool_name = tool_use.get('name', '')

                                # Show what the agent is doing
                                if tool_name == 'cortex_analyst_text_to_sql':
                                    st.info("🔧 **Agent Step**: Using Cortex Analyst to generate SQL query for structured data analysis")
                                    # Extract SQL from analyst tool use
                                    input_data = tool_use.get('input', {})
                                    if 'sql' in input_data:
                                        sql = input_data['sql']
                                elif tool_name == 'cortex_search' or tool_name == 'transcript_search':
                                    st.info("🔍 **Agent Step**: Using Cortex Search to find relevant transcripts and unstructured data")
                                elif tool_name == 'data_model':
                                    st.info("📊 **Agent Step**: Accessing semantic data model to understand available metrics")

                            # Handle direct text content
                            elif content_type == 'text':
                                text += content_item.get('text', '')

                    # Handle complete messages (alternative format)
                    elif 'role' in event and event['role'] == 'assistant':
                        content_list = event.get('content', [])
                        for content_item in content_list:
                            if content_item.get('type') == 'text':
                                text += content_item.get('text', '')

        # Handle direct dict response format (non-streaming)
        elif isinstance(response, dict):
            if 'choices' in response:
                for choice in response['choices']:
                    if 'message' in choice and 'content' in choice['message']:
                        text += choice['message']['content']
            elif 'content' in response:
                text += str(response['content'])

    except Exception as e:
        st.error(f"Error processing response: {str(e)}")
        return "", "", []

    return text, sql, citations



# Main App
def main():
    # Header
    st.markdown('<h1 class="main-header">🎧 AI-Powered Call Center Analytics</h1>', unsafe_allow_html=True)

    # Subtitle
    st.markdown("""
    <div style="text-align: center; margin-bottom: 2rem; font-size: 1.2rem; color: #666;">
        Powered by Snowflake AI_TRANSCRIBE, Cortex Agents, and Advanced Analytics
    </div>
    """, unsafe_allow_html=True)

    # Sidebar
    with st.sidebar:
        st.header("🚀 Navigation")
        page = st.selectbox(
            "Choose a section:",
            ["📊 Executive Dashboard", "🤖 AI Assistant", "📈 Deep Analytics", "🎵 Audio Explorer"]
        )

        if st.button("🔄 Reset Cache", use_container_width=True):
            st.cache_data.clear()
            st.success("Cache cleared!")
            st.rerun()

        st.markdown("---")
        st.markdown("### 🔧 Quick Stats")

        # Load and display quick stats
        kpis = load_kpis()
        if kpis is not None:
            st.metric("Total Calls", f"{int(kpis['TOTAL_CALLS']):,}")
            st.metric("Avg Sentiment", f"{kpis['AVG_SENTIMENT_SCORE']:.3f}")
            st.metric("Resolution Rate", f"{kpis['RESOLUTION_RATE_PCT']:.1f}%")
        else:
            st.metric("Total Calls", "0")
            st.metric("Avg Sentiment", "0.000")
            st.metric("Resolution Rate", "0.0%")

        st.markdown("---")
        st.markdown("### ℹ️ About")
        st.markdown("""
        This modern call center analytics platform uses:
        - **AI_TRANSCRIBE** for audio processing
        - **Cortex Agents** for intelligent queries
        - **Advanced ML** for insights
        - **Real-time** analytics
        """)

    # Page routing
    if page == "📊 Executive Dashboard":
        show_executive_dashboard()
    elif page == "🤖 AI Assistant":
        show_ai_assistant()
    elif page == "📈 Deep Analytics":
        show_deep_analytics()
    elif page == "🎵 Audio Explorer":
        show_audio_explorer()

def show_executive_dashboard():
    st.header("📊 Executive Dashboard")

    # Load data
    kpis = load_kpis()
    agent_perf = load_agent_performance()
    call_patterns = load_call_patterns()
    sentiment_data = load_sentiment_trends()

    if kpis is None or kpis['TOTAL_CALLS'] == 0:
        st.info("📊 **No call data available** - Please load your call center data to begin analysis.")
        if kpis is None:
            return

    # KPI Cards
    st.subheader("🎯 Key Performance Indicators")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{int(kpis['TOTAL_CALLS']):,}</div>
            <div class="metric-label">Total Calls Analyzed</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{kpis['RESOLUTION_RATE_PCT']:.1f}%</div>
            <div class="metric-label">Resolution Rate</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{kpis['SATISFACTION_RATE_PCT']:.1f}%</div>
            <div class="metric-label">Customer Satisfaction</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{kpis['AVG_AGENT_PERFORMANCE']:.1f}/10</div>
            <div class="metric-label">Avg Agent Score</div>
        </div>
        """, unsafe_allow_html=True)

    # Charts Row 1
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📞 Call Intent Distribution")
        if not call_patterns.empty:
            fig = px.pie(
                call_patterns,
                values='CALL_COUNT',
                names='PRIMARY_INTENT',
                title="Calls by Intent Type"
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No call pattern data available.")

    with col2:
        st.subheader("😊 Sentiment Analysis")
        if not sentiment_data.empty:
            fig = px.bar(
                sentiment_data,
                x='SENTIMENT_CATEGORY',
                y='COUNT',
                color='SENTIMENT_CATEGORY',
                title="Call Sentiment Distribution",
                color_discrete_map={
                    'POSITIVE': '#2E8B57',
                    'NEUTRAL': '#FFD700',
                    'NEGATIVE': '#DC143C'
                }
            )
            fig.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No sentiment data available.")

    # Agent Performance Section
    st.subheader("👥 Agent Performance Overview")
    if not agent_perf.empty:
        # Top performers
        col1, col2 = st.columns(2)

        with col1:
            st.write("**🏆 Top Performing Agents**")
            top_agents = agent_perf.head(5)[['AGENT_NAME', 'AVG_PERFORMANCE_SCORE', 'RESOLUTION_RATE']]
            st.dataframe(
                top_agents.style.format({
                    'AVG_PERFORMANCE_SCORE': '{:.1f}',
                    'RESOLUTION_RATE': '{:.1f}%'
                }),
                use_container_width=True
            )

        with col2:
            st.write("**📊 Performance vs Resolution Rate**")
            fig = px.scatter(
                agent_perf,
                x='AVG_PERFORMANCE_SCORE',
                y='RESOLUTION_RATE',
                size='TOTAL_CALLS',
                hover_data=['AGENT_NAME', 'SATISFACTION_RATE'],
                title="Agent Performance Analysis"
            )
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No agent performance data available.")

    # Insights Box
    st.markdown(f"""
    <div class="insight-box">
        <h4>🔍 AI-Generated Insights</h4>
        <ul>
            <li><strong>Top Call Intent:</strong> {kpis['TOP_CALL_INTENT']} represents the most common reason customers contact support</li>
            <li><strong>Performance Spread:</strong> {kpis['UNIQUE_AGENTS']} agents with varying performance levels indicate training opportunities</li>
            <li><strong>Efficiency:</strong> Average call length of {int(kpis['AVG_CALL_LENGTH_WORDS'])} words suggests good conversation management</li>
            <li><strong>Quality Score:</strong> {kpis['POSITIVE_SENTIMENT_PCT']:.1f}% positive sentiment rate shows overall customer experience health</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

def show_ai_assistant():
    st.header("🤖 AI Assistant - Powered by Cortex Agents")

    # Examples section
    with st.expander("💡 Example Questions", expanded=False):
        st.markdown("""
        **🔍 Search for specific content in calls:**
        - "Show me calls where customers mentioned billing disputes"
        - "Find transcripts where agents offered refunds"
        - "Search for calls about technical support issues"

        **📊 Analyze call center performance:**
        - "What's the average resolution rate by agent?"
        - "Which call intents have the lowest satisfaction scores?"
        - "Give me the breakdown of calls by topic"

        **🚀 Complex questions:**
        - "Find billing complaint calls and show resolution rates for those agents"
        - "What are customers saying about our product and how does that correlate with satisfaction?"
        """)

    # New chat button
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("🔄 New Conversation", key="new_chat"):
            st.session_state.messages = []
            st.rerun()

    # Initialize chat
    if 'messages' not in st.session_state:
        st.session_state.messages = []

    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message['role']):
            st.markdown(message['content'])

    # Chat input
    if query := st.chat_input("Ask me anything about your call center data..."):
        # Add user message
        with st.chat_message("user"):
            st.markdown(query)
        st.session_state.messages.append({"role": "user", "content": query})

        # Get AI response
        with st.chat_message("assistant"):
            with st.spinner("🧠 Analyzing your request..."):
                response = cortex_agent_call(query, st.session_state.messages, 5)
                text, sql, citations = process_agent_response(response, query)

                if text:
                    # Clean up response formatting
                    text = text.replace("【†", "[").replace("†】", "]")
                    st.markdown(text)

                    # Store response and SQL in session state
                    st.session_state.messages.append({"role": "assistant", "content": text})
                    if sql:
                        # Store SQL with message index for persistence
                        message_idx = len(st.session_state.messages) - 1
                        st.session_state[f"sql_{message_idx}"] = sql

                    # Show citations if available
                    if citations:
                        with st.expander("📄 Source Citations"):
                            for i, citation in enumerate(citations):
                                doc_id = citation.get("doc_id", "")
                                source_id = citation.get("source_id", "")
                                title = citation.get("title", "")

                                if doc_id:
                                    # Try multiple approaches to find the transcript
                                    # First, try exact match in comprehensive_call_analysis
                                    query_text = f"""
                                    SELECT call_id, agent_name, customer_name, primary_intent,
                                           LEFT(transcript_text, 400) || '...' as preview
                                    FROM {current_db}.{current_schema}.comprehensive_call_analysis
                                    WHERE call_id = '{doc_id}'
                                    """

                                    result = run_snowflake_query(query_text)

                                    if result:
                                        try:
                                            result_df = result.to_pandas()
                                            if not result_df.empty:
                                                row = result_df.iloc[0]
                                                call_id = safe_get_column(row, 'call_id', doc_id)
                                                agent_name = safe_get_column(row, 'agent_name', 'N/A')
                                                customer_name = safe_get_column(row, 'customer_name', 'N/A')
                                                primary_intent = safe_get_column(row, 'primary_intent', 'N/A')
                                                preview = safe_get_column(row, 'preview', 'No preview available')

                                                st.write(f"**Call ID:** {call_id}")
                                                st.write(f"**Agent:** {agent_name} | **Customer:** {customer_name}")
                                                st.write(f"**Intent:** {primary_intent}")
                                                st.write(f"**Preview:** {preview}")
                                                st.markdown("---")
                                                continue
                                        except Exception as e:
                                            pass  # Continue to next query

                                    # If no exact match, try pattern matching in comprehensive_call_analysis
                                    query_text = f"""
                                    SELECT call_id, agent_name, customer_name, primary_intent,
                                           LEFT(transcript_text, 400) || '...' as preview
                                    FROM {current_db}.{current_schema}.comprehensive_call_analysis
                                    WHERE call_id LIKE '%{doc_id.replace('.mp3', '').replace('.wav', '')}%'
                                    LIMIT 1
                                    """

                                    result = run_snowflake_query(query_text)

                                    if result:
                                        try:
                                            result_df = result.to_pandas()
                                            if not result_df.empty:
                                                row = result_df.iloc[0]
                                                call_id = safe_get_column(row, 'call_id', doc_id)
                                                agent_name = safe_get_column(row, 'agent_name', 'N/A')
                                                customer_name = safe_get_column(row, 'customer_name', 'N/A')
                                                primary_intent = safe_get_column(row, 'primary_intent', 'N/A')
                                                preview = safe_get_column(row, 'preview', 'No preview available')

                                                st.write(f"**Call ID:** {call_id}")
                                                st.write(f"**Agent:** {agent_name} | **Customer:** {customer_name}")
                                                st.write(f"**Intent:** {primary_intent}")
                                                st.write(f"**Preview:** {preview}")
                                                st.markdown("---")
                                                continue
                                        except Exception as e:
                                            pass  # Continue to next query

                                    # If still no match, try the ai_transcribed_calls table as fallback
                                    query_text = f"""
                                    SELECT call_id,
                                           'N/A' as agent_name,
                                           'N/A' as customer_name,
                                           'Sample Audio' as primary_intent,
                                           LEFT(transcript_text, 400) || '...' as preview
                                    FROM {current_db}.{current_schema}.ai_transcribed_calls
                                    WHERE call_id = '{doc_id}'
                                    AND transcript_text IS NOT NULL
                                    """

                                    result = run_snowflake_query(query_text)

                                    if result:
                                        try:
                                            result_df = result.to_pandas()
                                            if not result_df.empty:
                                                row = result_df.iloc[0]
                                                call_id = safe_get_column(row, 'call_id', doc_id)
                                                agent_name = safe_get_column(row, 'agent_name', 'N/A')
                                                customer_name = safe_get_column(row, 'customer_name', 'N/A')
                                                primary_intent = safe_get_column(row, 'primary_intent', 'N/A')
                                                preview = safe_get_column(row, 'preview', 'No preview available')

                                                st.write(f"**Call ID:** {call_id}")
                                                st.write(f"**Agent:** {agent_name} | **Customer:** {customer_name}")
                                                st.write(f"**Intent:** {primary_intent}")
                                                st.write(f"**Preview:** {preview}")
                                                st.markdown("---")
                                                continue
                                        except Exception as e:
                                            pass  # Continue to next query

                                    # If still no exact match, try pattern matching in ai_transcribed_calls
                                    query_text = f"""
                                    SELECT call_id,
                                           'N/A' as agent_name,
                                           'N/A' as customer_name,
                                           'Sample Audio' as primary_intent,
                                           LEFT(transcript_text, 400) || '...' as preview
                                    FROM {current_db}.{current_schema}.ai_transcribed_calls
                                    WHERE call_id LIKE '%{doc_id.replace('.mp3', '').replace('.wav', '')}%'
                                    AND transcript_text IS NOT NULL
                                    LIMIT 1
                                    """

                                    result = run_snowflake_query(query_text)

                                    if result:
                                        try:
                                            result_df = result.to_pandas()
                                            if not result_df.empty:
                                                row = result_df.iloc[0]
                                                call_id = safe_get_column(row, 'call_id', doc_id)
                                                agent_name = safe_get_column(row, 'agent_name', 'N/A')
                                                customer_name = safe_get_column(row, 'customer_name', 'N/A')
                                                primary_intent = safe_get_column(row, 'primary_intent', 'N/A')
                                                preview = safe_get_column(row, 'preview', 'No preview available')

                                                st.write(f"**Call ID:** {call_id}")
                                                st.write(f"**Agent:** {agent_name} | **Customer:** {customer_name}")
                                                st.write(f"**Intent:** {primary_intent}")
                                                st.write(f"**Preview:** {preview}")
                                                st.markdown("---")
                                                continue
                                        except Exception as e:
                                            pass  # Continue to next query

                                    # If we get here, no queries found data
                                    st.write(f"**Source File:** {doc_id}")
                                    if title:
                                        st.write(f"**Content Type:** {title}")
                                    st.write("*Transcript content not found in database*")
                                    st.markdown("---")
                                else:
                                    # Show citation info without database lookup
                                    st.write(f"**Citation {i+1}:**")
                                    if source_id:
                                        st.write(f"**Source ID:** {source_id}")
                                    if title:
                                        st.write(f"**Title:** {title}")
                                    st.markdown("---")

                    # Show generated SQL if available (only for analytical queries, not search)
                    is_search_query = any(word in query.lower() for word in ['show me calls', 'find calls', 'search for calls', 'find transcripts', 'show transcripts'])

                    if sql and not is_search_query:  # Only show SQL for analytical queries
                        message_idx = len(st.session_state.messages) - 1
                        st.session_state[f"sql_{message_idx}"] = sql

                else:
                    st.error("❌ **Unable to process your request.** Please try rephrasing your question or try again in a moment.")

    # Display SQL queries for all messages that have them
    for i, message in enumerate(st.session_state.messages):
        if message['role'] == 'assistant' and f"sql_{i}" in st.session_state:
            stored_sql = st.session_state[f"sql_{i}"]
            with st.expander("🔍 Generated SQL Query", expanded=True):
                st.code(stored_sql, language="sql")

                # Execute and show results with better error handling
                # Create a unique key that doesn't change
                query_hash = hash(stored_sql) % 10000
                col1, col2 = st.columns([1, 4])
                with col1:
                    execute_button = st.button("▶️ Execute Query", key=f"exec_sql_{query_hash}_{i}")

                # Always show some feedback
                if execute_button:
                    # Use session state to track execution
                    if f"executed_{query_hash}_{i}" not in st.session_state:
                        st.session_state[f"executed_{query_hash}_{i}"] = False

                    st.session_state[f"executed_{query_hash}_{i}"] = True

                if st.session_state.get(f"executed_{query_hash}_{i}", False):
                    with st.spinner("🔄 Executing SQL query..."):
                        result = run_snowflake_query(stored_sql)
                        if result is not None:
                            try:
                                df = result.to_pandas()
                                st.success(f"✅ **Query Results** ({len(df)} rows)")
                                st.dataframe(df, use_container_width=True)
                            except Exception as conv_error:
                                st.error(f"❌ **Data Conversion Error:** {str(conv_error)}")
                        else:
                            st.warning("⚠️ **Query execution failed** - please check the SQL syntax")
                else:
                    st.info("👆 **Click 'Execute Query' to run the SQL and see results**")

def show_deep_analytics():
    st.header("📈 Deep Analytics")

    tab1, tab2, tab3 = st.tabs(["🔍 Pattern Analysis", "🚨 Anomaly Detection", "🎯 Recommendations"])

    with tab1:
        st.subheader("Call Pattern Deep Dive")

        # Load cached pattern analysis data
        heatmap_df, scatter_df = load_pattern_analysis()

        if not heatmap_df.empty or not scatter_df.empty:
            col1, col2 = st.columns(2)

            with col1:
                # Heatmap of resolution rates
                if not heatmap_df.empty:
                    pivot_data = heatmap_df.pivot_table(
                        values='RESOLUTION_RATE',
                        index='PRIMARY_INTENT',
                        columns='URGENCY_LEVEL',
                        fill_value=0
                    )

                    fig = px.imshow(
                        pivot_data.values,
                        x=pivot_data.columns,
                        y=pivot_data.index,
                        color_continuous_scale='RdYlGn',
                        title="Resolution Rate by Intent & Urgency"
                    )
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No data available for heatmap.")

            with col2:
                # Escalation patterns - using aggregated data
                if not scatter_df.empty:
                    fig = px.scatter(
                        scatter_df,
                        x='RESOLUTION_RATE',
                        y='ESCALATION_RATE',
                        size='CALL_COUNT',
                        color='PRIMARY_INTENT',
                        title="Resolution vs Escalation Patterns"
                    )
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No data available for scatter plot.")

    with tab2:
        st.subheader("Anomaly Detection")

        # Load cached anomaly detection data
        anomalies_df = load_anomaly_detection()

        if not anomalies_df.empty:
            st.write("**🚨 Detected Anomalies:**")
            st.dataframe(
                anomalies_df.style.format({
                    'SENTIMENT_SCORE': '{:.3f}',
                    'AGENT_PERFORMANCE_SCORE': '{:.1f}'
                }),
                use_container_width=True
            )

            # Anomaly distribution
            fig = px.histogram(
                anomalies_df,
                x='ANOMALY_TYPE',
                title="Distribution of Anomaly Types"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No significant anomalies detected in the current dataset.")

    with tab3:
        st.subheader("AI-Generated Recommendations")

        # Load cached recommendations
        rec_result = load_recommendations()
        if not rec_result.empty:
            row = rec_result.iloc[0]
            recommendations = safe_get_column(row, 'recommendations', 'No recommendations available')
            st.markdown(recommendations)

def show_audio_explorer():
    st.header("🎵 Audio Explorer")

    # Get available calls
    calls_query = f"""
    SELECT
        call_id as CALL_ID,
        agent_name as AGENT_NAME,
        customer_name as CUSTOMER_NAME,
        primary_intent as PRIMARY_INTENT,
        sentiment_category as SENTIMENT_CATEGORY,
        customer_satisfaction as CUSTOMER_SATISFACTION,
        ROUND(sentiment_score, 3) as SENTIMENT_SCORE,
        ROUND(agent_performance_score, 1) as AGENT_PERFORMANCE_SCORE,
        LEFT(transcript_text, 200) || '...' as PREVIEW
    FROM {current_db}.{current_schema}.comprehensive_call_analysis
    WHERE transcript_text IS NOT NULL
    ORDER BY analysis_timestamp DESC
    LIMIT 20
    """

    calls_df = session.sql(calls_query).to_pandas()

    if not calls_df.empty:
        # Call selector
        st.subheader("📞 Select a Call to Analyze")

        # Filters
        col1, col2, col3 = st.columns(3)

        with col1:
            intent_filter = st.selectbox(
                "Filter by Intent",
                ["All"] + sorted(calls_df['PRIMARY_INTENT'].dropna().unique().tolist())
            )

        with col2:
            sentiment_filter = st.selectbox(
                "Filter by Sentiment",
                ["All"] + sorted(calls_df['SENTIMENT_CATEGORY'].dropna().unique().tolist())
            )

        with col3:
            agent_filter = st.selectbox(
                "Filter by Agent",
                ["All"] + sorted(calls_df['AGENT_NAME'].dropna().unique().tolist())
            )

        # Apply filters
        filtered_df = calls_df.copy()
        if intent_filter != "All":
            filtered_df = filtered_df[filtered_df['PRIMARY_INTENT'] == intent_filter]
        if sentiment_filter != "All":
            filtered_df = filtered_df[filtered_df['SENTIMENT_CATEGORY'] == sentiment_filter]
        if agent_filter != "All":
            filtered_df = filtered_df[filtered_df['AGENT_NAME'] == agent_filter]

        # Display filtered calls
        if not filtered_df.empty:
            selected_call = st.selectbox(
                "Choose a call:",
                filtered_df['CALL_ID'].tolist(),
                format_func=lambda x: f"{x} - {filtered_df[filtered_df['CALL_ID']==x]['AGENT_NAME'].iloc[0]} ({filtered_df[filtered_df['CALL_ID']==x]['PRIMARY_INTENT'].iloc[0]})"
            )

            # Call details
            call_data = filtered_df[filtered_df['CALL_ID'] == selected_call].iloc[0]

            col1, col2 = st.columns([1, 2])

            with col1:
                st.subheader("📋 Call Details")
                st.write(f"**Call ID:** {safe_get_column(call_data, 'CALL_ID', 'N/A')}")
                st.write(f"**Agent:** {safe_get_column(call_data, 'AGENT_NAME', 'N/A')}")
                st.write(f"**Customer:** {safe_get_column(call_data, 'CUSTOMER_NAME', 'N/A')}")
                st.write(f"**Intent:** {safe_get_column(call_data, 'PRIMARY_INTENT', 'N/A')}")
                st.write(f"**Sentiment:** {safe_get_column(call_data, 'SENTIMENT_CATEGORY', 'N/A')}")
                st.write(f"**Satisfaction:** {safe_get_column(call_data, 'CUSTOMER_SATISFACTION', 'N/A')}")

                # Metrics
                st.metric("Sentiment Score", safe_get_column(call_data, 'SENTIMENT_SCORE', 0))
                st.metric("Agent Performance", f"{safe_get_column(call_data, 'AGENT_PERFORMANCE_SCORE', 0)}/10")

            with col2:
                st.subheader("📝 Full Transcript")

                # Get full transcript
                full_transcript_query = f"""
                SELECT transcript_text, call_summary, improvement_opportunities
                FROM {current_db}.{current_schema}.comprehensive_call_analysis
                WHERE call_id = '{selected_call}'
                """

                transcript_data = session.sql(full_transcript_query).to_pandas()
                if not transcript_data.empty:
                    transcript_row = transcript_data.iloc[0]

                    # Transcript tabs
                    tab1, tab2, tab3 = st.tabs(["📄 Transcript", "📝 Summary", "💡 Improvements"])

                    with tab1:
                        st.text_area(
                            "Full Conversation:",
                            safe_get_column(transcript_row, 'transcript_text', 'No transcript available'),
                            height=400,
                            disabled=True
                        )

                    with tab2:
                        st.write(safe_get_column(transcript_row, 'call_summary', 'No summary available'))

                    with tab3:
                        st.write(safe_get_column(transcript_row, 'improvement_opportunities', 'No improvement opportunities available'))
                else:
                    st.warning("No transcript data found for this call.")
        else:
            st.info("No calls found matching the selected filters.")
    else:
        st.info("📊 **No call data available** - Please load your call center data to begin analysis.")

if __name__ == "__main__":
    main()
