import { Component, OnInit, OnDestroy, AfterViewInit, ViewChild } from '@angular/core';
import { FormControl } from '@angular/forms';
import { MatTableDataSource } from '@angular/material/table';
import { MatSort } from '@angular/material/sort';
import { ApiService, WhitelistResponse, WhitelistUpdateResponse } from '../../services/api.service';
import { DatabaseTrackingService } from '../../services/database-tracking.service';
import { Subscription } from 'rxjs';
import { debounceTime, distinctUntilChanged } from 'rxjs/operators';

interface DatabaseInfo {
  tables: any[];
  total_tables: number;
  database_path: string;
  table_mappings: any;
}

interface TableColumn {
  name: string;
  type: string;
}

@Component({
  selector: 'app-sql-query',
  templateUrl: './sql-query.component.html',
  styleUrls: ['./sql-query.component.css']
})
export class SqlQueryComponent implements OnInit, OnDestroy, AfterViewInit {
  @ViewChild(MatSort) sort!: MatSort;

  // Database info
  databaseInfo: DatabaseInfo | null = null;
  detailedDbInfo: any = null;
  isLoading = false;

  // Table browser
  selectedTable = '';
  tableData = new MatTableDataSource<any>([]);
  tableColumns: TableColumn[] = [];
  displayedColumns: string[] = [];
  loadingTableData = false;

  // Search functionality
  globalSearchControl = new FormControl('');

  // Statistics
  totalRows = 0;
  filteredRows = 0;

  // Debug
  lastError = '';
  showDebug = false; // Debug menu hidden by default
  isRefreshing = false; // Track refresh button state

  // Whitelist management
  whitelistData: WhitelistResponse | null = null;
  whitelistLoading = false;
  selectAllEnabled = false;

  // UI state for collapsible sections
  showDatabaseOverview = false;
  showModificationPermissions = false;

  // Context menu properties
  showContextMenu = false;
  contextMenuX = 0;
  contextMenuY = 0;
  contextMenuType: 'column' | 'row' | 'cell' | null = null;
  contextMenuTarget: any = null;
  selectedRowIndex = -1;
  selectedColumnName = '';
  
  // Cell editing properties
  editingCells: Set<string> = new Set();
  cellValues: { [key: string]: any } = {};
  
  // Track newly added rows for editing
  newlyAddedRowIndex: number = -1;
  private isRefreshingAfterAdd: boolean = false;

  private subscriptions: Subscription[] = [];

  constructor(
    private apiService: ApiService,
    private databaseTracking: DatabaseTrackingService
  ) {}

  ngOnInit(): void {
    this.loadDatabaseInfo();
    this.setupSearch();
    
    // Subscribe to database changes
    const changesSub = this.databaseTracking.getChanges().subscribe(changes => {
      if (changes.length > 0) {
        console.log('Database changes detected, refreshing...', changes);
        this.loadDatabaseInfo();
        // Refresh current table if one is selected
        if (this.selectedTable) {
          this.loadCompleteTable(this.selectedTable);
        }
      }
    });
    this.subscriptions.push(changesSub);

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
    // Setup sort after view init
    this.tableData.sort = this.sort;
  }

  ngOnDestroy(): void {
    this.subscriptions.forEach(sub => sub.unsubscribe());
  }

  setupSearch(): void {
    const globalSearchSub = this.globalSearchControl.valueChanges
      .pipe(debounceTime(300), distinctUntilChanged())
      .subscribe(value => {
        this.applyGlobalFilter(value || '');
      });
    
    this.subscriptions.push(globalSearchSub);
  }

  loadDatabaseInfo(): void {
    this.isLoading = true;
    this.apiService.getDatabaseInfo().subscribe({
      next: (data) => {
        console.log('Database info received:', data);
        this.databaseInfo = data;
        if (data && data.database_path) {
          this.getDetailedDatabaseInfo();
          // Load whitelist data after database info is available
          this.loadWhitelistData();
        }
        this.isLoading = false;
      },
      error: (error) => {
        console.error('Error loading database info:', error);
        this.isLoading = false;
      }
    });
  }

