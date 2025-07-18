import { Component, OnInit, OnDestroy, AfterViewInit, ViewChild } from '@angular/core';
import { FormControl } from '@angular/forms';
import { Subscription } from 'rxjs';
import { debounceTime, distinctUntilChanged } from 'rxjs/operators';
import { ApiService, DatabaseInfo, SQLResult, WhitelistResponse, WhitelistUpdateResponse } from '../../services/api.service';
import { DatabaseService, DatabaseChange } from '../../services/database.service';

interface TableColumn {
  name: string;
  type: string;
}

interface TableData {
  data: any[];
  columns: string[];
  totalRows: number;
  filteredRows: number;
}

@Component({
  selector: 'app-database-view',
  templateUrl: './database-view.component.html',
  styleUrls: ['./database-view.component.css']
})
export class DatabaseViewComponent implements OnInit, OnDestroy, AfterViewInit {
  // Database info
  databaseInfo: DatabaseInfo | null = null;
  detailedDbInfo: any = null;
  isLoading = false;

  // Table browser
  selectedTable = '';
  tableData: TableData = { data: [], columns: [], totalRows: 0, filteredRows: 0 };
  tableColumns: TableColumn[] = [];
  displayedColumns: string[] = [];
  loadingTableData = false;

  // Search functionality
  globalSearchControl = new FormControl('');
  tableSearchControl = new FormControl('');

  // Statistics
  totalRows = 0;
  filteredRows = 0;

  // Debug
  lastError = '';
  showDebug = false;
  isRefreshing = false;

  // Whitelist management
  whitelistData: WhitelistResponse | null = null;
  whitelistLoading = false;
  selectAllEnabled = false;

  // UI state for collapsible sections
  showTableModifications = false;

  // Context menu properties
  showContextMenu = false;
  contextMenuX = 0;
  contextMenuY = 0;
  contextMenuType: 'column' | 'row' | 'cell' | null = null;
  contextMenuTarget: any = null;
  selectedRowIndex = -1;
  selectedColumnName = '';
  
  // Column dialog properties
  showColumnDialog = false;
  newColumnName = '';
  
  // Confirmation dialog properties
  showDeleteColumnDialog = false;
  showDeleteRowDialog = false;
  itemToDelete: any = null;
  
  // Cell editing properties
  editingCells: Set<string> = new Set();
  cellValues: { [key: string]: any } = {};
  
  // Track newly added rows for editing
  newlyAddedRowIndex: number = -1;
  private isRefreshingAfterAdd: boolean = false;

  // Scenario-aware properties
  currentScenario: any = null;
  queryHistory: { sql: string; timestamp: Date; scenarioId: number }[] = [];
  isLoadingScenario = false;

  // Tables list
  tables: any[] = [];
  selectedTableObj: any = null;

  // Filtered tables for search
  filteredTables: any[] = [];

  // Sorting properties
  currentSortColumn: string = '';
  currentSortDirection: 'asc' | 'desc' | '' = '';
  sortedData: any[] = [];

  private subscriptions: Subscription[] = [];

  constructor(
    private apiService: ApiService,
    private databaseService: DatabaseService
  ) {}

  ngOnInit(): void {
    this.loadDatabaseInfo();
    this.setupSearch();
    this.setupTableSearch();
    
    // Subscribe to database changes
    const changesSub = this.databaseService.changes$.subscribe(changes => {
      if (changes.length > 0) {
        console.log('Database changes detected, refreshing...', changes);
        this.loadDatabaseInfo();
        // Refresh current table if one is selected
        if (this.selectedTable) {
          this.loadTableData(this.selectedTable);
        }
      }
    });
    this.subscriptions.push(changesSub);

    // Subscribe to scenario changes
    const scenarioSub = this.databaseService.currentScenario$.subscribe(scenario => {
      this.currentScenario = scenario;
      if (scenario) {
        console.log('Scenario changed, refreshing database info...', scenario);
        this.isLoadingScenario = true;
        this.loadDatabaseInfo();
        this.loadScenarioQueryHistory(scenario.id);
        // Clear current table selection when switching scenarios
        this.selectedTable = '';
        this.tableData = { data: [], columns: [], totalRows: 0, filteredRows: 0 };
        this.tableColumns = [];
        this.displayedColumns = [];
        this.isLoadingScenario = false;
      } else {
        // Clear all data when no scenario is active
        this.clearScenarioData();
      }
    });
    this.subscriptions.push(scenarioSub);

    // Subscribe to database info changes
    const dbInfoSub = this.databaseService.databaseInfo$.subscribe(dbInfo => {
      this.databaseInfo = dbInfo;
      if (dbInfo) {
        this.tables = dbInfo.tables || [];
        this.filteredTables = [...this.tables];
      }
    });
    this.subscriptions.push(dbInfoSub);

    // Subscribe to loading state
    const loadingSub = this.databaseService.isLoading$.subscribe(loading => {
      this.isLoading = loading;
    });
    this.subscriptions.push(loadingSub);

    // Listen for file uploads by polling database info periodically
    const refreshInterval = setInterval(() => {
      this.apiService.getDatabaseInfo().subscribe({
        next: (data) => {
          // Only refresh if there's a meaningful change
          const currentTableCount = this.databaseInfo?.total_tables || 0;
          const newTableCount = data?.total_tables || 0;
          
          if (newTableCount !== currentTableCount && newTableCount > 0) {
            console.log('New database detected, refreshing interface...', {
              oldTableCount: currentTableCount,
              newTableCount: newTableCount
            });
            this.loadDatabaseInfo();
          }
        },
        error: (error) => {
          // Silently handle errors during polling
        }
      });
    }, 2000); // Check every 2 seconds

    // Store interval ID for cleanup
    this.subscriptions.push({
      unsubscribe: () => clearInterval(refreshInterval)
    } as any);
  }

