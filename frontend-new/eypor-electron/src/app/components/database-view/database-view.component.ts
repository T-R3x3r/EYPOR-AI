import { Component, OnInit } from '@angular/core';

interface DatabaseTable {
  name: string;
  rowCount: number;
  columns: TableColumn[];
  isWhitelisted: boolean;
}

interface TableColumn {
  name: string;
  type: string;
  nullable: boolean;
}

@Component({
  selector: 'app-database-view',
  templateUrl: './database-view.component.html',
  styleUrls: ['./database-view.component.css']
})
export class DatabaseViewComponent implements OnInit {
  tables: DatabaseTable[] = [];
  selectedTable: DatabaseTable | null = null;
  isLoading = false;
  whitelistMode = false;

  constructor() {}

  ngOnInit(): void {
    this.loadDatabaseInfo();
  }

  loadDatabaseInfo(): void {
    this.isLoading = true;
    // TODO: Load from service
    setTimeout(() => {
      this.tables = [
        {
          name: 'hubs',
          rowCount: 150,
          isWhitelisted: true,
          columns: [
            { name: 'hub_id', type: 'INTEGER', nullable: false },
            { name: 'hub_name', type: 'TEXT', nullable: false },
            { name: 'location', type: 'TEXT', nullable: true },
            { name: 'capacity', type: 'REAL', nullable: true }
          ]
        },
        {
          name: 'demand',
          rowCount: 1200,
          isWhitelisted: true,
          columns: [
            { name: 'demand_id', type: 'INTEGER', nullable: false },
            { name: 'hub_id', type: 'INTEGER', nullable: false },
            { name: 'amount', type: 'REAL', nullable: false },
            { name: 'date', type: 'TEXT', nullable: false }
          ]
        },
        {
          name: 'routes',
          rowCount: 450,
          isWhitelisted: false,
          columns: [
            { name: 'route_id', type: 'INTEGER', nullable: false },
            { name: 'from_hub', type: 'INTEGER', nullable: false },
            { name: 'to_hub', type: 'INTEGER', nullable: false },
            { name: 'distance', type: 'REAL', nullable: true }
          ]
        }
      ];
      this.isLoading = false;
    }, 1000);
  }

  selectTable(table: DatabaseTable): void {
    this.selectedTable = table;
  }

  toggleWhitelist(table: DatabaseTable): void {
    table.isWhitelisted = !table.isWhitelisted;
    // TODO: Update whitelist via service
  }

  toggleWhitelistMode(): void {
    this.whitelistMode = !this.whitelistMode;
  }

  getTableIcon(isWhitelisted: boolean): string {
    return isWhitelisted ? '✅' : '❌';
  }

  getColumnTypeColor(type: string): string {
    switch (type.toUpperCase()) {
      case 'INTEGER': return '#4CAF50';
      case 'REAL': return '#2196F3';
      case 'TEXT': return '#FF9800';
      default: return '#9E9E9E';
    }
  }
} 