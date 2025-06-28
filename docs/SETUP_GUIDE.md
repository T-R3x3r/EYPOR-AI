# Setup Guide - ChatGPT File Editor Angular Migration

This guide will walk you through setting up the complete Angular application with FastAPI backend.

## Quick Start

### Step 1: Install Backend Dependencies
```bash
# Run the batch file (Windows)
install_backend.bat

# Or manually
cd backend
pip install -r requirements.txt
```

### Step 2: Install Frontend Dependencies
```bash
# Run the batch file (Windows)
install_frontend.bat

# Or manually
cd frontend
npm install
```

### Step 3: Start the Backend Server
```bash
# Run the batch file (Windows)
start_backend.bat

# Or manually
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Step 4: Start the Frontend Server
```bash
# Run the batch file (Windows)
start_frontend.bat

# Or manually
cd frontend
npm start
```

### Step 5: Access the Application
- **Frontend**: http://localhost:4200
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## Detailed Setup

### Prerequisites Check

1. **Python 3.8+**
   ```bash
   python --version
   ```

2. **Node.js 16+**
   ```bash
   node --version
   npm --version
   ```

3. **Environment File**
   - Ensure `EY.env` exists in the root directory
   - Contains: `OPENAI_API_KEY=your_api_key_here`

### Backend Configuration

The FastAPI backend provides:
- File upload and management
- Code execution
- ChatGPT integration
- RESTful API endpoints

**Key Features:**
- Automatic CORS configuration for Angular
- File content reading with encoding detection
- Safe file writing operations
- ChatGPT context building with file contents
- File edit request parsing and execution

### Frontend Configuration

The Angular frontend provides:
- Modern, responsive UI
- Real-time file management
- Interactive chat interface
- File editing capabilities

**Key Features:**
- Component-based architecture
- TypeScript for type safety
- Custom CSS styling (no emojis)
- API service for backend communication
- Error handling and loading states

## Testing the Setup

### 1. Test Backend
1. Start the backend server
2. Visit http://localhost:8000/docs
3. You should see the FastAPI interactive documentation

### 2. Test Frontend
1. Start the frontend server
2. Visit http://localhost:4200
3. You should see the ChatGPT File Editor interface

### 3. Test Integration
1. Upload a zip file with some Python code
2. Try running a Python file
3. Start a chat with ChatGPT
4. Test file editing functionality

## Troubleshooting

### Backend Issues

**Port 8000 already in use:**
```bash
# Find the process using port 8000
netstat -ano | findstr :8000
# Kill the process or change the port in start_backend.bat
```

**Module not found errors:**
```bash
cd backend
pip install -r requirements.txt --force-reinstall
```

**OpenAI API key issues:**
- Check that `EY.env` contains a valid API key
- Ensure the file is in the root directory
- Restart the backend server after changes

### Frontend Issues

**Port 4200 already in use:**
```bash
# Angular will automatically try the next available port
# Or manually specify a different port
npm start -- --port 4201
```

**Module not found errors:**
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

**CORS errors:**
- Ensure backend is running on port 8000
- Check that CORS is properly configured in main.py
- Restart both servers

### Common Solutions

1. **Clear cache and reinstall:**
   ```bash
   # Backend
   cd backend
   pip cache purge
   pip install -r requirements.txt
   
   # Frontend
   cd frontend
   npm cache clean --force
   rm -rf node_modules package-lock.json
   npm install
   ```

2. **Check file permissions:**
   - Ensure you have write permissions in the project directory
   - Run as administrator if needed (Windows)

3. **Network issues:**
   - Check firewall settings
   - Ensure localhost is accessible
   - Try different ports if needed

## Development Workflow

### Making Changes

1. **Backend changes:**
   - Edit files in the `backend/` directory
   - Server will auto-reload with `--reload` flag
   - Check http://localhost:8000/docs for API changes

2. **Frontend changes:**
   - Edit files in the `frontend/src/` directory
   - Angular will auto-reload in development mode
   - Check browser console for errors

### Adding New Features

1. **New API endpoint:**
   - Add to `backend/main.py`
   - Update `frontend/src/app/services/api.service.ts`
   - Test with the API documentation

2. **New component:**
   - Create in `frontend/src/app/components/`
   - Add to `app.module.ts`
   - Update routing if needed

3. **New styling:**
   - Add to component-specific CSS files
   - Or update `frontend/src/styles.css` for global styles

## Production Deployment

### Backend Deployment
- Use a production ASGI server like Gunicorn
- Set up proper environment variables
- Configure CORS for production domain
- Set up logging and monitoring

### Frontend Deployment
- Build the production version: `npm run build`
- Serve static files from a web server
- Configure API base URL for production
- Set up HTTPS and security headers

## Support

If you encounter issues:
1. Check this setup guide
2. Review the troubleshooting section
3. Check the browser console for errors
4. Verify all dependencies are installed
5. Ensure both servers are running

The application should now be fully functional with the same capabilities as the original Streamlit version but with a modern, professional web interface. 