  ngAfterViewInit(): void {
    // Setup sort after view init if needed
  }

  ngOnDestroy(): void {
    this.subscriptions.forEach(sub => sub.unsubscribe());
  }

  // Load scenario-specific query history
  private loadScenarioQueryHistory(scenarioId: number): void {
    console.log('Loading query history for scenario:', scenarioId);
    // TODO: Implement backend API for query history
  }

  // Clear all scenario-specific data
  private clearScenarioData(): void {
    this.databaseInfo = null;
    this.detailedDbInfo = null;
    this.selectedTable = '';
    this.tableData = { data: [], columns: [], totalRows: 0, filteredRows: 0 };
    this.tableColumns = [];
    this.displayedColumns = [];
    this.queryHistory = [];
    this.whitelistData = null;
  }

  // Add query to history
  private addToQueryHistory(sql: string): void {
    if (this.currentScenario) {
      this.queryHistory.push({
        sql,
        timestamp: new Date(),
        scenarioId: this.currentScenario.id
      });
      // Keep only last 50 queries
      if (this.queryHistory.length > 50) {
        this.queryHistory = this.queryHistory.slice(-50);
      }
    }
  }

  // Scenario display methods
  getScenarioDisplayName(): string {
    return this.currentScenario ? this.currentScenario.name : 'No Scenario';
  }

  getScenarioStatus(): string {
    if (!this.currentScenario) return 'No Scenario';
    return this.currentScenario.is_base_scenario ? 'Base' : 'Branch';
  }

  setupSearch(): void {
    this.globalSearchControl.valueChanges.pipe(
      debounceTime(300),
      distinctUntilChanged()
    ).subscribe(value => {
      this.applyGlobalFilter(value || '');
    });
  }

  loadDatabaseInfo(): void {
    console.log('Loading database info...');
    this.databaseService.loadDatabaseInfo().subscribe({
      next: (data) => {
        console.log('Database info loaded:', data);
        this.databaseInfo = data;
        this.tables = data.tables || [];
        this.filteredTables = [...this.tables];
        console.log('Tables loaded:', this.tables);
        this.getDetailedDatabaseInfo();
        this.loadWhitelistData();
      },
      error: (error) => {
        console.error('Error loading database info:', error);
        this.lastError = error.message || 'Failed to load database info';
      }
    });
  }

  getDetailedDatabaseInfo(): void {
    this.databaseService.getDetailedDatabaseInfo().subscribe({
      next: (data) => {
        this.detailedDbInfo = data;
      },
      error: (error) => {
        console.error('Error loading detailed database info:', error);
      }
    });
  }

  async loadTables(): Promise<void> {
    try {
      const tables = await this.databaseService.getTables();
      this.tables = tables;
      this.filteredTables = [...this.tables]; // Update filtered tables
    } catch (error) {
      console.error('Error loading tables:', error);
      this.lastError = error instanceof Error ? error.message : 'Unknown error';
    }
  }

  updatePagination(): void {
    // Update pagination logic if needed
    // For now, we'll keep it simple
  }

  // Database operations
  async refreshDatabaseInfo(): Promise<void> {
    if (this.isRefreshing) return;
    
    console.log('Refreshing database info...');
    this.isRefreshing = true;
    try {
      await this.loadDatabaseInfo();
      await this.loadTables();
      if (this.selectedTable) {
        await this.loadTableData(this.selectedTable);
      }
    } catch (error) {
      console.error('Error refreshing database info:', error);
      this.lastError = error instanceof Error ? error.message : 'Unknown error';
    } finally {
      this.isRefreshing = false;
    }
  }