  getDetailedDatabaseInfo(): void {
    this.apiService.getDetailedDatabaseInfo().subscribe({
      next: (data) => {
        console.log('Detailed database info received:', data);
        if (data && data.database_file) {
          this.detailedDbInfo = {
            file_size: `${data.database_file.size_mb} MB (${data.database_file.size_bytes} bytes)`,
            created_date: data.database_file.created,
            modified_date: data.database_file.modified,
            sqlite_version: 'SQLite 3.x',
            filename: data.database_file.filename,
            path: data.database_file.path
          };
        }
      },
      error: (error) => {
        console.error('Error loading detailed database info:', error);
      }
    });
  }

  // New method for comprehensive refresh (called by the refresh button)
  refreshDatabaseInfo(): void {
    console.log('Refreshing database info and current table...');
    this.isRefreshing = true;
    
    // First, refresh the basic database info
    this.loadDatabaseInfo();
    
    // Then refresh detailed info
    this.getDetailedDatabaseInfo();
    
    // Refresh whitelist data
    this.loadWhitelistData();
    
    // If a table is currently selected, reload its data
    if (this.selectedTable) {
      console.log('Refreshing current table data:', this.selectedTable);
      this.loadCompleteTable(this.selectedTable);
    }
    
    // Clear any previous errors
    this.lastError = '';
    
    // Reset refresh state after a brief delay to show feedback
    setTimeout(() => {
      this.isRefreshing = false;
    }, 1500);
  }

