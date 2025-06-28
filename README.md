# 🤖 EY Project - AI-Powered Operations Research Platform

A comprehensive AI-powered platform with Angular frontend and FastAPI backend, featuring LangGraph agents, SQL integration, and advanced file management capabilities for operations research projects.

## 🚀 Architecture

- **Frontend**: Angular 16 with TypeScript - Modern, responsive web interface
- **Backend**: FastAPI with Python - High-performance async API with LangGraph agents
- **AI Integration**: OpenAI GPT + Google Gemini with LangGraph multi-agent workflows
- **Database**: SQL with Vanna AI integration for natural language queries
- **Communication**: RESTful API with real-time features

## ✨ Key Features

### 🧠 **Intelligent AI Agents**
- **Multi-Agent System**: LangGraph-powered agents for different tasks
- **Context-Aware**: Agents understand your project files and database structure
- **SQL Intelligence**: Vanna AI integration for natural language SQL queries
- **Human-in-the-Loop**: Approval workflows for critical operations

### 📁 **Advanced File Management**
- **Project Upload**: Upload entire project folders as zip files
- **Interactive File Tree**: Navigate and manage your project structure
- **Real-time Editor**: Edit files directly in the browser with syntax highlighting
- **Code Execution**: Run Python scripts with full output capture

### 🗄️ **Database Integration**
- **Modern SQL Browser**: Complete SQLite database viewer with Material Design interface
- **Advanced Search & Filtering**: Real-time search across all columns with instant results
- **Complete Table Display**: View entire database tables with pagination, sorting, and virtual scrolling
- **Custom SQL Queries**: Execute any SQL query with syntax highlighting and results display
- **Natural Language Queries**: Ask questions about your data in plain English via Vanna AI
- **Data Modification**: Update and insert data through AI assistance
- **Multiple Export Formats**: Download as .db, SQL, or CSV formats
- **Performance Optimized**: Handles large datasets efficiently with Material Design components

### 🔄 **Parameter Synchronization**
- **Real-time Parameter Updates**: Models automatically use the latest parameters from the database
- **Excel to Database Conversion**: Excel files are converted to SQLite tables for instant access
- **Parameter Validation**: Automatic verification that parameter changes are properly applied
- **Model Compatibility**: Ensures models read from database instead of files
- **Change Tracking**: Complete history of parameter modifications with before/after snapshots
- **Execution Monitoring**: Tracks which parameters are used during model execution

### 🤖 **Chat Interface**
- **Action-Based Chat**: Specialized workflows for different types of requests
- **Persistent Memory**: Conversation history and context retention
- **Approval System**: Review and approve AI-suggested changes
- **Multi-Model Support**: Switch between OpenAI and Google AI models

## 🛠️ Quick Setup

### 1. Install Dependencies
```bash
# Backend
install_backend.bat

# Frontend  
install_frontend.bat
```

### 2. Configure Environment
Create or update `EY.env`:
```
OPENAI_API_KEY=your_openai_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
```

### 3. Start the Application
```bash
# Single command to launch everything
launch.bat
```

### 4. Access the Application
- **Frontend**: http://localhost:4200
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## 📚 Documentation

- **[Frontend Startup Guide](docs/FRONTEND_STARTUP_GUIDE.md)** - Detailed frontend setup instructions
- **[Setup Guide](docs/SETUP_GUIDE.md)** - Comprehensive setup documentation  
- **[SQL Integration Guide](docs/SQL_INTEGRATION_GUIDE.md)** - Database and SQL features
- **[Parameter Synchronization Guide](docs/PARAMETER_SYNCHRONIZATION_GUIDE.md)** - Parameter management and model synchronization
- **[Implementation Docs](docs/)** - Technical implementation details

### 📖 Additional Documentation
- **[Database Browser Implementation](docs/DATABASE_BROWSER_IMPLEMENTATION.md)** - Database UI features
- **[Human-in-Loop Implementation](docs/HUMAN_IN_LOOP_IMPLEMENTATION_SUMMARY.md)** - Approval workflows
- **[LangGraph Memory Implementation](docs/LANGGRAPH_MEMORY_IMPLEMENTATION.md)** - Agent memory system
- **[Chat Persistence Implementation](docs/CHAT_PERSISTENCE_IMPLEMENTATION.md)** - Chat history features
- **[Action System Implementation](docs/ACTION_SYSTEM_IMPLEMENTATION.md)** - Action-based workflows

## 🎯 Usage Examples

### Parameter Management
1. Upload your Excel files with parameters
2. Ask: *"Change the maximum hub demand to 25000"*
3. System updates database and validates the change
4. Models automatically use the new parameter values

### Project Analysis
1. Upload your project as a zip file
2. Ask: *"Analyze my project structure and suggest improvements"*
3. The AI agent will review all files and provide insights

### Database Queries
1. Upload a database file or create tables
2. Ask: *"Show me all customers who made purchases last month"*
3. Vanna AI converts your question to SQL and shows results

### Code Development
1. Upload your code project
2. Ask: *"Add error handling to my main function"*
3. The AI will modify your files with proper error handling

### Data Analysis
1. Upload CSV files or connect to a database
2. Ask: *"Create a visualization of sales trends"*
3. AI generates Python code and executes it to create charts

## 🔧 Advanced Features

### LangGraph Agent System
- **Data Analyst**: Main intelligence agent for SQL queries, visualizations, and database modifications
- **Database Modifier**: Specialized agent for parameter changes with human approval
- **Human Approval**: Critical operations require user confirmation

### Multi-Model AI Support
- Switch between OpenAI GPT and Google Gemini
- Model-specific optimizations for different tasks
- Fallback systems for reliability

### Memory and Persistence
- Conversation history across sessions
- File change tracking
- Database modification logging
- Action approval history

### Parameter Synchronization System
- **ModelParameterSync**: Comprehensive parameter tracking and validation
- **Real-time Updates**: Instant parameter availability to models
- **Change History**: Complete audit trail of parameter modifications
- **Compatibility Checking**: Ensures models use database access

## 🛡️ Security & Safety

- **Sandboxed Execution**: Code runs in isolated environments
- **User Approval**: Critical operations require explicit approval
- **Data Privacy**: All processing happens locally or through secure APIs
- **Access Control**: No access to system files outside project scope

## 🔄 Development Workflow

1. **Upload Project**: Start with your existing codebase
2. **Explore**: Use the file browser and database explorer
3. **Modify Parameters**: Update model parameters through chat or database browser
4. **Query**: Ask questions about your code or data
5. **Iterate**: Make changes through AI assistance
6. **Execute**: Run and test your code directly in the platform

---

**Transform your operations research workflow with AI assistance!** 🚀 