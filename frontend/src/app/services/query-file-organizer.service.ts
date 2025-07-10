import { Injectable } from '@angular/core';

export interface QueryFileGroup {
  query: string;
  timestamp: number;
  files: string[];
  queryId: string; // Unique identifier for the query
  scenarioId?: number; // Optional scenario ID for scenario-specific organization
}

export interface OrganizedFiles {
  uploaded_files: string[];
  query_groups: QueryFileGroup[];
}

@Injectable({
  providedIn: 'root'
})
export class QueryFileOrganizerService {
  private queryGroups: Map<string, QueryFileGroup> = new Map();
  private uploadedFiles: string[] = [];

  constructor() {
    this.loadFromLocalStorage();
  }

  /**
   * Add files generated from a specific query
   * Files are now global and accessible from any scenario
   */
  addQueryFiles(query: string, files: string[], timestamp?: number, scenarioId?: number): void {
    // Don't create query groups for empty file arrays
    if (!files || files.length === 0) {
      console.log('Skipping query group creation - no files provided');
      return;
    }
    
    const queryId = this.generateQueryId(query, timestamp);
    
    // Create or update query group - files are global
    const existingGroup = this.queryGroups.get(queryId);
    if (existingGroup) {
      // Add new files to existing group
      existingGroup.files = [...new Set([...existingGroup.files, ...files])];
    } else {
      // Create new query group - store scenarioId for reference but files are global
      const newGroup: QueryFileGroup = {
        query: query,
        timestamp: timestamp || Date.now(),
        files: files,
        queryId: queryId,
        scenarioId: scenarioId // Keep for reference but don't filter by it
      };
      this.queryGroups.set(queryId, newGroup);
    }
    
    this.saveToLocalStorage();
  }

  /**
   * Set uploaded files (non-AI generated)
   */
  setUploadedFiles(files: string[]): void {
    this.uploadedFiles = files;
    this.saveToLocalStorage();
  }

  /**
   * Get organized files structure
   */
  getOrganizedFiles(): OrganizedFiles {
    // Clean up empty query groups before returning
    this.cleanupEmptyQueryGroups();
    
    return {
      uploaded_files: this.uploadedFiles,
      query_groups: Array.from(this.queryGroups.values()).sort((a, b) => b.timestamp - a.timestamp)
    };
  }

  /**
   * Get organized files structure for a specific scenario
   */
  getOrganizedFilesForScenario(scenarioId: number): OrganizedFiles {
    // Clean up empty query groups before returning
    this.cleanupEmptyQueryGroups();
    
    const scenarioGroups = Array.from(this.queryGroups.values())
      .filter(group => group.scenarioId === scenarioId)
      .sort((a, b) => b.timestamp - a.timestamp);
    
    return {
      uploaded_files: this.uploadedFiles,
      query_groups: scenarioGroups
    };
  }

  /**
   * Remove a query group and its files
   */
  removeQueryGroup(queryId: string): void {
    this.queryGroups.delete(queryId);
    this.saveToLocalStorage();
  }

  /**
   * Clear all query groups
   */
  clearQueryGroups(): void {
    this.queryGroups.clear();
    this.saveToLocalStorage();
  }

  /**
   * Clear query groups for a specific scenario
   * Note: Files are now global, so this only clears files created in that specific scenario
   */
  clearQueryGroupsForScenario(scenarioId: number): void {
    const keysToDelete: string[] = [];
    
    this.queryGroups.forEach((group, key) => {
      if (group.scenarioId === scenarioId) {
        keysToDelete.push(key);
      }
    });
    
    keysToDelete.forEach(key => {
      this.queryGroups.delete(key);
    });
    
    if (keysToDelete.length > 0) {
      this.saveToLocalStorage();
    }
  }

  /**
   * Clear old query groups (older than 24 hours)
   */
  clearOldQueryGroups(): void {
    const oneDayAgo = Date.now() - (24 * 60 * 60 * 1000);
    const keysToDelete: string[] = [];
    
    this.queryGroups.forEach((group, key) => {
      if (group.timestamp < oneDayAgo) {
        keysToDelete.push(key);
      }
    });
    
    keysToDelete.forEach(key => {
      this.queryGroups.delete(key);
    });
    
    if (keysToDelete.length > 0) {
      this.saveToLocalStorage();
    }
  }

