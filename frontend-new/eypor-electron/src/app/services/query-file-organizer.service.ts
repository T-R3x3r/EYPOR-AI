import { Injectable } from '@angular/core';
import { ApiService } from './api.service';

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
  private lastServerStartup: string | null = null;

  constructor(private apiService: ApiService) {
    this.loadFromLocalStorage();
    this.checkServerRestart();
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
   * Add query-file mapping to track which files were created by which queries
   */
  addQueryFileMapping(queryId: string, filePath: string, scenarioId?: number): void {
    // Store mapping in localStorage for now (in a real implementation, this would be in the backend)
    const mappings = this.getQueryFileMappings();
    mappings.push({
      queryId,
      filePath,
      scenarioId,
      timestamp: Date.now()
    });
    
    // Keep only the last 100 mappings to prevent localStorage bloat
    if (mappings.length > 100) {
      mappings.splice(0, mappings.length - 100);
    }
    
    localStorage.setItem('queryFileMappings', JSON.stringify(mappings));
  }

  /**
   * Get files for a specific query
   */
  getFilesForQuery(queryId: string): string[] {
    const mappings = this.getQueryFileMappings();
    return mappings
      .filter(mapping => mapping.queryId === queryId)
      .map(mapping => mapping.filePath);
  }

  /**
   * Get original query for a file
   */
  getQueryForFile(filePath: string): string | null {
    const mappings = this.getQueryFileMappings();
    const mapping = mappings.find(m => m.filePath === filePath);
    return mapping ? mapping.queryId : null;
  }

  /**
   * Get all query-file mappings
   */
  getQueryFileMappings(): Array<{queryId: string, filePath: string, scenarioId?: number, timestamp: number}> {
    try {
      const stored = localStorage.getItem('queryFileMappings');
      return stored ? JSON.parse(stored) : [];
    } catch (error) {
      console.error('Error getting query file mappings:', error);
      return [];
    }
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
   * Clear all data including localStorage
   */
  clearAllData(): void {
    this.queryGroups.clear();
    this.uploadedFiles = [];
    this.lastServerStartup = null;
    
    // Clear from localStorage
    try {
      localStorage.removeItem('queryFileOrganizer');
      console.log('Cleared all query file organizer data from localStorage');
    } catch (error) {
      console.error('Failed to clear localStorage:', error);
    }
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
   * Find query group by file name
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
    const hash = this.hashString(query + time.toString());
    return `query_${hash}`;
  }

  /**
   * Simple hash function for generating unique IDs
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
   * Save data to localStorage
   */
  private saveToLocalStorage(): void {
    try {
      const data = {
        queryGroups: Array.from(this.queryGroups.entries()),
        uploadedFiles: this.uploadedFiles,
        lastServerStartup: this.lastServerStartup
      };
      localStorage.setItem('queryFileOrganizer', JSON.stringify(data));
    } catch (error) {
      console.error('Failed to save to localStorage:', error);
    }
  }

  /**
   * Load data from localStorage
   */
  private loadFromLocalStorage(): void {
    try {
      const data = localStorage.getItem('queryFileOrganizer');
      if (data) {
        const parsed = JSON.parse(data);
        this.queryGroups = new Map(parsed.queryGroups || []);
        this.uploadedFiles = parsed.uploadedFiles || [];
        this.lastServerStartup = parsed.lastServerStartup || null;
      }
    } catch (error) {
      console.error('Failed to load from localStorage:', error);
    }
  }

  /**
   * Get a display-friendly version of the query
   */
  getDisplayQuery(query: string): string {
    if (query.length <= 60) {
      return query;
    }
    return query.substring(0, 60) + '...';
  }

  /**
   * Format timestamp for display
   */
  formatTimestamp(timestamp: number): string {
    return new Date(timestamp).toLocaleString();
  }

  /**
   * Check if server has restarted and clear old data if needed
   */
  private checkServerRestart(): void {
    this.apiService.getServerStartupInfo().subscribe({
      next: (response) => {
        const currentStartup = response.server_startup_timestamp;
        if (this.lastServerStartup && this.lastServerStartup !== currentStartup) {
          // Server has restarted, clear old data
          console.log('Server restarted, clearing old query groups');
          this.clearAllData();
        }
        this.lastServerStartup = currentStartup;
        this.saveToLocalStorage();
      },
      error: (error) => {
        console.error('Failed to check server startup:', error);
        // If we can't reach the server, assume it's a new server and clear old data
        console.log('Cannot reach server, clearing old data as precaution');
        this.clearAllData();
      }
    });
  }
} 