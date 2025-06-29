import { Component, OnInit, ViewChild, ElementRef, AfterViewChecked, Output, EventEmitter, ViewEncapsulation } from '@angular/core';
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
  styleUrls: ['./chat.component.css'],
  encapsulation: ViewEncapsulation.None,
  host: {
    'class': 'app-chat-component'
  }
})
export class ChatComponent implements OnInit, AfterViewChecked {
  @ViewChild('messagesContainer') messagesContainer!: ElementRef;
  @Output() filesCreated = new EventEmitter<void>();

  currentMessage: string = '';
  messages: ChatMessage[] = [];
  isLoading: boolean = false;
  shouldAutoScroll = true;
  private lastMessageCount = 0;
  private currentThreadId = 'default';

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
      content: `**EYPOR - EY-Parthenon Operations Research AI**

Welcome! I'm EYPOR, your intelligent operations research assistant. I can help you analyze data, create visualizations, and modify database parameters.

Ready to analyze your data?`,
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
            
            // Determine command type based on response content and output files
            let commandType = 'Script Execution';
            if (response.output_files && response.output_files.length > 0) {
              commandType = 'Visualization Script Execution';
            } else if (response.execution_output && !response.execution_error) {
              commandType = 'Query Execution';
            } else if (response.execution_error) {
              commandType = 'Execution Error';
            }
            
            // Only show execution result if there's actual output/error or output files
            const hasContent = response.execution_output || response.execution_error || 
                             (response.output_files && response.output_files.length > 0);
            
            if (hasContent) {
              // Emit execution result for output display component
              const executionResult = {
                command: commandType,
                output: response.execution_output || '',
                error: response.execution_error || '',
                returnCode: response.execution_error ? 1 : 0,
                outputFiles: response.output_files || []
              };
              
              this.executionService.emitExecutionResult(executionResult);
              console.log('Emitted execution result with output files:', response.output_files);
            }
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
    // Convert markdown-style formatting to HTML
    let formatted = content;
    
    // Convert **bold** to <strong>bold</strong>
    formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    
    // Convert line breaks to <br> tags
    formatted = formatted.replace(/\n/g, '<br>');
    
    return formatted;
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