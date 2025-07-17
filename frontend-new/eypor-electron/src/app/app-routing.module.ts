import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { FileSelectionComponent } from './components/file-selection/file-selection.component';
import { WorkbenchComponent } from './components/workbench/workbench.component';

const routes: Routes = [
  { path: '', component: FileSelectionComponent },
  { path: 'workbench', component: WorkbenchComponent },
  { path: '**', redirectTo: '' }
];

@NgModule({
  imports: [RouterModule.forRoot(routes, { enableTracing: true })],
  exports: [RouterModule]
})
export class AppRoutingModule { } 