  // Debug method to test database connection
  testDatabaseConnection(): void {
    console.log('Testing database connection...');
    this.apiService.getDatabaseInfo().subscribe({
      next: (data) => {
        console.log('Database connection test successful:', data);
        this.databaseInfo = data;
        this.tables = data.tables || [];
        this.filteredTables = [...this.tables];
        console.log('Tables from test:', this.tables);
      },
      error: (error) => {
        console.error('Database connection test failed:', error);
        this.lastError = error.message || 'Database connection failed';
      }
    });
    
    // Also test current scenario
    this.apiService.getCurrentScenario().subscribe({
      next: (scenario) => {
        console.log('Current scenario:', scenario);
      },
      error: (error) => {
        console.error('Failed to get current scenario:', error);
        // Try to create a default scenario if none exist
        this.createDefaultScenario();
      }
    });
  }

  // Create a default scenario if none exist
  createDefaultScenario(): void {
    console.log('Attempting to create default scenario...');
    this.apiService.createScenario({
      name: 'Default Scenario',
      description: 'Default scenario created automatically'
    }).subscribe({
      next: (scenario) => {
        console.log('Default scenario created:', scenario);
        // Activate the scenario
        this.apiService.activateScenario(scenario.id).subscribe({
          next: (activatedScenario) => {
            console.log('Default scenario activated:', activatedScenario);
            // Refresh database info
            this.loadDatabaseInfo();
          },
          error: (error) => {
            console.error('Failed to activate default scenario:', error);
          }
        });
      },
      error: (error) => {
        console.error('Failed to create default scenario:', error);
      }
    });
  }

  async selectTable(table: any): Promise<void> {
    if (!table || !table.name) return;
    
    this.selectedTable = table.name;
    this.selectedTableObj = table;
    await this.loadTableData(table.name);
  }

  async loadTableData(tableName: string): Promise<void> {
    if (!tableName) return;
    
    console.log('Loading table data for:', tableName);
    this.loadingTableData = true;
    this.lastError = '';
    
    try {
      const data = await this.databaseService.getTableData(tableName);
      console.log('Table data loaded:', data);
      
      this.tableData = data;
      this.totalRows = data.total_rows || 0;
      this.filteredRows = data.data?.length || 0;
      this.displayedColumns = data.columns || [];
      
      // Update table columns for type information
      this.tableColumns = this.displayedColumns.map(colName => ({
        name: colName,
        type: this.guessColumnType(data.data?.[0]?.[colName])
      }));
      
      // Initialize sorted data
      this.sortedData = [...this.tableData.data];
      
      // Apply current sorting if any
      if (this.currentSortColumn && this.currentSortDirection) {
        this.applySorting();
      }
      
      console.log('Table data processed:', {
        totalRows: this.totalRows,
        filteredRows: this.filteredRows,
        displayedColumns: this.displayedColumns,
        tableColumns: this.tableColumns,
        dataLength: data.data?.length
      });
      
      this.updatePagination();
    } catch (error) {
      console.error('Error loading table data:', error);
      this.lastError = error instanceof Error ? error.message : 'Unknown error';
      // Clear table data on error
      this.tableData = { data: [], columns: [], totalRows: 0, filteredRows: 0 };
      this.displayedColumns = [];
      this.tableColumns = [];
      this.sortedData = [];
    } finally {
      this.loadingTableData = false;
    }
  }

  private guessColumnType(value: any): string {
    if (value === null || value === undefined) return 'TEXT';
    if (typeof value === 'number') {
      return Number.isInteger(value) ? 'INTEGER' : 'REAL';
    }
    if (typeof value === 'string') {
      // Try to parse as date
      if (!isNaN(Date.parse(value))) return 'TEXT';
      // Try to parse as number
      if (!isNaN(Number(value))) return 'REAL';
      return 'TEXT';
    }
    return 'TEXT';
  }

  applyGlobalFilter(filterValue: string): void {
    if (!this.tables) return; // Filter from the main tables list
    
    const lowerCaseFilter = filterValue.toLowerCase();
    this.filteredTables = this.tables.filter(table => {
      return table.name.toLowerCase().includes(lowerCaseFilter);
    });
  }

  getDatabaseStatus(): string {
    return this.databaseInfo ? 'Connected' : 'Not Connected';
  }

  getTableRowCount(tableName: string): number {
    const table = this.tables.find(t => t.name === tableName);
    return table ? table.row_count : 0;
  }

  formatCellValue(value: any): string {
    if (value === null || value === undefined) return '';
    return value.toString();
  }

  clearSearch(): void {
    this.globalSearchControl.setValue('');
    this.filteredTables = [...this.tables];
    if (this.selectedTable) {
      this.loadTableData(this.selectedTable);
    }
  }

  getColumnType(columnName: string): string {
    const column = this.tableColumns.find(col => col.name === columnName);
    return column ? column.type : 'TEXT';
  }

