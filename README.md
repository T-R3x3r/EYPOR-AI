# 🤖 EY Project - AI-Powered Operations Research Platform

## 🎯 Overview

The EY Project is a comprehensive AI-powered platform for operations research, featuring advanced database management, visualization capabilities, and automated model execution. Built with Angular frontend and Python backend, it provides an intuitive interface for data analysis and optimization.

## 🚀 Key Features

- **Multi-Agent AI System**: Specialized agents for different operations
- **Database Integration**: Direct SQL execution and parameter management
- **Visualization Engine**: Dynamic chart and graph generation
- **Model Execution**: Automated Python model discovery and execution
- **Memory Management**: LangGraph-based conversation persistence
- **Model Selection**: User-controlled model execution after database changes

## 🏗️ Architecture

### Frontend (Angular)
- **Modern UI**: Responsive design with real-time updates
- **File Management**: Upload, edit, and organize project files
- **Chat Interface**: Natural language interaction with AI agents
- **Database Browser**: Intuitive database exploration and management
- **Model Selection**: Interactive model execution interface

### Backend (Python/FastAPI)
- **LangGraph Agents**: Multi-agent workflow orchestration
- **Database Engine**: SQLite with advanced query capabilities
- **File Processing**: Dynamic Python script execution
- **Memory System**: Persistent conversation state management
- **API Integration**: RESTful endpoints for all operations

## 🧠 AI Agents

### Data Analyst Agent (Primary)
- **Role**: Main intelligence for routing and coordination
- **Capabilities**: SQL queries, visualizations, database modifications
- **Memory**: LangGraph-based conversation persistence

### Database Modifier Agent (Specialist)
- **Role**: Specialized database parameter management
- **Capabilities**: Parameter changes, data updates, model discovery
- **Model Selection**: User-controlled model execution after changes

## 🔄 Workflow

```
User Request → Agent Classification → Specialized Processing → Results
     ↓              ↓                      ↓                    ↓
Natural Language → SQL/Visualization → Database/Model → Formatted Output
```

## 📁 Project Structure

```
EYProjectGit/
├── frontend/                 # Angular application
│   ├── src/app/
│   │   ├── components/       # UI components
│   │   ├── services/         # API services
│   │   └── pipes/           # Data transformation
│   └── package.json
├── backend/                  # Python FastAPI server
│   ├── main.py              # Main application
│   ├── langgraph_agent.py   # AI agent implementation
│   └── requirements.txt
├── docs/                    # Documentation
├── outputs/                 # Generated files
└── README.md
```

## 🛠️ Installation

### Prerequisites
- Node.js (v16+)
- Python (v3.8+)
- Git

### Quick Start
1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd EYProjectGit
   ```

2. **Install dependencies**
   ```bash
   # Install frontend dependencies
   cd frontend
   npm install
   
   # Install backend dependencies
   cd ../backend
   pip install -r requirements.txt
   ```

3. **Configure environment**
   ```bash
   # Copy environment template
   cp EY.env.example EY.env
   
   # Edit EY.env with your API keys
   nano EY.env
   ```

4. **Launch the application**
   ```bash
   # Start backend server
   cd backend
   python main.py
   
   # Start frontend (in new terminal)
   cd frontend
   ng serve
   ```

5. **Access the application**
   - Frontend: http://localhost:4200
   - Backend API: http://localhost:8000

## 🎯 Usage Examples

### Database Queries
```
User: "Show me the top 10 records from the inventory table"
System: [Formatted SQL results with pagination]
```

### Visualizations
```
User: "Create a bar chart showing sales by region"
System: [Python script generation → Chart display]
```

### Database Modifications
```
User: "Change the maximum capacity to 5000"
System: [Database update → Model discovery → Model selection dialog]
```

### Model Selection
```
User: "Update the price parameter to 15.99"
System: [Database modification → Available models listed → User selection → Execution]
```

## 🔧 Configuration

### Environment Variables
```bash
# API Configuration
OPENAI_API_KEY=your_openai_key
GOOGLE_API_KEY=your_google_key

# Database Configuration
DATABASE_PATH=./data/project.db

# Server Configuration
HOST=0.0.0.0
PORT=8000
```

### Agent Configuration
```python
# Agent types available
AGENT_TYPES = ["data_analyst", "database_modifier"]

# Memory configuration
MEMORY_TYPE = "sqlite"  # or "memory"
```

## 📚 Documentation

- **[Setup Guide](docs/SETUP_GUIDE.md)** - Complete installation instructions
- **[Frontend Guide](docs/FRONTEND_STARTUP_GUIDE.md)** - Angular development guide
- **[SQL Integration](docs/SQL_INTEGRATION_GUIDE.md)** - Database query capabilities
- **[Parameter Synchronization](docs/PARAMETER_SYNCHRONIZATION_GUIDE.md)** - Database parameter management
- **[Model Selection Implementation](docs/HUMAN_IN_LOOP_IMPLEMENTATION_SUMMARY.md)** - Model execution workflows
- **[LangGraph Memory](docs/LANGGRAPH_MEMORY_IMPLEMENTATION.md)** - Conversation persistence
- **[Agent Workflow](docs/NEW_AGENT_WORKFLOW_IMPLEMENTATION.md)** - Multi-agent architecture

## 🧪 Testing

### Backend Testing
```bash
cd backend
python -m pytest tests/
```

### Frontend Testing
```bash
cd frontend
ng test
```

### Integration Testing
```bash
# Run full system tests
python tests/integration_test.py
```

## 🔄 Development Workflow

### Adding New Features
1. **Backend**: Implement in `backend/langgraph_agent.py`
2. **API**: Add endpoints in `backend/main.py`
3. **Frontend**: Create components in `frontend/src/app/components/`
4. **Testing**: Add tests in respective test directories

### Code Style
- **Python**: PEP 8 with Black formatting
- **TypeScript**: ESLint with Angular style guide
- **Documentation**: Comprehensive docstrings and README updates

## 🚀 Deployment

### Production Setup
```bash
# Build frontend
cd frontend
ng build --prod

# Deploy backend
cd backend
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker
```

### Docker Deployment
```bash
# Build and run with Docker
docker-compose up -d
```

## 🤝 Contributing

1. **Fork the repository**
2. **Create feature branch**: `git checkout -b feature/new-feature`
3. **Commit changes**: `git commit -am 'Add new feature'`
4. **Push branch**: `git push origin feature/new-feature`
5. **Submit pull request**

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/your-repo/issues)
- **Documentation**: [Project Wiki](https://github.com/your-repo/wiki)
- **Email**: support@eyproject.com

## 🎯 Roadmap

### Phase 1 (Current)
- ✅ Multi-agent workflow implementation
- ✅ Database integration and parameter management
- ✅ Model selection and execution
- ✅ LangGraph memory system

### Phase 2 (Next)
- 🔄 Advanced visualization options
- 🔄 Real-time collaboration features
- 🔄 Batch operation support
- 🔄 Performance optimization

### Phase 3 (Future)
- 📋 Machine learning model integration
- 📋 Advanced analytics dashboard
- 📋 Mobile application
- 📋 Cloud deployment options

---

**Built with ❤️ by the EY Project Team** 