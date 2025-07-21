import { Component, OnInit, ViewChild, ElementRef, AfterViewChecked, HostListener, Output, EventEmitter } from '@angular/core';
import { ApiService } from '../../services/api.service';
import { ScenarioAwareExecutionService } from '../../services/scenario-aware-execution.service';
import { QueryFileOrganizerService } from '../../services/query-file-organizer.service';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  isLoading?: boolean;
  hasGeneratedFiles?: boolean;
  generatedFiles?: string[];
  isEditable?: boolean;
  editMode?: boolean;
}

interface EditModeState {
  isActive: boolean;
  editingFile: string | null;
  originalQuery: string | null;
  modificationHistory: FileModification[];
}

interface FileModification {
  modification_query: string;
  timestamp: number;
  query_id: string;
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
  
  // Edit mode state
  editModeState: EditModeState = {
    isActive: false,
    editingFile: null,
    originalQuery: null,
    modificationHistory: []
  };
  
  // AI Model Selection
  selectedModel = 'GPT-4.1';
  showModelDropdown = false;
  availableModels: string[] = [];
  modelLoading = false;

  constructor(
    private apiService: ApiService,
    private executionService: ScenarioAwareExecutionService,
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
    this.loadAvailableModels();
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

  loadAvailableModels(): void {
    this.modelLoading = true;
    this.apiService.getLangGraphAvailableModels().subscribe({
      next: (response) => {
        this.availableModels = Object.keys(response.available_models);
        // Get current model
        this.apiService.getLangGraphCurrentModel().subscribe({
          next: (currentModelResponse) => {
            this.selectedModel = currentModelResponse.current_model;
            this.modelLoading = false;
          },
          error: (error) => {
            console.error('Error loading current model:', error);
            this.modelLoading = false;
          }
        });
      },
      error: (error) => {
        console.error('Error loading available models:', error);
        this.modelLoading = false;
        // Fallback to default models
        this.availableModels = ['GPT-4.1', 'o4-mini', 'GPT-4o', 'o3', 'ChatGPT-4o'];
      }
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
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: messageToSend,
      timestamp: new Date()
    };

    this.messages.push(userMessage);
    this.shouldAutoScroll = true;

    try {
      // If in edit mode, modify the request to indicate file editing
      let finalMessage = messageToSend;
      if (this.editModeState.isActive && this.editModeState.editingFile) {
        finalMessage = `Edit file ${this.editModeState.editingFile}: ${messageToSend}`;
      }
      
      // Call LangGraph API with the v2 agent
      console.log('Calling LangGraph API with message:', finalMessage);
      
      // Pass edit mode state to the backend
      const editModeState = this.editModeState.isActive ? {
        isActive: this.editModeState.isActive,
        editingFile: this.editModeState.editingFile || undefined
      } : undefined;
      
      const apiCall = this.apiService.langGraphChatV2(finalMessage, undefined, editModeState);
      
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
            
            // Check if this is an edit operation
            const isEditOperation = response.response && response.response.includes('[EDIT_OPERATION]');
            const editedFileMatch = response.response && response.response.match(/\[EDITED_FILE: ([^\]]+)\]/);
            const editedFile = editedFileMatch ? editedFileMatch[1] : null;
            
            console.log('Is edit operation:', isEditOperation);
            console.log('Edited file:', editedFile);
            
            if (isEditOperation && editedFile) {
              // This is an edit operation - don't create new query groups
              console.log('Processing edit operation for file:', editedFile);
              
              // Mark the assistant message as having generated files but don't create new query groups
              assistantMessage.hasGeneratedFiles = true;
              assistantMessage.generatedFiles = response.generated_files;
              assistantMessage.isEditable = true;
              
              // Don't add new query files or emit files created event for edits
              // The file already exists in the sidebar
            } else {
              // This is a regular file generation operation
              // Organize files by query (v2 agent) - only if files were actually generated
              if (response.user_query && response.generated_files && response.generated_files.length > 0) {
                console.log('Organizing files by query:', response.user_query, response.generated_files);
                this.queryFileOrganizer.addQueryFiles(
                  response.user_query, 
                  response.generated_files, 
                  response.query_timestamp
                );
                
                // Mark the assistant message as having generated files
                assistantMessage.hasGeneratedFiles = true;
                assistantMessage.generatedFiles = response.generated_files;
                assistantMessage.isEditable = true;
                
                // Add query-file mappings
                const queryId = this.generateQueryId(response.user_query);
                response.generated_files.forEach((file: string) => {
                  this.queryFileOrganizer.addQueryFileMapping(queryId, file);
                });
                
                // Emit files created event to trigger file tree refresh
                this.filesCreated.emit();
              } else if (response.user_query && (!response.generated_files || response.generated_files.length === 0)) {
                console.log('No files generated for query:', response.user_query);
                // Don't create a query group if no files were generated
              }
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
            
            // For edit operations, use a different command type
            if (isEditOperation) {
              commandType = 'File Edit Execution';
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
                timestamp: Date.now(),
                scenarioId: 0, // Will be set by the service
                isEditOperation: isEditOperation,
                editedFile: editedFile
              };
              
              this.executionService.emitExecutionResult(executionResult);
            }
          }
          
          // Exit edit mode after successful response
          if (this.editModeState.isActive) {
            this.exitEditMode();
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
    this.modelLoading = true;
    this.apiService.switchLangGraphModel(model).subscribe({
      next: (response) => {
        this.selectedModel = model;
        this.showModelDropdown = false;
        this.modelLoading = false;
        console.log('Model switched successfully:', response);
      },
      error: (error) => {
        console.error('Error switching model:', error);
        this.modelLoading = false;
        // Keep the current model if switching failed
      }
    });
  }

  private getFileType(filename: string): string {
    const extension = filename.split('.').pop()?.toLowerCase();
    switch (extension) {
      case 'py':
        return 'python';
      case 'sql':
        return 'sql';
      case 'html':
        return 'html';
      case 'txt':
        return 'text';
      case 'json':
        return 'json';
      default:
        return 'unknown';
    }
  }

  // Edit mode methods
  onMessageRightClick(message: ChatMessage, event: MouseEvent): void {
    if (message.hasGeneratedFiles && message.generatedFiles && message.generatedFiles.length > 0) {
      event.preventDefault();
      this.showContextMenu(event, message);
    }
  }

  showContextMenu(event: MouseEvent, message: ChatMessage): void {
    // Create context menu
    const menu = document.createElement('div');
    menu.className = 'context-menu';
    menu.style.position = 'fixed';
    menu.style.left = event.clientX + 'px';
    menu.style.top = event.clientY + 'px';
    menu.style.zIndex = '1000';
    menu.style.backgroundColor = 'var(--bg-primary)';
    menu.style.border = '1px solid var(--border-color)';
    menu.style.borderRadius = '6px';
    menu.style.boxShadow = 'var(--shadow)';
    menu.style.padding = '4px 0';
    menu.style.color = 'var(--text-primary)';
    
    // Add menu items
    const editItem = document.createElement('div');
    editItem.className = 'menu-item';
    editItem.style.padding = '8px 16px';
    editItem.style.cursor = 'pointer';
    editItem.style.fontSize = '14px';
    editItem.style.color = 'var(--text-primary)';
    editItem.style.transition = 'background-color 0.2s ease';
    editItem.innerHTML = '<i class="fas fa-edit"></i> Edit Generated Files';
    editItem.onmouseenter = () => {
      editItem.style.backgroundColor = 'var(--bg-tertiary)';
    };
    editItem.onmouseleave = () => {
      editItem.style.backgroundColor = 'transparent';
    };
    editItem.onclick = () => {
      this.enterEditMode(message);
      document.body.removeChild(menu);
    };
    
    const viewItem = document.createElement('div');
    viewItem.className = 'menu-item';
    viewItem.style.padding = '8px 16px';
    viewItem.style.cursor = 'pointer';
    viewItem.style.fontSize = '14px';
    viewItem.style.color = 'var(--text-primary)';
    viewItem.style.transition = 'background-color 0.2s ease';
    viewItem.innerHTML = '<i class="fas fa-eye"></i> View Files';
    viewItem.onmouseenter = () => {
      viewItem.style.backgroundColor = 'var(--bg-tertiary)';
    };
    viewItem.onmouseleave = () => {
      viewItem.style.backgroundColor = 'transparent';
    };
    viewItem.onclick = () => {
      this.viewFiles(message);
      document.body.removeChild(menu);
    };
    
    menu.appendChild(editItem);
    menu.appendChild(viewItem);
    document.body.appendChild(menu);
    
    // Remove menu when clicking outside
    const removeMenu = () => {
      if (document.body.contains(menu)) {
        document.body.removeChild(menu);
      }
      document.removeEventListener('click', removeMenu);
    };
    setTimeout(() => document.addEventListener('click', removeMenu), 100);
  }

  enterEditMode(message: ChatMessage): void {
    this.editModeState.isActive = true;
    this.editModeState.originalQuery = message.content;
    this.highlightEditMode();
    
    // If multiple files, show file selection dialog
    if (message.generatedFiles && message.generatedFiles.length > 1) {
      this.showFileSelectionDialog(message.generatedFiles);
    } else if (message.generatedFiles && message.generatedFiles.length === 1) {
      this.editModeState.editingFile = message.generatedFiles[0];
      this.updateInputPlaceholder();
    }
  }

  exitEditMode(): void {
    this.editModeState.isActive = false;
    this.editModeState.editingFile = null;
    this.editModeState.originalQuery = null;
    this.clearEditModeHighlight();
    this.updateInputPlaceholder();
  }

  highlightEditMode(): void {
    // Add visual indicator for edit mode
    const inputElement = this.messageInput?.nativeElement;
    if (inputElement) {
      inputElement.style.borderColor = 'var(--accent-color)';
      inputElement.style.backgroundColor = 'var(--bg-secondary)';
      inputElement.classList.add('edit-mode');
    }
  }

  clearEditModeHighlight(): void {
    // Remove visual indicator for edit mode
    const inputElement = this.messageInput?.nativeElement;
    if (inputElement) {
      inputElement.style.borderColor = '';
      inputElement.style.backgroundColor = '';
      inputElement.classList.remove('edit-mode');
    }
  }

  updateInputPlaceholder(): void {
    const inputElement = this.messageInput?.nativeElement;
    if (inputElement) {
      if (this.editModeState.isActive && this.editModeState.editingFile) {
        inputElement.placeholder = `Editing: ${this.editModeState.editingFile} - Enter your modification request...`;
      } else {
        inputElement.placeholder = 'Ask EYPOR...';
      }
    }
  }

  showFileSelectionDialog(files: string[]): void {
    // Create file selection dialog
    const dialog = document.createElement('div');
    dialog.className = 'file-selection-dialog';
    dialog.style.position = 'fixed';
    dialog.style.top = '50%';
    dialog.style.left = '50%';
    dialog.style.transform = 'translate(-50%, -50%)';
    dialog.style.backgroundColor = 'var(--bg-primary)';
    dialog.style.border = '1px solid var(--border-color)';
    dialog.style.borderRadius = '8px';
    dialog.style.padding = '20px';
    dialog.style.zIndex = '1001';
    dialog.style.minWidth = '300px';
    dialog.style.boxShadow = 'var(--shadow)';
    dialog.style.color = 'var(--text-primary)';
    
    dialog.innerHTML = `
      <h3 style="margin: 0 0 16px 0; color: var(--text-primary);">Select File to Edit</h3>
      <div style="max-height: 200px; overflow-y: auto;">
        ${files.map(file => `
          <div class="file-option" style="padding: 8px 12px; cursor: pointer; border-radius: 4px; margin: 4px 0; color: var(--text-primary); transition: background-color 0.2s ease;"
               onmouseenter="this.style.backgroundColor='var(--bg-tertiary)'"
               onmouseleave="this.style.backgroundColor='transparent'"
               onclick="this.parentElement.parentElement.selectFile('${file}')">
            <i class="fas fa-file-code"></i> ${file}
          </div>
        `).join('')}
      </div>
      <button onclick="this.parentElement.close()" 
              style="margin-top: 16px; padding: 8px 16px; background: var(--bg-tertiary); color: var(--text-primary); border: 1px solid var(--border-color); border-radius: 4px; cursor: pointer; transition: background-color 0.2s ease;"
              onmouseenter="this.style.backgroundColor='var(--bg-secondary)'"
              onmouseleave="this.style.backgroundColor='var(--bg-tertiary)'">
        Cancel
      </button>
    `;
    
    // Add methods to dialog
    (dialog as any).selectFile = (file: string) => {
      this.editModeState.editingFile = file;
      this.updateInputPlaceholder();
      document.body.removeChild(dialog);
    };
    
    (dialog as any).close = () => {
      this.exitEditMode();
      document.body.removeChild(dialog);
    };
    
    document.body.appendChild(dialog);
  }

  viewFiles(message: ChatMessage): void {
    if (message.generatedFiles && message.generatedFiles.length > 0) {
      // Open the first file in the code editor
      const firstFile = message.generatedFiles[0];
      this.openFileInCodeEditor(firstFile);
    }
  }

  private openFileInCodeEditor(filePath: string): void {
    // Extract just the filename from the path
    const fileName = filePath.split('/').pop() || filePath.split('\\').pop() || filePath;
    
    // Emit an event to the parent component to open the file in the code editor
    // This will be handled by the workbench component
    const event = new CustomEvent('openFileInEditor', {
      detail: {
        filePath: fileName, // Use just the filename, the backend will find it in scenario directories
        fileName: fileName
      }
    });
    window.dispatchEvent(event);
  }

  private generateQueryId(query: string): string {
    // Simple hash function to generate unique query ID
    let hash = 0;
    for (let i = 0; i < query.length; i++) {
      const char = query.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // Convert to 32-bit integer
    }
    return Math.abs(hash).toString(36) + Date.now().toString(36);
  }
} 