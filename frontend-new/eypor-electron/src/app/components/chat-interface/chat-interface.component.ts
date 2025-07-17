import { Component, OnInit, ViewChild, ElementRef, AfterViewChecked, HostListener, Output, EventEmitter } from '@angular/core';
import { ApiService } from '../../services/api.service';
import { ExecutionService } from '../../services/execution.service';
import { QueryFileOrganizerService } from '../../services/query-file-organizer.service';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  isLoading?: boolean;
}

@Component({
  selector: 'app-chat-interface',
  templateUrl: './chat-interface.component.html',
  styleUrls: ['./chat-interface.component.css']
})
export class ChatInterfaceComponent implements OnInit, AfterViewChecked {
  @ViewChild('messagesContainer') messagesContainer!: ElementRef;
  @ViewChild('messageInput') messageInput!: ElementRef;
  @Output() filesCreated = new EventEmitter<void>();

  messages: ChatMessage[] = [];
  currentMessage = '';
  isLoading = false;
  shouldAutoScroll = true;
  isInputAnchored = false;
  
  // AI Model Selection
  selectedModel = 'GPT-4';
  showModelDropdown = false;
  availableModels = ['GPT-4', 'GPT-3.5', 'Claude-3', 'Gemini Pro'];

  constructor(
    private apiService: ApiService,
    private executionService: ExecutionService,
    private queryFileOrganizer: QueryFileOrganizerService
  ) {}

  @HostListener('document:click', ['$event'])
  onDocumentClick(event: Event): void {
    const target = event.target as HTMLElement;
    const modelSelector = target.closest('.model-selector');
    
    if (!modelSelector) {
      this.showModelDropdown = false;
    }
  }

  ngOnInit(): void {
    this.loadChatHistory();
  }

  ngAfterViewChecked(): void {
    this.checkInputPosition();
    if (this.shouldAutoScroll) {
      this.scrollToBottom();
    }
  }

  checkInputPosition(): void {
    if (this.messagesContainer) {
      const container = this.messagesContainer.nativeElement;
      const containerHeight = container.clientHeight;
      const scrollHeight = container.scrollHeight;
      const scrollTop = container.scrollTop;
      
      // Check if we're at 2/3 of the sidebar height
      const sidebarHeight = window.innerHeight;
      const twoThirdsHeight = (sidebarHeight * 2) / 3;
      
      if (scrollHeight > twoThirdsHeight) {
        this.isInputAnchored = true;
        container.style.maxHeight = 'calc(100vh - 200px)';
        container.style.overflowY = 'auto';
      } else {
        this.isInputAnchored = false;
        container.style.maxHeight = 'none';
        container.style.overflowY = 'visible';
      }
    }
  }

  loadChatHistory(): void {
    // TODO: Load from service
    this.messages = [];
  }

  async sendMessage(): Promise<void> {
    if (!this.currentMessage.trim() || this.isLoading) {
      return;
    }

    const messageToSend = this.currentMessage.trim();
    this.currentMessage = '';
    this.isLoading = true;

    // Add user message
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: messageToSend,
      timestamp: new Date()
    };

    this.messages.push(userMessage);
    this.shouldAutoScroll = true;

