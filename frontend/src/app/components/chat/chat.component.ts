import { Component, OnInit, ViewChild, ElementRef, AfterViewChecked, Output, EventEmitter, ViewEncapsulation } from '@angular/core';
import { ApiService } from '../../services/api.service';
import { ExecutionService } from '../../services/execution.service';
import { ScenarioService } from '../../services/scenario.service';
import { Scenario } from '../../models/scenario.model';
import { QueryFileOrganizerService } from '../../services/query-file-organizer.service';

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
  currentScenario: Scenario | null = null;
  chatHistory: { scenarioId: number; messages: ChatMessage[] }[] = [];
  private lastMessageCount = 0;
  private currentThreadId = 'default';
  // Removed v1 agent toggle - now using v2 agent only

  constructor(
    private apiService: ApiService,
    private executionService: ExecutionService,
    private scenarioService: ScenarioService,
    private queryFileOrganizer: QueryFileOrganizerService
  ) {}

  ngOnInit(): void {
    this.addWelcomeMessage();
    this.lastMessageCount = this.messages.length;

    // Subscribe to scenario changes to load scenario-specific chat history
    this.scenarioService.currentScenario$.subscribe(scenario => {
      this.currentScenario = scenario;
      if (scenario) {
        this.loadScenarioChatHistory(scenario.id);
      } else {
        // Clear chat when no scenario is active
        this.messages = [];
        this.addWelcomeMessage();
        this.lastMessageCount = this.messages.length;
      }
    });
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

  // Load scenario-specific chat history
  private loadScenarioChatHistory(scenarioId: number): void {
    // For now, we'll store chat history in memory
    // In a real implementation, this would load from the backend
    console.log('Loading chat history for scenario:', scenarioId);
    
    // Check if we have cached history for this scenario
    const cachedHistory = this.chatHistory.find(h => h.scenarioId === scenarioId);
    if (cachedHistory) {
      this.messages = [...cachedHistory.messages];
      this.lastMessageCount = this.messages.length;
    } else {
      // Initialize with welcome message for new scenario
      this.messages = [];
      this.addWelcomeMessage();
      this.lastMessageCount = this.messages.length;
    }
  }

  // Save current chat to history
  private saveChatToHistory(): void {
    if (this.currentScenario) {
      const existingIndex = this.chatHistory.findIndex(h => h.scenarioId === this.currentScenario!.id);
      if (existingIndex >= 0) {
        this.chatHistory[existingIndex].messages = [...this.messages];
      } else {
        this.chatHistory.push({
          scenarioId: this.currentScenario.id,
          messages: [...this.messages]
        });
      }
    }
  }

  // Get scenario display name for headers
  getScenarioDisplayName(): string {
    return this.currentScenario?.name || 'No Scenario';
  }

  // Get scenario status for display
  getScenarioStatus(): string {
    if (!this.currentScenario) return 'none';
    if (this.currentScenario.is_base_scenario) return 'base';
    if (this.currentScenario.parent_scenario_id) return 'branch';
    return 'custom';
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

    // Save chat to history
    this.saveChatToHistory();

    // Reset auto-scroll when sending a new message
    this.shouldAutoScroll = true;

    try {
      // Get current scenario ID for context
      let scenarioId: number | undefined;
      this.scenarioService.currentScenario$.subscribe(scenario => {
        scenarioId = scenario?.id;
      }).unsubscribe();
      
      // Call LangGraph API with the simple schema agent
      console.log('Calling LangGraph API with message:', messageToSend, 'scenario:', scenarioId);
      
      // Use v2 agent only
      const apiCall = this.apiService.langGraphChatV2(messageToSend, scenarioId);
      
      apiCall.subscribe({
        next: (response) => {
          console.log('LangGraph response received:', response);
          
          // Add assistant response
          const assistantMessage: ChatMessage = {
            role: 'assistant',
            content: response.response || 'No response received',
            timestamp: new Date()
          };
          
          this.messages.push(assistantMessage);
          
          // Save chat to history after assistant response
          this.saveChatToHistory();
          
          // Handle execution results and output files
          if (response.has_execution_results || response.output_files || response.generated_files) {
            console.log('Processing execution results:', response);
            
            // Organize files by query (v2 agent) - only if files were actually generated
            if (response.user_query && response.generated_files && response.generated_files.length > 0) {
              console.log('Organizing files by query:', response.user_query, response.generated_files);
              this.queryFileOrganizer.addQueryFiles(
                response.user_query, 
                response.generated_files, 
                response.query_timestamp,
                this.currentScenario?.id
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
                outputFiles: outputFiles
              };
              
              this.executionService.emitExecutionResult(executionResult);
              console.log('Emitted execution result with output files:', outputFiles);
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
    
    // Files are global, so we don't clear files when clearing chat
    // Only clear the chat messages, keep all generated files visible
    
    // Emit files created event to refresh file tree
    this.filesCreated.emit();
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

  // Removed v1 agent toggle functionality - now using v2 agent only

  // Get agent version info
  getAgentVersionInfo(): string {
    return 'v2 (Simplified)';
  }

  // Helper method to determine file type
  private getFileType(filename: string): string {
    const extension = filename.split('.').pop()?.toLowerCase();
    switch (extension) {
      case 'html':
        return 'html';
      case 'py':
        return 'python';
      case 'csv':
        return 'csv';
      case 'json':
        return 'json';
      case 'png':
      case 'jpg':
      case 'jpeg':
        return 'image';
      default:
        return 'text';
    }
  }

} 