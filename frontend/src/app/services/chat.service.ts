import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  actionType?: string;
  threadId?: string;
  requiresApproval?: boolean;
  approved?: boolean;
  messageId?: string;
}

export interface ChatState {
  messages: ChatMessage[];
  isLoading: boolean;
  threadId: string;
  pendingApproval?: ChatMessage;
}

@Injectable({
  providedIn: 'root'
})
export class ChatService {
  private readonly DEFAULT_THREAD_ID = 'default';
  
  private chatStateSubject = new BehaviorSubject<ChatState>({
    messages: [],
    isLoading: false,
    threadId: this.DEFAULT_THREAD_ID
  });
  
  public chatState$ = this.chatStateSubject.asObservable();

  constructor() {}

  private getCurrentState(): ChatState {
    return this.chatStateSubject.value;
  }

  private updateState(newState: ChatState): void {
    this.chatStateSubject.next(newState);
  }

  // Add a single message
  addMessage(message: ChatMessage): void {
    const currentState = this.getCurrentState();
    const updatedMessages = [...currentState.messages, message];
    
    this.updateState({
      ...currentState,
      messages: updatedMessages
    });
  }

  // Set loading state
  setLoading(loading: boolean): void {
    const currentState = this.getCurrentState();
    this.updateState({
      ...currentState,
      isLoading: loading
    });
  }

  // Clear all messages (will trigger reload from LangGraph)
  clearMessages(): void {
    const currentState = this.getCurrentState();
    this.updateState({
      ...currentState,
      messages: []
    });
  }

  // Get current thread ID
  getCurrentThreadId(): string {
    return this.getCurrentState().threadId;
  }

  // Switch to a different thread
  switchThread(threadId: string): void {
    const currentState = this.getCurrentState();
    this.updateState({
      ...currentState,
      threadId,
      messages: [] // Clear messages - they'll be loaded from LangGraph
    });
  }

  // Create a new thread
  createNewThread(): string {
    const newThreadId = `thread_${Date.now()}`;
    this.switchThread(newThreadId);
    return newThreadId;
  }

  // Human-in-the-loop: Set pending approval message
  setPendingApproval(message: ChatMessage): void {
    const currentState = this.getCurrentState();
    this.updateState({
      ...currentState,
      pendingApproval: message
    });
  }

  // Human-in-the-loop: Clear pending approval
  clearPendingApproval(): void {
    const currentState = this.getCurrentState();
    this.updateState({
      ...currentState,
      pendingApproval: undefined
    });
  }

  // Human-in-the-loop: Get pending approval message
  getPendingApproval(): ChatMessage | undefined {
    return this.getCurrentState().pendingApproval;
  }

  // Load messages from LangGraph backend
  loadMessagesFromBackend(messages: ChatMessage[]): void {
    const currentState = this.getCurrentState();
    this.updateState({
      ...currentState,
      messages: messages
    });
  }
} 