    try {
      // Call LangGraph API with the v2 agent
      console.log('Calling LangGraph API with message:', messageToSend);
      
      const apiCall = this.apiService.langGraphChatV2(messageToSend);
      
      apiCall.subscribe({
        next: (response) => {
          console.log('LangGraph response received:', response);
          
          // Add assistant response
          const assistantMessage: ChatMessage = {
            id: (Date.now() + 1).toString(),
            role: 'assistant',
            content: response.response || 'No response received',
            timestamp: new Date()
          };
          
          this.messages.push(assistantMessage);
          
          // Handle execution results and output files
          if (response.has_execution_results || response.output_files || response.generated_files) {
            console.log('Processing execution results:', response);
            
            // Organize files by query (v2 agent) - only if files were actually generated
            if (response.user_query && response.generated_files && response.generated_files.length > 0) {
              console.log('Organizing files by query:', response.user_query, response.generated_files);
              this.queryFileOrganizer.addQueryFiles(
                response.user_query, 
                response.generated_files, 
                response.query_timestamp
              );
              
              // Emit files created event to trigger file tree refresh
              this.filesCreated.emit();
            } else if (response.user_query && (!response.generated_files || response.generated_files.length === 0)) {
              console.log('No files generated for query:', response.user_query);
              // Don't create a query group if no files were generated
            }
            
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
              // Convert generated files to output files format for execution service
              const outputFiles = (response.output_files || []).concat(
                (response.generated_files || []).map((filename: string) => ({
                  filename: filename,
                  path: filename,
                  url: `/files/${filename}`,
                  type: this.getFileType(filename),
                  timestamp: Date.now()
                }))
              );
              
              // Emit execution result for output display component
              const executionResult = {
                command: commandType,
                output: response.execution_output || '',
                error: response.execution_error || '',
                returnCode: response.execution_error ? 1 : 0,
                outputFiles: outputFiles,
                timestamp: Date.now()
              };
              
              this.executionService.emitExecutionResult(executionResult);
            }
          }
          
          this.isLoading = false;
          this.shouldAutoScroll = true;
        },
        error: (error) => {
          console.error('Error calling LangGraph API:', error);
          
          const errorMessage: ChatMessage = {
            id: (Date.now() + 1).toString(),
            role: 'assistant',
            content: 'Sorry, I encountered an error while processing your request. Please try again.',
            timestamp: new Date()
          };
          
          this.messages.push(errorMessage);
          this.isLoading = false;
          this.shouldAutoScroll = true;
        }
      });
    } catch (error) {
      console.error('Error in sendMessage:', error);
      this.isLoading = false;
    }
  }

  onKeyPress(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.sendMessage();
    }
  }

  onInputChange(): void {
    // Auto-expand textarea
    setTimeout(() => {
      if (this.messageInput) {
        const textarea = this.messageInput.nativeElement;
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
      }
    }, 0);
  }

  scrollToBottom(): void {
    try {
      const element = this.messagesContainer.nativeElement;
      element.scrollTop = element.scrollHeight;
    } catch (err) {
      // Ignore scroll errors
    }
  }

  onScroll(): void {
    const element = this.messagesContainer.nativeElement;
    const isAtBottom = element.scrollHeight - element.scrollTop <= element.clientHeight + 1;
    this.shouldAutoScroll = isAtBottom;
  }

  clearChat(): void {
    this.messages = [];
  }

  getMessageIconClass(role: string): string {
    return role === 'user' ? 'icon-user' : 'icon-bot';
  }

  formatTimestamp(timestamp: Date): string {
    return timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  getCurrentTime(): Date {
    return new Date();
  }

  toggleModelDropdown(event: Event): void {
    event.stopPropagation();
    this.showModelDropdown = !this.showModelDropdown;
  }

  selectModel(model: string): void {
    this.selectedModel = model;
    this.showModelDropdown = false;
    // TODO: Implement backend integration for model switching
    console.log('Selected model:', model);
  }

  private getFileType(filename: string): string {
    const extension = filename.split('.').pop()?.toLowerCase() || '';
    console.log('Chat interface getting file type for:', filename, 'Extension:', extension);
    
    switch (extension) {
      case 'html': 
        // Detect as plotly if it contains plotly, chart, or visualization in the name
        const lowerFilename = filename.toLowerCase();
        if (lowerFilename.includes('plotly') || lowerFilename.includes('chart') || lowerFilename.includes('visualization')) {
          console.log('Chat interface detected as plotly-html:', filename);
          return 'plotly-html';
        } else {
          console.log('Chat interface detected as regular html:', filename);
          return 'html'; // Regular HTML files (including charts from AI agent)
        }
      case 'png':
      case 'jpg':
      case 'jpeg':
      case 'gif':
      case 'svg': return 'image';
      case 'py': return 'python';
      case 'csv': return 'csv';
      case 'xlsx': return 'xlsx';
      default: return 'file';
    }
  }
} 