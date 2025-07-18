import { NgModule } from '@angular/core';
import { BrowserModule } from '@angular/platform-browser';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { HttpClientModule } from '@angular/common/http';
import { BrowserAnimationsModule } from '@angular/platform-browser/animations';

// Angular Material imports
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatTableModule } from '@angular/material/table';
import { MatSortModule } from '@angular/material/sort';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatTabsModule } from '@angular/material/tabs';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatChipsModule } from '@angular/material/chips';
import { MatDialogModule } from '@angular/material/dialog';
import { MatMenuModule } from '@angular/material/menu';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatSidenavModule } from '@angular/material/sidenav';
import { MatListModule } from '@angular/material/list';
import { MatOptionModule } from '@angular/material/core';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatDividerModule } from '@angular/material/divider';

// App components
import { AppComponent } from './app.component';
import { FileSelectionComponent } from './components/file-selection/file-selection.component';
import { WorkbenchComponent } from './components/workbench/workbench.component';
import { UploadedFilesComponent } from './components/uploaded-files/uploaded-files.component';
import { UserQueriesComponent } from './components/user-queries/user-queries.component';
import { DatabaseViewComponent } from './components/database-view/database-view.component';
import { ChatInterfaceComponent } from './components/chat-interface/chat-interface.component';
import { CodeEditorComponent } from './components/code-editor/code-editor.component';
import { ConfirmationDialogComponent } from './components/confirmation-dialog/confirmation-dialog.component';
import { WorkbenchOutputComponent } from './components/workbench-output/workbench-output.component';
import { PlotlyChartComponent } from './components/plotly-chart/plotly-chart.component';

// Services
import { DatabaseService } from './services/database.service';

// Pipes
import { SafePipe } from './pipes/safe.pipe';

// App routing
import { AppRoutingModule } from './app-routing.module';

@NgModule({
  declarations: [
    AppComponent,
    FileSelectionComponent,
    WorkbenchComponent,
    UploadedFilesComponent,
    UserQueriesComponent,
    DatabaseViewComponent,
    ChatInterfaceComponent,
    CodeEditorComponent,
    ConfirmationDialogComponent,
    WorkbenchOutputComponent,
    PlotlyChartComponent,
    SafePipe
  ],
  imports: [
    BrowserModule,
    BrowserAnimationsModule,
    FormsModule,
    ReactiveFormsModule,
    HttpClientModule,
    AppRoutingModule,
    
    // Material modules
    MatButtonModule,
    MatCardModule,
    MatIconModule,
    MatTableModule,
    MatSortModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatTabsModule,
    MatProgressSpinnerModule,
    MatChipsModule,
    MatDialogModule,
    MatMenuModule,
    MatToolbarModule,
    MatSidenavModule,
    MatListModule,
    MatOptionModule,
    MatSlideToggleModule,
    MatExpansionModule,
    MatDividerModule
  ],
  providers: [DatabaseService],
  bootstrap: [AppComponent]
})
export class AppModule { } 