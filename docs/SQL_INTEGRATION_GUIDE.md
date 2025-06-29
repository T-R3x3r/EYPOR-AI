# 🗄️ SQL Database Integration

## Overview
EY Project automatically converts uploaded CSV and Excel data files into a single SQLite database (`project_data.db`) and rewrites Python models to query this database directly.  The LangGraph agent can then generate SQL on-the-fly from natural-language requests, execute it, and return formatted results or visualisations.

## Key Benefits
• **Automatic conversion** – CSV sheets become tables; each Excel sheet becomes its own table.  
• **Natural-language queries** – ask "Show the top 10 hubs by demand" and the agent writes and executes the SQL.  
• **Safe modifications** – update values through conversational requests ("Set opening_cost to 5000") with validation.  
• **Unified storage** – one lightweight, portable database for the whole project.  

## How It Works
1. **File Upload**  
   – Data files inside the uploaded ZIP are analysed.  
   – Each CSV/Excel sheet is imported as a table with the correct column types.  
   – A summary of the created tables is returned.
2. **Code Transformation**  
   – Any `.py` files that contain Pandas file reads (`read_csv`, `read_excel`) are updated to SQL helper calls (see below).  
   – The original source files are preserved alongside the SQL-enabled copies (`*_sql.py`).
3. **Query Execution**  
   – At run-time the LangGraph agent examines the user message.  If it is a query request it generates SQL with OpenAI, validates it against the cached schema, executes it via `sqlite3`, then streams the results back to the frontend.
4. **Database Modification**  
   – For parameter-change requests the agent generates safe `UPDATE` statements, runs them, and (if configured) triggers the human-in-the-loop model-rerun dialog.

## SQL Helper Functions
All transformed Python code imports the helpers from `backend/langgraph_agent.py`:
```python
import sqlite3, pandas as pd

DB_PATH = r"/absolute/path/to/project_data.db"

def query_table(sql: str, params: tuple | None = None):
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(sql, conn, params=params)

def execute_sql(sql: str, params: tuple | None = None):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(sql, params or [])
        conn.commit()
```

## Available API Endpoints
| Method | Path | Purpose |
|--------|------|---------|
| POST   | `/sql/execute` | Execute raw SQL (body field `sql`). |
| GET    | `/database/info` | List tables and basic metadata. |
| GET    | `/database/tables/{table}/schema` | Detailed schema for a table. |

## Example Workflows
### Natural-Language Query (Chat)
```
User: "Which regions have average demand > 10,000?"
Agent → generates SQL → executes → returns table.
```

### Direct SQL via API
```bash
curl -X POST http://localhost:8001/sql/execute \
     -F "sql=SELECT region, AVG(demand) AS avg_demand FROM inputs_params GROUP BY region HAVING avg_demand > 10000;"
```

### Parameter Update
```
User: "Change maximum_hub_demand to 20000"
→ Agent builds and runs:
   UPDATE inputs_params SET value = 20000 WHERE parameter = 'maximum_hub_demand';
→ Model-rerun dialog appears.
```

## Integration Notes
• The agent keeps an in-memory cache of the schema to minimise database hits.  
• All queries are parameterised to prevent SQL injection.  
• If the generated SQL fails validation the agent explains the error and asks for clarification.

---
**Last Updated:** 2025-06-29 