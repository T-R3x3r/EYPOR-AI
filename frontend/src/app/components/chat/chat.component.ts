import { Component, OnInit, ViewChild, ElementRef, AfterViewChecked, Output, EventEmitter } from '@angular/core';
import { ApiService } from '../../services/api.service';
import { ExecutionService } from '../../services/execution.service';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  sql?: string;
  results?: any[];
  row_count?: number;
  is_general_response?: boolean;
}

interface SQLResponse {
  success: boolean;
  message?: string;
  sql?: string;
  results?: any[];
  row_count?: number;
  error?: string;
  is_general_response?: boolean;
}

@Component({
  selector: 'app-chat',
  templateUrl: './chat.component.html',
  styleUrls: ['./chat.component.css']
})
export class ChatComponent implements OnInit, AfterViewChecked {
  @ViewChild('messagesContainer') messagesContainer!: ElementRef;
  @Output() filesCreated = new EventEmitter<void>();

  currentMessage: string = '';
  messages: ChatMessage[] = [];
  isLoading: boolean = false;
  showDebugInfo = false;
  shouldAutoScroll = true;
  private lastMessageCount = 0;
  private currentThreadId = 'default';
  suggestions: string[] = [
    "How many rows are in each table?",
    "Show me the top 10 records from the main table", 
    "What's the total count by category?",
    "Find all records where value > 100",
    "Which table has the most data?",
    "Compare totals across different groups"
  ];

  constructor(
    private apiService: ApiService,
    private executionService: ExecutionService
  ) {}

  ngOnInit(): void {
    this.addWelcomeMessage();
    this.lastMessageCount = this.messages.length;
  }

  ngAfterViewChecked() {
    // Only auto-scroll if new messages were added and user hasn't manually scrolled up
    if (this.messagesContainer && this.shouldAutoScroll && this.messages.length > this.lastMessageCount) {
      const element = this.messagesContainer.nativeElement;
      element.scrollTop = element.scrollHeight;
      this.lastMessageCount = this.messages.length;
    }
  }

  addWelcomeMessage() {
    this.messages.push({
      role: 'assistant',
      content: `🤖 **Advanced Data Analyst**

Welcome! I'm your intelligent data analyst that automatically routes requests through specialized workflows. I can handle SQL queries, create visualizations, and manage database modifications.

**🔄 How I Work:**
I analyze your request and automatically route it to the appropriate workflow:
- **SQL Queries** → Direct execution with formatted results
- **Visualizations** → Python script creation and execution
- **Database Changes** → Direct execution with detailed change tracking

**📊 SQL Query Examples:**
- "Show me the top 10 hubs with highest demand"
- "What is the total supply capacity by region?"
- "List all routes with cost > 500"
- "Find hubs with demand exceeding 15000"
- "Compare opening costs across all locations"

**📈 Visualization Examples:**
- "Create a bar chart of hub demands"
- "Visualize cost distribution across routes"
- "Show a map of all hub locations"
- "Plot demand vs supply capacity"
- "Generate a heatmap of route usage"

**⚙️ Database Modification Examples:**
- "Change maximum hub demand to 20000"
- "Update route supply limit to 15000"
- "Set opening cost to 5000"
- "Modify hub capacity parameter to 25000"
- "Adjust transportation cost factor to 1.5"

**📍 Table-Specific Modifications:**
- "Change maximum demand to 20000 in inputs_params"
- "Update cost to 500 in routes table" 
- "Set capacity to 15000 in hubs_data"
- "Modify value to 25000 in parameters table"

**📋 Database Change Details:**
When you request database changes, I'll show you exactly:
- Which table and column was modified
- The old value → new value
- How many rows were affected
- The exact SQL that was executed

**🔒 Safety Features:**
- Detailed change tracking for all database modifications
- Error recovery with intelligent code fixing
- Complete execution history tracking

**🎯 Smart Routing:**
I automatically determine whether you need data analysis, visualization, or parameter changes. Just ask naturally and I'll handle the rest!

Ask me anything about your data!`,
      timestamp: new Date()
    });
  }

