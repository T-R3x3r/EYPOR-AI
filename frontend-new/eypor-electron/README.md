# EYPOR Electron Frontend

A modern Angular-based frontend for the EYPOR data analysis application, designed specifically for Electron desktop deployment.

## Features

### 🎨 **Modern UI Design**
- Clean, professional interface optimized for data analysis
- Native dark mode support with smooth transitions
- Responsive design that works on all screen sizes
- CSS custom properties for easy theming

### 📊 **Layout Structure**
- **Top Bar**: Scenario selector with horizontal scrolling
- **Left Sidebar**: Uploaded files and user queries with expandable elements
- **Center Area**: Workbench (visualizations) and Database views
- **Right Sidebar**: Permanent chat interface

### 🔧 **Key Components**

#### **Scenario Management**
- Horizontal scrolling scenario tabs
- Create new scenarios with the + button
- Active scenario highlighting

#### **File Management**
- **Uploaded Files**: Expandable file list with download/delete actions
- **User Queries**: Expandable query history showing generated files
- File type icons and metadata display

#### **Workbench**
- Large visualization area for Plotly charts
- Clean display without file containers
- Code execution output display
- Demo functionality for testing

#### **Database View**
- Table listing with whitelist management
- Column details and data types
- Clean, professional styling

#### **Chat Interface**
- Permanent right-sidebar chat
- Real-time message display
- Typing indicators
- Message history

### 🌙 **Dark Mode Support**
- Automatic theme detection
- Manual toggle in header
- Smooth transitions between themes
- All components support both light and dark modes

## Development

### Prerequisites
- Node.js 16+
- Angular CLI 16+

### Installation
```bash
cd frontend-new/eypor-electron
npm install
```

### Development Server
```bash
npm start
```
The app will be available at `http://localhost:4200`

### Build for Production
```bash
npm run build
```

## Architecture

### Component Structure
```
app/
├── components/
│   ├── uploaded-files/     # File management
│   ├── user-queries/       # Query history
│   ├── workbench/          # Main visualization area
│   ├── database-view/      # Database interface
│   └── chat-interface/     # AI chat
├── services/
│   └── theme.service.ts    # Theme management
└── models/                 # TypeScript interfaces
```

### Styling Approach
- **CSS Custom Properties**: Theme variables for easy customization
- **Component-scoped styles**: Each component has its own CSS
- **Global styles**: Common utilities and overrides
- **Responsive design**: Mobile-first approach

### State Management
- Component-level state management
- Service-based data sharing
- Reactive forms for user input
- Observable patterns for real-time updates

## Integration with Backend

The frontend is designed to work with the existing FastAPI backend:

- **API Endpoints**: Compatible with existing backend routes
- **File Management**: Integrates with upload/download services
- **Chat Interface**: Connects to LangGraph agent
- **Database**: SQLite integration for scenarios

## Electron Integration

This frontend is optimized for Electron:

- **File System Access**: Direct file operations
- **Native Dialogs**: File upload/download dialogs
- **System Integration**: Menu bar and native features
- **Offline Capability**: Works without internet connection

## Future Enhancements

### Planned Features
- **Settings Page**: User preferences and configuration
- **File Upload Page**: Dedicated upload interface
- **Advanced Visualizations**: More chart types
- **Export Options**: PDF, Excel, etc.
- **Keyboard Shortcuts**: Power user features

### Third Theme Support
The CSS variable system makes it easy to add additional themes:
- High contrast mode
- Custom brand themes
- Accessibility-focused themes

## Contributing

1. Follow Angular style guide
2. Use TypeScript strict mode
3. Write component tests
4. Maintain dark mode compatibility
5. Test responsive design

## License

This project is part of the EYPOR data analysis platform. 