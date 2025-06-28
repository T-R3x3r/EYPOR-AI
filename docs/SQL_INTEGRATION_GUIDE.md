# 🗄️ SQL Database Integration with Vanna AI

## Overview

This project has been upgraded to use an **SQL-based approach** that automatically converts uploaded CSV and Excel files into SQLite databases and transforms Python code to work with SQL queries. This integration includes the powerful **Vanna AI framework** for natural language to SQL generation, significantly improving efficiency and reducing token usage.

## 🎯 Key Benefits

### ✅ **Automatic Data Conversion**
- **CSV files** → SQL tables with proper schema detection
- **Excel files** → Multiple SQL tables (one per sheet)
- **Python files** → Automatically transformed to use SQL queries instead of file operations

### ✅ **Natural Language Queries**
- Ask questions in plain English: *"What is the average sales by region?"*
- Vanna AI generates optimized SQL queries automatically
- No need to remember complex SQL syntax

### ✅ **Reduced Token Usage**
- Database schema and sample data are stored in vector database
- Only relevant context is sent to the LLM
- Faster responses and lower API costs

### ✅ **Easy Data Modification**
- Update database values through natural language or simple forms
- Insert new records without writing SQL
- Changes immediately reflect in subsequent queries

## 🚀 How It Works

### 1. **File Upload & Conversion**
When you upload a ZIP file containing data files:

```
Original Files:
├── sales_data.csv
├── customer_info.xlsx  
└── analysis.py

Automatically Becomes:
├── project_data.db (SQLite database)
│   ├── sales_data (table)
│   ├── customer_info (table)
│   └── customer_info_sheet2 (if multiple sheets)
├── analysis_sql.py (transformed Python code)
└── Original files (preserved)
```

### 2. **Code Transformation**
Python code is automatically updated to use SQL:

**Before:**
```python
import pandas as pd
df = pd.read_csv('sales_data.csv')
result = df.groupby('region')['sales'].mean()
```

**After:**
```python
import pandas as pd
import sqlite3

def get_db_connection():
    return sqlite3.connect(r"/path/to/project_data.db")

def query_table(query, params=None):
    conn = get_db_connection()
    try:
        return pd.read_sql_query(query, conn, params=params)
    finally:
        conn.close()

# Transformed code
df = pd.read_sql_query("SELECT * FROM sales_data", sqlite3.connect(r"/path/to/project_data.db"))
result = df.groupby('region')['sales'].mean()
```

### 3. **Vanna AI Training**
- Database schema is automatically analyzed
- Sample data is used to train the AI model
- Vector database stores learned patterns for fast retrieval

## 🔧 Using the SQL Interface

### **Query Tab - Natural Language Queries**

1. **Ask Questions in Plain English:**
   ```
   Examples:
   • "Show me all customers from New York"
   • "What are the top 5 products by sales?"
   • "Calculate monthly revenue trends"
   • "Which regions have the highest growth?"
   ```

2. **View Generated SQL:**
   - See the automatically generated SQL query
   - Understand how your question was interpreted
   - Copy SQL for reuse in your own code

3. **Export Results:**
   - Download query results as CSV
   - Use data in external tools
   - Share insights with stakeholders

### **Database Info Tab - Explore Your Data**

1. **Database Overview:**
   - See all available tables
   - View table schemas and data types
   - Check row counts and sample data

2. **Table Details:**
   - Click on any table to see detailed schema
   - Preview sample data
   - Understand data structure

### **Modify Data Tab - Update Information**

1. **Update Existing Records:**
   ```
   Table: customers
   Updates: {"status": "active", "last_contact": "2024-01-15"}
   Condition: "region = 'East'"
   ```

2. **Insert New Records:**
   ```
   Table: products
   Data: {"name": "New Product", "price": 99.99, "category": "Electronics"}
   ```

## 📚 API Endpoints

The system provides comprehensive REST API endpoints:

### **Query Endpoints**
- `POST /sql/query` - Natural language to SQL query
- `GET /sql/suggestions` - Get suggested questions
- `POST /sql/execute` - Execute raw SQL

