import { Component } from '@angular/core';

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css']
})
export class AppComponent {
  // This component now just serves as a router outlet container
  
  constructor() {
    console.log('App component initialized');
  }
} 