  /**
   * Get all AI-generated files (flattened from all query groups)
   */
  getAllAIGeneratedFiles(): string[] {
    const allFiles: string[] = [];
    this.queryGroups.forEach(group => {
      allFiles.push(...group.files);
    });
    return allFiles;
  }

  /**
   * Add files to an existing query group by query ID
   */
  addFilesToExistingQueryGroup(queryId: string, files: string[]): boolean {
    const existingGroup = this.queryGroups.get(queryId);
    if (existingGroup) {
      // Add new files to existing group, avoiding duplicates
      existingGroup.files = [...new Set([...existingGroup.files, ...files])];
      this.saveToLocalStorage();
      return true;
    }
    return false;
  }

  /**
   * Remove files from a query group and clean up if empty
   */
  removeFilesFromQueryGroup(queryId: string, files: string[]): boolean {
    const existingGroup = this.queryGroups.get(queryId);
    if (existingGroup) {
      // Remove specified files
      existingGroup.files = existingGroup.files.filter(file => !files.includes(file));
      
      // If no files remain, remove the entire group
      if (existingGroup.files.length === 0) {
        this.queryGroups.delete(queryId);
        console.log(`Removed empty query group: ${queryId}`);
      }
      
      this.saveToLocalStorage();
      return true;
    }
    return false;
  }

  /**
   * Find a query group that contains a specific file
   */
  findQueryGroupByFile(fileName: string): QueryFileGroup | null {
    for (const group of this.queryGroups.values()) {
      if (group.files.includes(fileName)) {
        return group;
      }
    }
    return null;
  }

  /**
   * Clean up query groups that have no files
   */
  private cleanupEmptyQueryGroups(): void {
    const keysToDelete: string[] = [];
    
    this.queryGroups.forEach((group, key) => {
      if (!group.files || group.files.length === 0) {
        keysToDelete.push(key);
      }
    });
    
    keysToDelete.forEach(key => {
      this.queryGroups.delete(key);
    });
    
    if (keysToDelete.length > 0) {
      console.log(`Cleaned up ${keysToDelete.length} empty query groups`);
      this.saveToLocalStorage();
    }
  }

  /**
   * Manually trigger cleanup of empty query groups
   */
  public cleanupEmptyGroups(): void {
    this.cleanupEmptyQueryGroups();
  }

  /**
   * Generate a unique query ID based on query text and timestamp
   */
  private generateQueryId(query: string, timestamp?: number): string {
    const time = timestamp || Date.now();
    const queryHash = this.hashString(query);
    return `${time}_${queryHash}`;
  }

  /**
   * Simple string hash function
   */
  private hashString(str: string): string {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // Convert to 32-bit integer
    }
    return Math.abs(hash).toString(36);
  }

  /**
   * Save current state to localStorage
   */
  private saveToLocalStorage(): void {
    try {
      const data = {
        queryGroups: Array.from(this.queryGroups.entries()),
        uploadedFiles: this.uploadedFiles
      };
      localStorage.setItem('queryFileOrganizer', JSON.stringify(data));
    } catch (e) {
      console.warn('Failed to save query file organizer state:', e);
    }
  }

  /**
   * Load state from localStorage
   */
  private loadFromLocalStorage(): void {
    try {
      const data = localStorage.getItem('queryFileOrganizer');
      if (data) {
        const parsed = JSON.parse(data);
        this.queryGroups = new Map(parsed.queryGroups || []);
        this.uploadedFiles = parsed.uploadedFiles || [];
      }
    } catch (e) {
      console.warn('Failed to load query file organizer state:', e);
    }
  }

  /**
   * Get a truncated query for display (max 50 characters)
   */
  getDisplayQuery(query: string): string {
    if (query.length <= 50) {
      return query;
    }
    return query.substring(0, 47) + '...';
  }

  /**
   * Format timestamp for display
   */
  formatTimestamp(timestamp: number): string {
    return new Date(timestamp).toLocaleString();
  }
} 