  // Enhanced table loading - loads ALL data for better searching/filtering
  loadCompleteTable(tableName: string): void {
    if (!tableName) {
      console.log('No table name provided');
      return;
    }
    
    console.log('Loading table:', tableName);
    this.selectedTable = tableName;
    this.loadingTableData = true;
    this.totalRows = 0;
    this.filteredRows = 0;
    this.lastError = '';
    
    // Clear any editing state when switching tables
    this.editingCells.clear();
    this.cellValues = {};
    this.newlyAddedRowIndex = -1;
    
    // Load table data directly and extract columns from the result
    const sqlQuery = `SELECT * FROM ${tableName}`;
    console.log('Executing SQL query:', sqlQuery);
    
    this.apiService.executeSQL(sqlQuery).subscribe({
      next: (queryResult) => {
        console.log('Query result received:', queryResult);
        console.log('Result type:', typeof queryResult);
        console.log('Result success:', queryResult.success);
        console.log('Result data length:', queryResult.result?.length);
        
        if (queryResult.success && queryResult.result && queryResult.result.length > 0) {
          const data = queryResult.result;
          this.totalRows = data.length;
          this.filteredRows = data.length;
          
          // Extract column names from the first row of data
          const firstRow = data[0];
          this.displayedColumns = Object.keys(firstRow);
          
          // Create table columns with default types
          this.tableColumns = this.displayedColumns.map(colName => ({
            name: colName,
            type: this.guessColumnType(firstRow[colName])
          }));
          
          console.log('Extracted columns:', this.displayedColumns);
          console.log('Setting table data with', data.length, 'rows');
          console.log('First few rows of data:', data.slice(0, 3));
          
          // Check for any rows with placeholder values
          data.forEach((row: any, index: number) => {
            let placeholderCount = 0;
            this.displayedColumns.forEach(column => {
              const value = row[column];
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
            if (placeholderCount > 0) {
              console.log(`Row ${index} has ${placeholderCount} placeholder values:`, row);
            }
          });
          
          // Set up the Material table data source with proper sorting configuration
          this.tableData = new MatTableDataSource(data);
          
          // Configure sorting data accessor immediately
          this.tableData.sortingDataAccessor = (item: any, property: string) => {
            const value = item[property];
            // Handle null/undefined values for proper sorting
            if (value === null || value === undefined) return '';
            // Detect column type
            const colType = this.getColumnType(property).toUpperCase();
            if (colType.includes('INT') || colType.includes('REAL') || colType.includes('FLOAT') || colType.includes('DOUBLE') || typeof value === 'number') {
              return Number(value);
            }
            // Otherwise, sort as string
            return String(value).toLowerCase();
          };
          
          // Reconnect sort after data change
          setTimeout(() => {
            if (this.sort) {
              this.tableData.sort = this.sort;
              console.log('Sort connected');
            }
          });
          
          console.log('Table data setup complete. Total rows:', this.totalRows);
        } else if (queryResult.success && queryResult.result && queryResult.result.length === 0) {
          // Table exists but is empty
          console.log('Table is empty');
          this.totalRows = 0;
          this.filteredRows = 0;
          this.displayedColumns = [];
          this.tableColumns = [];
          this.tableData = new MatTableDataSource<any>([]);
          this.lastError = 'Table is empty (0 rows)';
        } else {
          console.error('Query failed or no result data:', queryResult);
          this.totalRows = 0;
          this.filteredRows = 0;
          this.displayedColumns = [];
          this.tableColumns = [];
          this.tableData = new MatTableDataSource<any>([]);
          this.lastError = queryResult.error || 'Failed to load table data';
        }
        
        this.loadingTableData = false;
      },
      error: (error) => {
        console.error('Error loading table data:', error);
        const errorMsg = error.error?.detail || error.message || JSON.stringify(error);
        this.lastError = `SQL Error: ${errorMsg}`;
        this.totalRows = 0;
        this.filteredRows = 0;
        this.displayedColumns = [];
        this.tableColumns = [];
        this.tableData = new MatTableDataSource<any>([]);
        this.loadingTableData = false;
      }
    });
  }

  // Helper method to guess column type from value
  private guessColumnType(value: any): string {
    if (value === null || value === undefined) return 'TEXT';
    if (typeof value === 'number') {
      if (Number.isInteger(value)) return 'INTEGER';
      return 'REAL';
    }
    if (typeof value === 'boolean') return 'BOOLEAN';
    if (typeof value === 'string') {
      // Try to detect if it's a date
      if (value.match(/^\d{4}-\d{2}-\d{2}/) || value.match(/\d{2}\/\d{2}\/\d{4}/)) {
        return 'DATE';
      }
      return 'TEXT';
    }
    return 'TEXT';
  }

  applyGlobalFilter(filterValue: string): void {
    // Custom filter that searches across all columns
    this.tableData.filterPredicate = (data: any, filter: string) => {
      const searchTerm = filter.toLowerCase();
      
      // Search in all columns
      return this.displayedColumns.some(column => {
        const cellValue = data[column];
        if (cellValue == null) return false;
        return cellValue.toString().toLowerCase().includes(searchTerm);
      });
    };
    
    this.tableData.filter = filterValue.trim().toLowerCase();
    this.filteredRows = this.tableData.filteredData.length;
    

  }

  // Utility methods
  getDatabaseStatus(): string {
    return this.databaseInfo?.database_path ? 'Available' : 'Not Available';
  }

  getTableRowCount(tableName: string): number {
    const table = this.databaseInfo?.tables?.find(t => t.name === tableName);
    return table?.row_count || 0;
  }

  formatCellValue(value: any): string {
    if (value == null) return '';
    if (typeof value === 'object') return JSON.stringify(value);
    return value.toString();
  }

  clearSearch(): void {
    this.globalSearchControl.setValue('');
  }

  getColumnType(columnName: string): string {
    const column = this.tableColumns.find(col => col.name === columnName);
    return column?.type || 'TEXT';
  }

  downloadDatabase(): void {
    this.apiService.downloadDatabase().subscribe({
      next: (blob) => {
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = 'project_data.db';
        link.click();
        window.URL.revokeObjectURL(url);
      },
      error: (error) => {
        console.error('Error downloading database:', error);
        alert('Failed to download database');
      }
    });
  }

  exportDatabase(format: string): void {
    this.apiService.exportDatabase(format).subscribe({
      next: (blob) => {
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        
        let filename = 'database_export';
        let extension = '.zip';
        
        if (format === 'sql') {
          filename = 'database_export.sql';
          extension = '';
        } else if (format === 'csv') {
          filename = 'database_export_csv.zip';
          extension = '';
        }
        
        link.download = filename + extension;
        link.click();
        window.URL.revokeObjectURL(url);
      },
      error: (error) => {
        console.error('Error exporting database:', error);
        alert('Failed to export database');
      }
    });
  }

  // Debug methods
  getApiBaseUrl(): string {
    return this.apiService['baseUrl'] || 'Unknown';
  }

  toggleDebug(): void {
    this.showDebug = !this.showDebug;
  }

  testDatabaseConnection(): void {
    console.log('Testing database connection...');
    this.lastError = 'Testing connection...';
    
    this.apiService.getDatabaseInfo().subscribe({
      next: (data) => {
        console.log('Database info test successful:', data);
        this.lastError = `Connection OK: ${data.total_tables} tables found`;
      },
      error: (error) => {
        console.error('Database connection test failed:', error);
        const errorMsg = error.error?.detail || error.message || JSON.stringify(error);
        this.lastError = `Connection Failed: ${errorMsg}`;
      }
    });
  }

  // Toggle methods for collapsible sections
  toggleDatabaseOverview(): void {
    this.showDatabaseOverview = !this.showDatabaseOverview;
  }

  toggleModificationPermissions(): void {
    this.showModificationPermissions = !this.showModificationPermissions;
  }

  loadWhitelistData(): void {
    this.apiService.getDatabaseWhitelist().subscribe({
      next: (data: WhitelistResponse) => {
        console.log('Whitelist data received:', data);
        this.whitelistData = data;
        this.updateSelectAllState();
      },
      error: (error: any) => {
        console.error('Error loading whitelist data:', error);
      }
    });
  }

  // Whitelist management methods
  updateSelectAllState(): void {
    if (!this.whitelistData) {
      this.selectAllEnabled = false;
      return;
    }
    this.selectAllEnabled = this.whitelistData.whitelist.length === this.whitelistData.available_tables.length;
  }

  isTableWhitelisted(tableName: string): boolean {
    return this.whitelistData?.whitelist.includes(tableName) || false;
  }

  toggleTableWhitelist(tableName: string): void {
    if (!this.whitelistData) return;

    this.whitelistLoading = true;
    let updatedWhitelist = [...this.whitelistData.whitelist];

    if (this.isTableWhitelisted(tableName)) {
      // Remove from whitelist
      updatedWhitelist = updatedWhitelist.filter(name => name !== tableName);
    } else {
      // Add to whitelist
      updatedWhitelist.push(tableName);
    }

    this.updateWhitelist(updatedWhitelist);
  }

  toggleSelectAll(): void {
    if (!this.whitelistData) return;

    this.whitelistLoading = true;
    const newWhitelist = this.selectAllEnabled ? [] : [...this.whitelistData.available_tables];
    this.updateWhitelist(newWhitelist);
  }

  private updateWhitelist(newWhitelist: string[]): void {
    this.apiService.updateDatabaseWhitelist(newWhitelist).subscribe({
      next: (response: WhitelistUpdateResponse) => {
        console.log('Whitelist updated successfully:', response);
        // Reload whitelist data to get the current state
        this.loadWhitelistData();
        this.whitelistLoading = false;
      },
      error: (error: any) => {
        console.error('Error updating whitelist:', error);
        this.whitelistLoading = false;
        // Optionally show an error message to the user
        alert('Failed to update table whitelist. Please try again.');
      }
    });
  }

  // Context menu methods
  onColumnRightClick(event: MouseEvent, columnName: string): void {
    event.preventDefault();
    this.showContextMenu = true;
    this.contextMenuX = event.clientX;
    this.contextMenuY = event.clientY;
    this.contextMenuType = 'column';
    this.selectedColumnName = columnName;
    this.contextMenuTarget = { columnName };
  }

  onRowRightClick(event: MouseEvent, rowData: any, rowIndex: number): void {
    event.preventDefault();
    this.showContextMenu = true;
    this.contextMenuX = event.clientX;
    this.contextMenuY = event.clientY;
    this.contextMenuType = 'row';
    this.selectedRowIndex = rowIndex;
    this.contextMenuTarget = { rowData, rowIndex };
  }

  onCellRightClick(event: MouseEvent, rowData: any, columnName: string, rowIndex: number): void {
    event.preventDefault();
    this.showContextMenu = true;
    this.contextMenuX = event.clientX;
    this.contextMenuY = event.clientY;
    this.contextMenuType = 'cell';
    this.selectedRowIndex = rowIndex;
    this.selectedColumnName = columnName;
    this.contextMenuTarget = { rowData, columnName, rowIndex };
  }

  hideContextMenu(): void {
    this.showContextMenu = false;
    this.contextMenuType = null;
    this.contextMenuTarget = null;
  }

  // Table modification methods
  addColumn(): void {
    if (!this.selectedTable) return;
    
    const columnName = prompt('Enter new column name:');
    if (!columnName || columnName.trim() === '') return;
    
    const columnType = prompt('Enter column type (TEXT, INTEGER, REAL, BLOB):', 'TEXT');
    if (!columnType || columnType.trim() === '') return;

    this.executeStructuralChange('ADD_COLUMN', {
      table: this.selectedTable,
      column: columnName.trim(),
      columnType: columnType.trim()
    });
    this.hideContextMenu();
  }

  deleteColumn(): void {
    if (!this.selectedTable || !this.selectedColumnName) return;
    
    const confirmed = confirm(`Are you sure you want to delete column "${this.selectedColumnName}"? This action cannot be undone.`);
    if (!confirmed) return;

    this.executeStructuralChange('REMOVE_COLUMN', {
      table: this.selectedTable,
      column: this.selectedColumnName
    });
    this.hideContextMenu();
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
    // Let the database handle default values instead of sending placeholder values
    this.executeStructuralChange('ADD_ROW', {
      table: this.selectedTable,
      targetRowData: targetRowData,
      targetRowIndex: targetRowIndex
    });
    
    this.hideContextMenu();
  }

  deleteRow(): void {
    if (!this.selectedTable || this.selectedRowIndex < 0) return;
    
    const confirmed = confirm('Are you sure you want to delete this row? This action cannot be undone.');
    if (!confirmed) return;

    const rowData = this.contextMenuTarget?.rowData;
    if (!rowData) return;

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
        table: this.selectedTable,
        whereCondition: whereConditions.join(' AND ')
      });
    } else {
      // If no conditions (all values are null/empty), try a different approach
      // Create a WHERE clause that includes all columns with their actual values (including nulls)
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
        table: this.selectedTable,
        whereCondition: allConditions.join(' AND ')
      });
    }
    
    this.hideContextMenu();
  }

  // Helper method to get the actual row data from the current view
  getActualRowData(rowIndex: number): any {
    // Get the actual row from the current data source (which may be sorted/filtered)
    const actualData = this.tableData.filteredData || this.tableData.data;
    return actualData[rowIndex];
  }

  // NEW METHODS THAT WORK WITH ROW DATA DIRECTLY
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
          this.loadCompleteTable(this.selectedTable);
        }
      },
      error: (error) => {
        console.error('Cell update error:', error);
        alert(`Error updating cell: ${error.message || 'Unknown error'}`);
        // Revert the change
        this.loadCompleteTable(this.selectedTable);
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

  // Debug method to log current table state
  logTableState(): void {
    console.log('=== Table State Debug ===');
    console.log('Total rows:', this.totalRows);
    console.log('Filtered rows:', this.filteredRows);
    console.log('Original data length:', this.tableData.data.length);
    console.log('Filtered data length:', this.tableData.filteredData?.length || 'undefined');
    console.log('Current sort state:', this.tableData.sort?.direction || 'none');
    console.log('Current sort active:', this.tableData.sort?.active || 'none');
    console.log('First few rows of original data:', this.tableData.data.slice(0, 3));
    console.log('First few rows of filtered data:', this.tableData.filteredData?.slice(0, 3) || 'undefined');
    
    // Test sorting manually
    if (this.tableData.sort?.active) {
      console.log('=== Manual Sort Test ===');
      const testData = [...this.tableData.data];
      const sortColumn = this.tableData.sort.active;
      const sortDirection = this.tableData.sort.direction;
      
      testData.sort((a, b) => {
        const aVal = a[sortColumn] || '';
        const bVal = b[sortColumn] || '';
        const aStr = String(aVal).toLowerCase();
        const bStr = String(bVal).toLowerCase();
        
        if (sortDirection === 'asc') {
          return aStr.localeCompare(bStr);
        } else {
          return bStr.localeCompare(aStr);
        }
      });
      
      console.log('Manually sorted first 5 rows:', testData.slice(0, 5).map(row => row[sortColumn]));
      console.log('Current filtered data first 5 rows:', this.tableData.filteredData?.slice(0, 5).map(row => row[sortColumn]) || 'undefined');
    }
    
    console.log('=== End Table State Debug ===');
  }

  // Test method to check data at specific indices
  testDataAtIndex(index: number): void {
    console.log('=== Test Data at Index ===');
    console.log('Testing index:', index);
    console.log('Original data at index:', this.tableData.data[index]);
    console.log('Filtered data at index:', this.tableData.filteredData?.[index]);
    console.log('getActualRowData result:', this.getActualRowData(index));
    console.log('=== End Test ===');
  }

  // Method to force a proper sort
  forceSort(): void {
    if (!this.tableData.sort?.active) {
      console.log('No active sort to force');
      return;
    }

    console.log('Forcing sort on column:', this.tableData.sort.active);
    
    // Manually sort the data
    const sortColumn = this.tableData.sort.active;
    const sortDirection = this.tableData.sort.direction;
    
    this.tableData.data.sort((a, b) => {
      const aVal = a[sortColumn] || '';
      const bVal = b[sortColumn] || '';
      const aStr = String(aVal).toLowerCase();
      const bStr = String(bVal).toLowerCase();
      
      if (sortDirection === 'asc') {
        return aStr.localeCompare(bStr);
      } else {
        return bStr.localeCompare(aStr);
      }
    });
    
    // Trigger change detection
    this.tableData._updateChangeSubscription();
    
    console.log('Sort forced. First 5 rows:', this.tableData.data.slice(0, 5).map(row => row[sortColumn]));
  }

  isNewlyAddedRow(rowIndex: number): boolean {
    if (this.newlyAddedRowIndex < 0) return false;
    
    // Check if this row has default values (indicating it's newly added)
    const row = this.tableData.data[rowIndex];
    if (!row) return false;
    
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
    
    // Consider it a newly added row if it has mostly default values
    return defaultCount >= Math.floor(this.displayedColumns.length / 2);
  }

  // Backend API calls
  private executeStructuralChange(operationType: string, params: any): void {
    const sql = this.generateStructuralSQL(operationType, params);
    if (!sql) return;

    console.log('Executing structural change:', operationType, params);
    console.log('Generated SQL:', sql);
    console.log('SQL parameters:', { table: params.table, whereCondition: params.whereCondition });
    
    this.apiService.executeSQL(sql).subscribe({
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
        this.forceDataRefresh();
        
        // If we just added a row, make it editable after data is loaded
        if (operationType === 'ADD_ROW') {
          this.isRefreshingAfterAdd = true;
          setTimeout(() => {
            console.log('Making newly added row editable...');
            this.makeFirstRowEditable();
            this.isRefreshingAfterAdd = false;
          }, 500); // Increased delay to ensure data is fully loaded
        }
      }, 800); // Increased delay to ensure database is fully updated
    }
  }

  // Force a complete data refresh to ensure UI shows actual database values
  private forceDataRefresh(): void {
    if (!this.selectedTable) return;
    
    console.log('Forcing complete data refresh...');
    
    // Clear current data
    this.tableData.data = [];
    this.totalRows = 0;
    this.filteredRows = 0;
    
    // Reload from database
    this.loadCompleteTable(this.selectedTable);
  }

  private makeFirstRowEditable(): void {
    if (this.tableData.data.length === 0) return;
    
    let targetRowIndex = -1;
    
    // First, try to use the tracked newly added row index
    if (this.newlyAddedRowIndex >= 0 && this.newlyAddedRowIndex < this.tableData.data.length) {
      targetRowIndex = this.newlyAddedRowIndex;
      console.log(`Using tracked newly added row index: ${targetRowIndex}`);
    } else {
      // Fallback: find the row with the most default values
      let maxDefaultCount = 0;
      
      for (let i = 0; i < this.tableData.data.length; i++) {
        const row = this.tableData.data[i];
        let defaultCount = 0;
        
        this.displayedColumns.forEach(column => {
          const value = row[column];
          // Check for various default value patterns
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
      
      console.log(`Found row with most default values: ${targetRowIndex} (${maxDefaultCount} defaults)`);
      
      // If we found a row with mostly default values, check if it's actually a newly added row
      // by looking for the last row in the table (new rows are typically added at the end)
      if (maxDefaultCount > 0) {
        const lastRowIndex = this.tableData.data.length - 1;
        const lastRow = this.tableData.data[lastRowIndex];
        let lastRowDefaultCount = 0;
        
        this.displayedColumns.forEach(column => {
          const value = lastRow[column];
          if (value === '' || 
              value === 'New Entry' || 
              value === 'example@email.com' || 
              value === 0 || 
              value === 0.0 ||
              value === null ||
              (typeof value === 'string' && value.includes('New Entry'))) {
            lastRowDefaultCount++;
          }
        });
        
        // If the last row has more defaults, use that instead
        if (lastRowDefaultCount >= maxDefaultCount) {
          targetRowIndex = lastRowIndex;
          console.log(`Using last row as newly added row: ${targetRowIndex} (${lastRowDefaultCount} defaults)`);
        }
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
        
        // If we still have placeholder values and we're not already refreshing, try one more force refresh
        if (placeholderCount >= Math.floor(this.displayedColumns.length / 2) && !this.isRefreshingAfterAdd) {
          console.log('Too many placeholder values, forcing another data refresh...');
          this.isRefreshingAfterAdd = true;
          setTimeout(() => {
            this.forceDataRefresh();
            setTimeout(() => {
              this.makeFirstRowEditable();
              this.isRefreshingAfterAdd = false;
            }, 300);
          }, 200);
          return;
        }
        
        console.log(`Making row ${targetRowIndex} editable for data entry`);
        
        // Make all cells in the target row editable for easy data entry
        this.displayedColumns.forEach(column => {
          const cellKey = `${targetRowIndex}_${column}`;
          this.editingCells.add(cellKey);
          
          // Initialize with current values from the database
          this.cellValues[cellKey] = this.tableData.data[targetRowIndex][column] || '';
        });
        

        
        console.log(`Made row ${targetRowIndex} editable for data entry`);
      } else {
        console.log(`Row ${targetRowIndex} has no placeholder values, data was properly refreshed from database`);
      }
      
      // Reset the tracked index
      this.newlyAddedRowIndex = -1;
    } else {
      console.log('No suitable row found to make editable');
    }
  }

  // New method to reorder table data to position new row correctly
  private reorderTableDataToPositionNewRow(): void {
    if (this.newlyAddedRowIndex < 0 || this.newlyAddedRowIndex >= this.tableData.data.length) {
      return;
    }

    // Get the current data
    const currentData = [...this.tableData.data];
    
    // Find the newly added row (the one with the most default values)
    let newRowIndex = -1;
    let maxDefaultCount = 0;
    
    for (let i = 0; i < currentData.length; i++) {
      const row = currentData[i];
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
        newRowIndex = i;
      }
    }
    
    if (newRowIndex >= 0 && newRowIndex !== this.newlyAddedRowIndex) {
      // Move the new row to the desired position
      const newRow = currentData.splice(newRowIndex, 1)[0];
      currentData.splice(this.newlyAddedRowIndex, 0, newRow);
      
      // Update the table data
      this.tableData.data = currentData;
      
      console.log(`Moved new row from position ${newRowIndex} to position ${this.newlyAddedRowIndex}`);
    }
  }

  // Alternative approach: Use a temporary table with proper ordering
  private createTemporaryTableWithOrderedData(): void {
    if (this.newlyAddedRowIndex < 0) return;
    
    // This is a more complex approach that would require creating a temporary table
    // with the new row in the correct position, then replacing the original table
    // For now, we'll stick with the frontend reordering approach
    console.log('Temporary table approach not implemented yet');
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
}