  async sendMessage(): Promise<void> {
    if (!this.currentMessage.trim() || this.isLoading) {
      return;
    }

    const messageToSend = this.currentMessage.trim();
    this.currentMessage = '';
    this.isLoading = true;

    // Add user message
    this.messages.push({
      role: 'user',
      content: messageToSend,
      timestamp: new Date()
    });

    // Reset auto-scroll when sending a new message
    this.shouldAutoScroll = true;

    try {
      // Call LangGraph API with the simple schema agent
      console.log('Calling LangGraph API with message:', messageToSend);
      
      this.apiService.langGraphChat(messageToSend).subscribe({
        next: (response) => {
          console.log('LangGraph response received:', response);
          
          // Add assistant response
          const assistantMessage: ChatMessage = {
            role: 'assistant',
            content: response.response || 'No response received',
            timestamp: new Date()
          };
          
          this.messages.push(assistantMessage);
          
          // Handle execution results and output files
          if (response.has_execution_results || response.output_files) {
            console.log('Processing execution results:', response);
            
            // Emit execution result for output display component
            const executionResult = {
              command: 'Visualization Script Execution',
              output: response.execution_output || '',
              error: response.execution_error || '',
              returnCode: response.execution_error ? 1 : 0,
              outputFiles: response.output_files || []
            };
            
            this.executionService.emitExecutionResult(executionResult);
            console.log('Emitted execution result with output files:', response.output_files);
          }
          
          // Emit files created event if files were created
          if (response.created_files && response.created_files.length > 0) {
            this.filesCreated.emit();
          }
          
          this.isLoading = false;
          this.scrollToBottom();
        },
        error: (error) => {
          console.error('LangGraph API error:', error);
          
          let errorMessage = 'Unable to process your request.';
          if (error.error?.error) {
            errorMessage = error.error.error;
          } else if (error.message) {
            errorMessage = error.message;
          }
          
          this.messages.push({
            role: 'assistant',
            content: `❌ **Error**: ${errorMessage}

**Possible solutions:**
- Make sure you've uploaded a SQLite database file (.db)
- Check if the backend server is running
- Verify your API keys are configured correctly
- Try asking a simpler question about the database structure`,
            timestamp: new Date()
          });
          
          this.isLoading = false;
          this.scrollToBottom();
        }
      });

    } catch (error) {
      console.error('Error in sendMessage:', error);
      this.messages.push({
        role: 'assistant',
        content: `❌ **Error**: Failed to send message to the assistant.

Please check your connection and try again.`,
        timestamp: new Date()
      });
      this.isLoading = false;
      this.scrollToBottom();
    }
  }

  useSuggestion(suggestion: string) {
    this.currentMessage = suggestion;
  }

  onEnterKey(event: Event) {
    const keyboardEvent = event as KeyboardEvent;
    if (!keyboardEvent.shiftKey) {
      event.preventDefault();
      this.sendMessage();
    }
  }

  clearChat() {
    this.messages = [];
    this.addWelcomeMessage();
  }

  toggleDebugInfo() {
    this.showDebugInfo = !this.showDebugInfo;
  }

  exportChat() {
    const chatData = {
      exported_at: new Date().toISOString(),
      total_messages: this.messages.length,
      messages: this.messages
    };

    const blob = new Blob([JSON.stringify(chatData, null, 2)], { type: 'application/json' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'sql_chat_history.json';
    link.click();
    window.URL.revokeObjectURL(url);
  }

  formatContent(content: string): string {
    // Simple formatting for better display
    return content.replace(/\n/g, '<br>');
  }

  scrollToBottom() {
    if (this.messagesContainer) {
      const element = this.messagesContainer.nativeElement;
      element.scrollTop = element.scrollHeight;
    }
  }

  onScroll(event: Event) {
    if (this.messagesContainer) {
      const element = this.messagesContainer.nativeElement;
      const isScrolledToBottom = element.scrollHeight - element.clientHeight <= element.scrollTop + 1;
      this.shouldAutoScroll = isScrolledToBottom;
    }
  }


} 