  downloadDatabase(): void {
    this.databaseService.downloadDatabase().subscribe({
      next: (blob) => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'database.db';
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      },
      error: (error) => {
        console.error('Error downloading database:', error);
        alert('Failed to download database');
      }
    });
  }

  exportDatabase(format: string): void {
    this.databaseService.exportDatabase(format).subscribe({
      next: (blob) => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `database_export.${format}`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      },
      error: (error) => {
        console.error('Error exporting database:', error);
        alert('Failed to export database');
      }
    });
  }

  toggleDebug(): void {
    this.showDebug = !this.showDebug;
  }

  toggleTableModifications(): void {
    this.showTableModifications = !this.showTableModifications;
  }

  loadWhitelistData(): void {
    this.whitelistLoading = true;
    this.databaseService.loadWhitelistData().subscribe({
      next: (data: WhitelistResponse) => {
        this.whitelistData = data;
        this.updateSelectAllState();
        this.whitelistLoading = false;
      },
      error: (error) => {
        console.error('Error loading whitelist data:', error);
        this.whitelistLoading = false;
      }
    });
  }

  updateSelectAllState(): void {
    if (!this.whitelistData) return;
    this.selectAllEnabled = this.whitelistData.available_tables.length > 0;
  }

  isTableWhitelisted(tableName: string): boolean {
    if (!this.whitelistData) return false;
    return this.whitelistData.whitelist.includes(tableName);
  }

  toggleTableWhitelist(tableName: string): void {
    if (!this.whitelistData) return;
    
    const currentWhitelist = [...this.whitelistData.whitelist];
    const index = currentWhitelist.indexOf(tableName);
    
    if (index > -1) {
      currentWhitelist.splice(index, 1);
    } else {
      currentWhitelist.push(tableName);
    }
    
    this.updateWhitelist(currentWhitelist);
  }

  toggleSelectAll(): void {
    if (!this.whitelistData) return;
    
    const newWhitelist = this.selectAllEnabled ? 
      [] : 
      [...this.whitelistData.available_tables];
    
    this.updateWhitelist(newWhitelist);
  }

  private updateWhitelist(newWhitelist: string[]): void {
    this.databaseService.updateWhitelist(newWhitelist).subscribe({
      next: (response: WhitelistUpdateResponse) => {
        console.log('Whitelist updated successfully:', response);
        // Reload whitelist data to get the current state
        this.loadWhitelistData();
        this.whitelistLoading = false;
      },
      error: (error: any) => {
        console.error('Error updating whitelist:', error);
        this.whitelistLoading = false;
        alert('Failed to update table whitelist. Please try again.');
      }
    });
  }

  // Context menu methods
  onColumnRightClick(event: MouseEvent, columnName: string): void {
    event.preventDefault();
    this.contextMenuType = 'column';
    this.selectedColumnName = columnName;
    this.positionContextMenu(event.clientX, event.clientY);
    this.showContextMenu = true;
  }

  onRowRightClick(event: MouseEvent, rowData: any, rowIndex: number): void {
    event.preventDefault();
    this.contextMenuType = 'row';
    this.selectedRowIndex = rowIndex;
    this.contextMenuTarget = { rowData, rowIndex };
    this.positionContextMenu(event.clientX, event.clientY);
    this.showContextMenu = true;
  }

  onCellRightClick(event: MouseEvent, rowData: any, columnName: string, rowIndex: number): void {
    event.preventDefault();
    this.contextMenuType = 'cell';
    this.selectedColumnName = columnName;
    this.selectedRowIndex = rowIndex;
    this.contextMenuTarget = { rowData, columnName, rowIndex };
    this.positionContextMenu(event.clientX, event.clientY);
    this.showContextMenu = true;
  }

  hideContextMenu(): void {
    this.showContextMenu = false;
    this.contextMenuType = null;
    this.contextMenuTarget = null;
  }

  private positionContextMenu(x: number, y: number): void {
    const menuWidth = 200; // Approximate menu width
    const menuHeight = 150; // Approximate menu height
    const windowWidth = window.innerWidth;
    const windowHeight = window.innerHeight;
    
    // Adjust X position if menu would go off right edge
    if (x + menuWidth > windowWidth) {
      x = windowWidth - menuWidth - 10;
    }
    
    // Adjust Y position if menu would go off bottom edge
    if (y + menuHeight > windowHeight) {
      y = y - menuHeight;
    }
    
    // Ensure menu doesn't go off left or top edges
    x = Math.max(10, x);
    y = Math.max(10, y);
    
    this.contextMenuX = x;
    this.contextMenuY = y;
  }

  // Table modification methods
  addColumn(): void {
    if (!this.selectedTable) return;
    
    // Reset form
    this.newColumnName = '';
    this.showColumnDialog = true;
    this.hideContextMenu();
  }

  openColumnDialog(): void {
    this.newColumnName = '';
    this.showColumnDialog = true;
  }

  closeColumnDialog(): void {
    this.showColumnDialog = false;
    this.newColumnName = '';
  }

  confirmAddColumn(): void {
    if (!this.selectedTable || !this.newColumnName.trim()) return;
    
    this.executeStructuralChange('ADD_COLUMN', {
      table: this.selectedTable,
      column: this.newColumnName.trim(),
      columnType: 'TEXT' // Always use TEXT as default
    });
    
    this.closeColumnDialog();
  }

  // Inline table search methods
  setupTableSearch(): void {
    this.tableSearchControl.valueChanges.pipe(
      debounceTime(300),
      distinctUntilChanged()
    ).subscribe(value => {
      this.applyTableFilter(value || '');
    });
  }

  applyTableFilter(filterValue: string): void {
    if (!this.tableData.data || !filterValue.trim()) {
      // No filter, show all data
      this.sortedData = [...this.tableData.data];
      this.filteredRows = this.tableData.data.length;
      return;
    }

    const lowerCaseFilter = filterValue.toLowerCase();
    this.sortedData = this.tableData.data.filter(row => {
      // Search across all columns
      return this.displayedColumns.some(column => {
        const value = row[column];
        if (value === null || value === undefined) return false;
        return String(value).toLowerCase().includes(lowerCaseFilter);
      });
    });
    
    this.filteredRows = this.sortedData.length;
    
    // Apply current sorting if any
    if (this.currentSortColumn && this.currentSortDirection) {
      this.applySorting();
    }
  }

  clearTableSearch(): void {
    this.tableSearchControl.setValue('');
  }

  deleteColumn(): void {
    if (!this.selectedTable || !this.selectedColumnName) return;
    
    this.itemToDelete = {
      type: 'column',
      name: this.selectedColumnName,
      table: this.selectedTable
    };
    this.showDeleteColumnDialog = true;
    this.hideContextMenu();
  }

  confirmDeleteColumn(): void {
    if (!this.itemToDelete || this.itemToDelete.type !== 'column') return;
    
    this.executeStructuralChange('REMOVE_COLUMN', {
      table: this.itemToDelete.table,
      column: this.itemToDelete.name
    });
    
    this.showDeleteColumnDialog = false;
    this.itemToDelete = null;
  }

  cancelDeleteColumn(): void {
    this.showDeleteColumnDialog = false;
    this.itemToDelete = null;
  }

  getDeleteColumnMessage(): string {
    if (!this.itemToDelete) return '';
    return `Are you sure you want to delete column "${this.itemToDelete.name}" from table "${this.itemToDelete.table}"? This action cannot be undone.`;
  }

  addRow(): void {
    if (!this.selectedTable) return;

    // Get the row data from the context menu target
    const targetRowData = this.contextMenuTarget?.rowData;
    const targetRowIndex = this.contextMenuTarget?.rowIndex;
    
    if (!targetRowData) {
      console.error('No target row data found for adding new row');
      return;
    }

    // Store the target row index to position the new row correctly
    this.newlyAddedRowIndex = targetRowIndex + 1; // New row should be right after the target row

    // Execute INSERT statement to actually add row to database
    this.executeStructuralChange('ADD_ROW', {
      table: this.selectedTable,
      targetRowData: targetRowData,
      targetRowIndex: targetRowIndex
    });
    
    this.hideContextMenu();
  }

  deleteRow(): void {
    if (!this.selectedTable || this.selectedRowIndex < 0) return;
    
    const rowData = this.contextMenuTarget?.rowData;
    if (!rowData) return;

    this.itemToDelete = {
      type: 'row',
      rowData: rowData,
      table: this.selectedTable,
      rowIndex: this.selectedRowIndex
    };
    this.showDeleteRowDialog = true;
    this.hideContextMenu();
  }

  confirmDeleteRow(): void {
    if (!this.itemToDelete || this.itemToDelete.type !== 'row') return;
    
    const rowData = this.itemToDelete.rowData;
    const table = this.itemToDelete.table;

    // Try to create WHERE clause from row data first
    const whereConditions: string[] = [];
    Object.keys(rowData).forEach(key => {
      const value = rowData[key];
      if (value !== null && value !== undefined && value !== '') {
        if (typeof value === 'string') {
          whereConditions.push(`${key} = '${value.replace(/'/g, "''")}'`);
        } else {
          whereConditions.push(`${key} = ${value}`);
        }
      }
    });

    // If we have conditions, use them
    if (whereConditions.length > 0) {
      console.log('Using WHERE conditions for row deletion:', whereConditions);
      this.executeStructuralChange('REMOVE_ROW', {
        table: table,
        whereCondition: whereConditions.join(' AND ')
      });
    } else {
      // If no conditions (all values are null/empty), try a different approach
      const allConditions: string[] = [];
      Object.keys(rowData).forEach(key => {
        const value = rowData[key];
        if (value === null || value === undefined) {
          allConditions.push(`${key} IS NULL`);
        } else if (value === '') {
          allConditions.push(`${key} = ''`);
        } else if (typeof value === 'string') {
          allConditions.push(`${key} = '${value.replace(/'/g, "''")}'`);
        } else {
          allConditions.push(`${key} = ${value}`);
        }
      });
      
      console.log('Using all-column conditions for row deletion:', allConditions);
      this.executeStructuralChange('REMOVE_ROW', {
        table: table,
        whereCondition: allConditions.join(' AND ')
      });
    }
    
    this.showDeleteRowDialog = false;
    this.itemToDelete = null;
  }

  cancelDeleteRow(): void {
    this.showDeleteRowDialog = false;
    this.itemToDelete = null;
  }

  getDeleteRowMessage(): string {
    if (!this.itemToDelete) return '';
    return `Are you sure you want to delete this row? This action cannot be undone.`;
  }

  // Cell editing methods
  getActualRowData(rowIndex: number): any {
    if (rowIndex < 0 || rowIndex >= this.tableData.data.length) return null;
    return this.tableData.data[rowIndex];
  }

  startCellEditWithRow(rowData: any, rowIndex: number, columnName: string): void {
    if (!rowData) {
      console.error('Row data is null or undefined');
      return;
    }

    // Create a unique key based on the row data content
    const rowKey = this.createRowKey(rowData);
    const cellKey = `${rowKey}_${columnName}`;
    
    this.editingCells.add(cellKey);
    
    // Initialize with current value from the row data
    this.cellValues[cellKey] = rowData[columnName];
  }

  saveCellEditWithRow(rowData: any, rowIndex: number, columnName: string): void {
    if (!rowData) {
      console.error('Row data is null or undefined');
      return;
    }

    // Create a unique key based on the row data content
    const rowKey = this.createRowKey(rowData);
    const cellKey = `${rowKey}_${columnName}`;
    const newValue = this.cellValues[cellKey];
    
    if (newValue !== undefined) {
      // Update the row data directly
      rowData[columnName] = newValue;
      
      // Execute UPDATE query using the row data for identification
      this.executeCellUpdateWithRowData(rowData, columnName, newValue);
    }
    
    this.editingCells.delete(cellKey);
    delete this.cellValues[cellKey];
  }

  cancelCellEditWithRow(rowData: any, columnName: string): void {
    if (!rowData) {
      console.error('Row data is null or undefined');
      return;
    }

    // Create a unique key based on the row data content
    const rowKey = this.createRowKey(rowData);
    const cellKey = `${rowKey}_${columnName}`;
    
    this.editingCells.delete(cellKey);
    delete this.cellValues[cellKey];
  }

  isCellEditingWithRow(rowData: any, columnName: string): boolean {
    if (!rowData) {
      return false;
    }

    // Create a unique key based on the row data content
    const rowKey = this.createRowKey(rowData);
    const cellKey = `${rowKey}_${columnName}`;
    
    return this.editingCells.has(cellKey);
  }

  getCellValueWithRow(rowData: any, columnName: string): any {
    if (!rowData) {
      return '';
    }

    // Create a unique key based on the row data content
    const rowKey = this.createRowKey(rowData);
    const cellKey = `${rowKey}_${columnName}`;
    
    if (this.isCellEditingWithRow(rowData, columnName)) {
      return this.cellValues[cellKey];
    }
    return rowData[columnName];
  }

  updateCellValueWithRow(rowData: any, columnName: string, value: any): void {
    if (!rowData) {
      console.error('Row data is null or undefined');
      return;
    }

    // Create a unique key based on the row data content
    const rowKey = this.createRowKey(rowData);
    const cellKey = `${rowKey}_${columnName}`;
    
    this.cellValues[cellKey] = value;
  }

  // Method to handle cell editing from context menu
  startCellEditFromContext(): void {
    if (this.contextMenuType === 'cell' && this.contextMenuTarget) {
      const rowData = this.contextMenuTarget.rowData;
      const columnName = this.contextMenuTarget.columnName;
      const rowIndex = this.contextMenuTarget.rowIndex;
      
      this.startCellEditWithRow(rowData, rowIndex, columnName);
      this.hideContextMenu();
    }
  }

  // New method to execute cell update using row data instead of index
  private executeCellUpdateWithRowData(rowData: any, columnName: string, newValue: any): void {
    if (!this.selectedTable) return;

    const whereConditions: string[] = [];

    // Build WHERE clause from all other columns, including NULL values
    Object.keys(rowData).forEach(key => {
      if (key !== columnName) {
        const value = rowData[key];
        if (value === null || value === undefined) {
          whereConditions.push(`${key} IS NULL`);
        } else if (value === '') {
          whereConditions.push(`${key} = ''`);
        } else if (typeof value === 'string') {
          whereConditions.push(`${key} = '${value.replace(/'/g, "''")}'`);
        } else {
          whereConditions.push(`${key} = ${value}`);
        }
      }
    });

    if (whereConditions.length === 0) {
      alert('Cannot update cell: no unique identifiers found in row.');
      return;
    }

    const sql = `UPDATE ${this.selectedTable} SET ${columnName} = '${String(newValue).replace(/'/g, "''")}' WHERE ${whereConditions.join(' AND ')}`;
    
    console.log('Executing cell update:', sql);
    console.log('Row data:', rowData);
    console.log('Where conditions:', whereConditions);
    
    this.apiService.executeSQL(sql).subscribe({
      next: (result) => {
        if (result.success) {
          console.log('Cell update successful');
        } else {
          alert(`Failed to update cell: ${result.error}`);
          // Revert the change
          this.loadTableData(this.selectedTable);
        }
      },
      error: (error) => {
        console.error('Cell update error:', error);
        alert(`Error updating cell: ${error.message || 'Unknown error'}`);
        // Revert the change
        this.loadTableData(this.selectedTable);
      }
    });
  }

  // Helper method to create a unique key for a row based on its content
  private createRowKey(rowData: any): string {
    // Create a hash of the row data to use as a unique identifier
    const rowString = this.displayedColumns
      .map(col => `${col}:${rowData[col]}`)
      .join('|');
    
    // Simple hash function
    let hash = 0;
    for (let i = 0; i < rowString.length; i++) {
      const char = rowString.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // Convert to 32-bit integer
    }
    return Math.abs(hash).toString();
  }

  // Sorting functionality
  sortColumn(columnName: string): void {
    if (this.currentSortColumn === columnName) {
      // Cycle through: asc -> desc -> none
      if (this.currentSortDirection === 'asc') {
        this.currentSortDirection = 'desc';
      } else if (this.currentSortDirection === 'desc') {
        this.currentSortDirection = '';
        this.currentSortColumn = '';
      } else {
        this.currentSortDirection = 'asc';
      }
    } else {
      // New column, start with asc
      this.currentSortColumn = columnName;
      this.currentSortDirection = 'asc';
    }

    this.applySorting();
  }

  private applySorting(): void {
    if (!this.currentSortColumn || !this.currentSortDirection) {
      // No sorting, use original data
      this.sortedData = [...this.tableData.data];
      return;
    }

    this.sortedData = [...this.tableData.data].sort((a, b) => {
      const aVal = a[this.currentSortColumn];
      const bVal = b[this.currentSortColumn];

      // Handle null/undefined values - put them at the end
      if (aVal === null || aVal === undefined) return 1;
      if (bVal === null || bVal === undefined) return -1;

      // Try to compare as numbers first
      const aNum = Number(aVal);
      const bNum = Number(bVal);
      
      // If both are valid numbers, compare numerically
      if (!isNaN(aNum) && !isNaN(bNum) && aNum !== bNum) {
        return this.currentSortDirection === 'asc' ? aNum - bNum : bNum - aNum;
      }

      // Otherwise, compare as strings
      const aStr = String(aVal).toLowerCase();
      const bStr = String(bVal).toLowerCase();

      if (this.currentSortDirection === 'asc') {
        return aStr.localeCompare(bStr);
      } else {
        return bStr.localeCompare(aStr);
      }
    });
  }

  getSortIcon(columnName: string): string {
    if (this.currentSortColumn !== columnName) {
      return 'none'; // No sort
    }
    return this.currentSortDirection === 'asc' ? 'asc' : 'desc';
  }

  getSortDirection(columnName: string): string {
    if (this.currentSortColumn !== columnName) {
      return '';
    }
    return this.currentSortDirection;
  }

  isNewlyAddedRow(rowIndex: number): boolean {
    return rowIndex === this.newlyAddedRowIndex;
  }

  // Backend API calls
  private executeStructuralChange(operationType: string, params: any): void {
    const sql = this.generateStructuralSQL(operationType, params);
    if (!sql) return;

    console.log('Executing structural change:', operationType, params);
    console.log('Generated SQL:', sql);
    
    this.databaseService.executeSQL(sql).subscribe({
      next: (result) => {
        if (result.success) {
          console.log('Structural change successful');
          
          // Refresh both database schema and table data
          this.refreshAfterStructuralChange(operationType);
        } else {
          alert(`Failed to ${operationType.toLowerCase()}: ${result.error}`);
        }
      },
      error: (error) => {
        console.error('Structural change error:', error);
        alert(`Error during ${operationType.toLowerCase()}: ${error.message || 'Unknown error'}`);
      }
    });
  }

  private refreshAfterStructuralChange(operationType?: string): void {
    console.log('Refreshing database schema and table data after structural change...');
    
    // Refresh database info to update schema
    this.loadDatabaseInfo();
    
    // Refresh detailed database info
    this.getDetailedDatabaseInfo();
    
    // Refresh current table data with force refresh
    if (this.selectedTable) {
      // Small delay to ensure database info is updated
      setTimeout(() => {
        console.log('Refreshing table data after structural change...');
        this.loadTableData(this.selectedTable);
        
        // If we just added a row, make it editable after data is loaded
        if (operationType === 'ADD_ROW') {
          this.isRefreshingAfterAdd = true;
          setTimeout(() => {
            console.log('Making newly added row editable...');
            this.makeFirstRowEditable();
            this.isRefreshingAfterAdd = false;
          }, 500);
        }
      }, 800);
    }
  }

  private makeFirstRowEditable(): void {
    if (this.tableData.data.length === 0) return;
    
    // Find the newly added row (the one with the most default values)
    let targetRowIndex = -1;
    let maxDefaultCount = 0;
    
    for (let i = 0; i < this.tableData.data.length; i++) {
      const row = this.tableData.data[i];
      let defaultCount = 0;
      
      this.displayedColumns.forEach(column => {
        const value = row[column];
        if (value === '' || 
            value === 'New Entry' || 
            value === 'example@email.com' || 
            value === 0 || 
            value === 0.0 ||
            value === null ||
            (typeof value === 'string' && value.includes('New Entry'))) {
          defaultCount++;
        }
      });
      
      if (defaultCount > maxDefaultCount) {
        maxDefaultCount = defaultCount;
        targetRowIndex = i;
      }
    }
    
    // If we found a target row, check if it still has placeholder values
    if (targetRowIndex >= 0) {
      const targetRow = this.tableData.data[targetRowIndex];
      let placeholderCount = 0;
      
      this.displayedColumns.forEach(column => {
        const value = targetRow[column];
        if (value === '' || 
            value === 'New Entry' || 
            value === 'example@email.com' || 
            value === 0 || 
            value === 0.0 ||
            value === null ||
            (typeof value === 'string' && value.includes('New Entry'))) {
          placeholderCount++;
        }
      });
      
      // Only make editable if it still has placeholder values
      if (placeholderCount > 0) {
        console.log(`Row ${targetRowIndex} still has ${placeholderCount} placeholder values`);
        
        // Make all cells in the target row editable for easy data entry
        this.displayedColumns.forEach(column => {
          const cellKey = `${targetRowIndex}_${column}`;
          this.editingCells.add(cellKey);
          
          // Initialize with current values from the database
          this.cellValues[cellKey] = this.tableData.data[targetRowIndex][column] || '';
        });
        
        console.log(`Made row ${targetRowIndex} editable for data entry`);
      }
    }
  }

  private generateStructuralSQL(operationType: string, params: any): string {
    const { table, column, columnType, whereCondition, values, targetRowData, targetRowIndex } = params;

    switch (operationType) {
      case 'ADD_COLUMN':
        return `ALTER TABLE ${table} ADD COLUMN ${column} ${columnType || 'TEXT'}`;
      case 'REMOVE_COLUMN':
        return `ALTER TABLE ${table} DROP COLUMN ${column}`;
      case 'ADD_ROW':
        // Generate INSERT statement with proper default values based on column types
        const columnList = this.displayedColumns.join(', ');
        const defaultValues = this.displayedColumns.map(col => {
          const columnType = this.getColumnType(col).toUpperCase();
          const columnName = col.toLowerCase();
          
          if (columnName.includes('id') && (columnType.includes('INTEGER') || columnType.includes('INT'))) {
            return 'NULL'; // Let database auto-generate
          } else if (columnType.includes('INTEGER') || columnType.includes('INT')) {
            return 'NULL'; // Let database use default
          } else if (columnType.includes('REAL') || columnType.includes('FLOAT') || columnType.includes('DOUBLE')) {
            return 'NULL'; // Let database use default
          } else if (columnType.includes('BLOB')) {
            return 'NULL';
          } else {
            return 'NULL'; // Let database use default for text columns
          }
        }).join(', ');
        return `INSERT INTO ${table} (${columnList}) VALUES (${defaultValues})`;
      case 'REMOVE_ROW':
        return `DELETE FROM ${table} WHERE ${whereCondition}`;
      default:
        console.error('Unknown operation type:', operationType);
        return '';
    }
  }



  // Utility methods for template
  getTableIcon(isWhitelisted: boolean): string {
    return isWhitelisted ? '✅' : '❌';
  }

  getColumnTypeColor(type: string): string {
    switch (type.toUpperCase()) {
      case 'INTEGER': return '#2E7D32'; // Dark green
      case 'REAL': return '#1565C0'; // Dark blue
      case 'TEXT': return '#E65100'; // Dark orange
      case 'BLOB': return '#6A1B9A'; // Dark purple
      default: return '#424242'; // Dark grey
    }
  }

  // Debug methods
  logTableState(): void {
    console.log('Current table state:', {
      selectedTable: this.selectedTable,
      tableData: this.tableData,
      tableColumns: this.tableColumns,
      displayedColumns: this.displayedColumns,
      totalRows: this.totalRows,
      filteredRows: this.filteredRows,
      editingCells: Array.from(this.editingCells),
      cellValues: this.cellValues
    });
  }

  // Public method for template to check if cell is highlighted
  isCellHighlighted(table: string, column: string, rowIndex: number): boolean {
    return this.databaseService.isCellHighlighted(table, column, rowIndex);
  }
} 