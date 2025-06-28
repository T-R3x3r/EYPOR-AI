import { Component, OnInit, OnDestroy, AfterViewInit, ViewChild } from '@angular/core';
import { FormControl } from '@angular/forms';
import { MatTableDataSource } from '@angular/material/table';
import { MatPaginator } from '@angular/material/paginator';
import { MatSort } from '@angular/material/sort';
import { ApiService } from '../../services/api.service';
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
  @ViewChild(MatPaginator) paginator!: MatPaginator;
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
    // Setup paginator and sort after view init
    this.tableData.paginator = this.paginator;
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
          
          // Set up the Material table data source
          this.tableData = new MatTableDataSource(data);
          
          // Reconnect paginator and sort after data change
          setTimeout(() => {
            if (this.paginator) {
              this.tableData.paginator = this.paginator;
              this.paginator.pageSize = 50; // Default page size
              this.paginator.pageSizeOptions = [25, 50, 100, 250, 500];
              console.log('Paginator connected');
            }
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
    
    // Reset to first page when filtering
    if (this.paginator) {
      this.paginator.firstPage();
    }
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
} 