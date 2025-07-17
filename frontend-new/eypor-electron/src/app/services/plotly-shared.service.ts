import { Injectable } from '@angular/core';

declare var Plotly: any;

@Injectable({
  providedIn: 'root'
})
export class PlotlySharedService {
  private plotlyInstance: any = null;
  private isPlotlyLoaded = false;
  private loadPromise: Promise<any> | null = null;

  constructor() {
    this.initializePlotly();
  }

  private initializePlotly(): void {
    // Check if Plotly is already available globally
    if (typeof Plotly !== 'undefined') {
      this.plotlyInstance = Plotly;
      this.isPlotlyLoaded = true;
      return;
    }

    // If not available, create a promise to load it
    this.loadPromise = this.loadPlotlyFromCDN();
  }

  private loadPlotlyFromCDN(): Promise<any> {
    return new Promise((resolve, reject) => {
      // Check if script is already loaded
      const existingScript = document.querySelector('script[src*="plotly"]');
      if (existingScript) {
        // Wait for existing script to load
        const checkPlotly = () => {
          if (typeof Plotly !== 'undefined') {
            this.plotlyInstance = Plotly;
            this.isPlotlyLoaded = true;
            resolve(Plotly);
          } else {
            setTimeout(checkPlotly, 100);
          }
        };
        checkPlotly();
        return;
      }

      // Load Plotly from CDN
      const script = document.createElement('script');
      script.src = 'https://cdn.plot.ly/plotly-latest.min.js';
      script.onload = () => {
        if (typeof Plotly !== 'undefined') {
          this.plotlyInstance = Plotly;
          this.isPlotlyLoaded = true;
          resolve(Plotly);
        } else {
          reject(new Error('Plotly failed to load'));
        }
      };
      script.onerror = () => {
        reject(new Error('Failed to load Plotly from CDN'));
      };
      document.head.appendChild(script);
    });
  }

  public getPlotly(): Promise<any> {
    if (this.isPlotlyLoaded && this.plotlyInstance) {
      return Promise.resolve(this.plotlyInstance);
    }
    
    if (this.loadPromise) {
      return this.loadPromise;
    }
    
    // Fallback: try to load again
    this.loadPromise = this.loadPlotlyFromCDN();
    return this.loadPromise;
  }

  public isReady(): boolean {
    return this.isPlotlyLoaded && this.plotlyInstance !== null;
  }

  public newPlot(element: HTMLElement, data: any[], layout?: any, config?: any): Promise<any> {
    return this.getPlotly().then(plotly => {
      return plotly.newPlot(element, data, layout, config);
    });
  }

  public react(element: HTMLElement, data: any[], layout?: any, config?: any): Promise<any> {
    return this.getPlotly().then(plotly => {
      return plotly.react(element, data, layout, config);
    });
  }

  public purge(element: HTMLElement): void {
    if (this.plotlyInstance) {
      this.plotlyInstance.purge(element);
    }
  }

  public resize(element: HTMLElement): void {
    if (this.plotlyInstance) {
      this.plotlyInstance.relayout(element, {});
    }
  }
} 