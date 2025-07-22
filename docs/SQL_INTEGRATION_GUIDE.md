# SQL Database Integration (2024)

## Overview
EYProject automatically converts uploaded CSV and Excel data files into a scenario-specific SQLite database. All SQL operations, queries, and modifications are routed through the current scenario context. The agent can generate SQL from natural-language requests, execute it, and return formatted results or visualizations.

---

## Key Benefits
- **Automatic conversion:** CSV and Excel sheets become tables in the scenario database
- **Natural-language queries:** Ask "Show the top 10 hubs by demand" and the agent writes and executes the SQL
- **Safe modifications:** Update values through conversational requests ("Set opening_cost to 5000") with validation
- **Scenario isolation:** Each scenario has its own database, ensuring data separation and reproducibility

---

## How It Works
1. **File Upload**
   - Data files in the uploaded ZIP are analyzed
   - Each CSV/Excel sheet is imported as a table with correct column types
   - A summary of created tables is returned
2. **Code Transformation**
   - Python files that use Pandas file reads (`read_csv`, `read_excel`) are updated to use SQL helper calls
   - Original source files are preserved alongside SQL-enabled copies
3. **Query Execution**
   - The agent examines the user message; if it's a query, it generates SQL, validates it against the schema, executes it, and streams results to the frontend
4. **Database Modification**
   - For parameter changes, the agent generates safe `UPDATE` statements, runs them, and logs the change in the scenario context

---

## SQL Helper Functions
All transformed Python code uses helpers like:
```python
import sqlite3, pandas as pd

DB_PATH = r"/absolute/path/to/scenario_database.db"

def query_table(sql: str, params: tuple | None = None):
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(sql, conn, params=params)

def execute_sql(sql: str, params: tuple | None = None):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(sql, params or [])
        conn.commit()
```

---

## Main API Endpoints
| Method | Path | Purpose |
|--------|------|---------|
| POST   | `/sql/execute` | Execute raw SQL (body field `sql`) in the current scenario's database |
| GET    | `/database/info` | List tables and basic metadata for the current scenario |
| GET    | `/database/tables/{table}/schema` | Detailed schema for a table |
| GET    | `/database/download` | Download the current scenario's database |

---

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
→ Change is logged in the scenario context.
```

---

## Integration Notes
- All SQL/database operations are scenario-aware; each scenario has its own database
- The agent keeps an in-memory cache of the schema to minimize database hits
- All queries are parameterized to prevent SQL injection
- If generated SQL fails validation, the agent explains the error and asks for clarification

---
**Last Updated:** 2025-07-10 