### **Database Management**
- `GET /database/info` - Database schema and tables
- `GET /database/summary` - Comprehensive database overview
- `GET /database/tables/{table}/schema` - Specific table details

### **Data Modification**
- `POST /data/update` - Update existing records
- `POST /data/insert` - Insert new records

### **AI Training**
- `POST /vanna/train` - Add custom training data
- `GET /sql/mode` - Check SQL system status

## 💡 Advanced Features

### **Custom Training**
Improve Vanna AI by adding your own question-SQL pairs:

```python
# Add domain-specific training
vanna.train(
    question="Show high-value customers",
    sql="SELECT * FROM customers WHERE total_purchases > 10000",
    documentation="High-value customers are those with purchases over $10,000"
)
```

### **Visualization Support**
Vanna can generate visualization code for your queries:

```python
# Example generated visualization
import plotly.express as px
fig = px.bar(df, x='region', y='sales', title='Sales by Region')
fig.show()
```

### **Python Code Integration**
Use the SQL helper functions in your transformed Python code:

```python
# Query data
sales_data = query_table("SELECT * FROM sales_data WHERE date >= ?", ["2024-01-01"])

# Execute updates
execute_sql("UPDATE products SET price = price * 1.1 WHERE category = 'Electronics'")

# Get database info
tables = get_available_tables()
```

## 🔒 Technical Architecture

### **Components:**
1. **SQLConverter** - Handles file conversion and code transformation
2. **VannaSQL** - Manages AI training and query generation
3. **ChromaDB** - Vector database for fast context retrieval
4. **SQLite** - Local database for data storage

### **Dependencies Added:**
```txt
pandas>=2.0.0
vanna>=0.3.0
sqlite3-utils>=3.0.0
openpyxl>=3.1.0
astor>=0.8.1
chromadb>=0.4.0
```

## 🎯 Best Practices

### **Writing Effective Questions**
- Be specific about what you want to see
- Mention table names when dealing with multiple tables
- Use business terms that match your column names
- Ask for clarification if results don't match expectations

### **Data Quality**
- Ensure CSV files have proper headers
- Use consistent data types within columns
- Clean data before upload for best results
- Provide meaningful column names

### **Performance Tips**
- Use LIMIT clauses for large datasets
- Create indexes for frequently queried columns
- Train Vanna with common question patterns
- Cache frequently used queries

## 🚨 Migration Notes

### **Backward Compatibility**
- Original files are preserved alongside SQL versions
- Existing workflows continue to work
- New SQL features are optional enhancements

### **Upgrading Existing Projects**
1. Re-upload your ZIP files to trigger conversion
2. Review transformed Python code
3. Test SQL queries against your data
4. Train Vanna with project-specific questions

## 🔍 Troubleshooting

### **Common Issues:**

**Vanna not responding:**
- Check if database contains data
- Verify API keys are configured
- Retrain Vanna with more examples

**SQL conversion failed:**
- Ensure CSV files are well-formatted
- Check for special characters in column names
- Verify Python code uses standard pandas operations

**Query returns empty results:**
- Check table names and column names
- Verify data was imported correctly
- Use Database Info tab to explore schema

## 📈 Example Workflows

### **Business Analytics**
```
1. Upload sales_data.csv, customers.xlsx
2. Ask: "Which customers generated the most revenue last quarter?"
3. Follow up: "Show monthly trends for top 10 customers"
4. Export results for presentation
```

### **Data Exploration**
```
1. Upload multiple related CSV files
2. Ask: "What tables do I have and how are they related?"
3. Query: "Show me sample data from each table"
4. Explore: "Find correlations between customer demographics and purchase behavior"
```

### **Operational Updates**
```
1. Query current inventory levels
2. Update product prices based on market analysis
3. Insert new customer records from recent signups
4. Generate updated reports
```

---

**Ready to explore your data with natural language?** 🚀 Upload your files and start asking questions in the SQL Database tab! 