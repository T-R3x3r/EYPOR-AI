import { Component, Input, OnInit, OnDestroy, ViewChild, ElementRef, AfterViewInit, OnChanges, SimpleChanges, ChangeDetectorRef } from '@angular/core';
import { ThemeService } from '../../services/theme.service';
import { Subscription } from 'rxjs';

declare var Plotly: any;

@Component({
  selector: 'app-plotly-chart',
  templateUrl: './plotly-chart.component.html',
  styleUrls: ['./plotly-chart.component.css']
})
export class PlotlyChartComponent implements OnInit, OnDestroy, AfterViewInit, OnChanges {
  @ViewChild('plotlyContainer', { static: true }) plotlyContainer!: ElementRef;
  
  @Input() data: any[] = [];
  @Input() layout: any = {};
  @Input() config: any = {};
  @Input() htmlContent: string = '';
  @Input() fileName: string = '';
  @Input() width: string = '100%';
  @Input() height: string = '400px';
  
  private themeSubscription: Subscription = new Subscription();
  private isDarkTheme: boolean = false;
  public isInitialized: boolean = false;

  constructor(
    private themeService: ThemeService,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit() {
    // Subscribe to theme changes
    this.themeSubscription = this.themeService.darkMode$.subscribe((isDark: boolean) => {
      this.isDarkTheme = isDark;
      if (this.isInitialized) {
        this.updatePlotlyTheme();
      }
    });
  }

  ngAfterViewInit() {
    console.log('PlotlyChartComponent ngAfterViewInit called');
    console.log('htmlContent length:', this.htmlContent?.length || 0);
    console.log('data length:', this.data?.length || 0);
    console.log('fileName:', this.fileName);
    
    // Only process if we haven't already processed htmlContent in ngOnChanges
    if (this.htmlContent && !this.isInitialized) {
      console.log('Loading from HTML content in ngAfterViewInit');
      this.loadPlotlyFromHTML();
    } else if (this.data.length > 0 && !this.isInitialized) {
      console.log('Loading from data array');
      this.createPlotlyChart();
    } else if (!this.htmlContent && !this.data.length) {
      console.log('No content available - showing error state');
      this.isInitialized = true; // Stop loading spinner
      this.cdr.detectChanges();
    }
  }

  ngOnChanges(changes: SimpleChanges) {
    console.log('PlotlyChartComponent ngOnChanges called:', Object.keys(changes));
    
    // Handle htmlContent changes even if not initialized yet
    if (changes['htmlContent'] && changes['htmlContent'].currentValue) {
      console.log('Received htmlContent, processing immediately');
      // Use setTimeout to ensure the view is ready
      setTimeout(() => {
        this.loadPlotlyFromHTML();
      }, 0);
    }
    
    if (this.isInitialized) {
      if (changes['data'] || changes['layout'] || changes['config']) {
        console.log('Updating chart due to data/layout/config changes');
        this.updateChart();
      }
    } else {
      console.log('Component not initialized yet, but htmlContent was handled above');
    }
  }

  ngOnDestroy() {
    if (this.themeSubscription) {
      this.themeSubscription.unsubscribe();
    }
    this.destroyChart();
  }

  private loadPlotlyFromHTML() {
    if (!this.htmlContent) {
      console.warn('No HTML content provided to plotly chart component');
      return;
    }

    // Check if Plotly is available, if not wait for it
    if (typeof Plotly === 'undefined') {
      console.log('Plotly not available yet, waiting...');
      setTimeout(() => {
        this.loadPlotlyFromHTML();
      }, 100);
      return;
    }

    console.log('Loading plotly from HTML content, length:', this.htmlContent.length);
    console.log('HTML content preview:', this.htmlContent.substring(0, 500));

    try {
      // Create a temporary container to parse the HTML
      const tempDiv = document.createElement('div');
      tempDiv.innerHTML = this.htmlContent;

      // Look for script tags containing Plotly data
      const scripts = tempDiv.querySelectorAll('script');
      console.log('Found', scripts.length, 'script tags in HTML');
      
      let plotlyData: any = null;
      let plotlyLayout: any = null;
      let plotlyConfig: any = null;

      scripts.forEach((script, index) => {
        const content = script.textContent || script.innerHTML;
        console.log(`Script ${index} content preview:`, content.substring(0, 200));
        
        // Extract Plotly.newPlot calls
        const plotlyMatch = content.match(/Plotly\.newPlot\s*\(\s*['"]([^'"]+)['"]\s*,\s*(\[.*?\])\s*,\s*(\{.*?\})\s*(?:,\s*(\{.*?\}))?\s*\)/s);
        if (plotlyMatch) {
          console.log('Found Plotly.newPlot call in script', index);
          try {
            plotlyData = JSON.parse(plotlyMatch[2]);
            plotlyLayout = JSON.parse(plotlyMatch[3]);
            if (plotlyMatch[4]) {
              plotlyConfig = JSON.parse(plotlyMatch[4]);
            }
            console.log('Successfully parsed plotly data:', { data: plotlyData, layout: plotlyLayout, config: plotlyConfig });
          } catch (e) {
            console.warn('Failed to parse Plotly data from HTML:', e);
          }
        }

        // Also look for data/layout/config variables
        if (content.includes('var data =') || content.includes('var layout =')) {
          console.log('Found data/layout variables in script', index);
          try {
            // This is a more complex extraction - we'll use eval in a sandboxed way
            const sandboxedContent = this.extractPlotlyVariables(content);
            if (sandboxedContent.data) plotlyData = sandboxedContent.data;
            if (sandboxedContent.layout) plotlyLayout = sandboxedContent.layout;
            if (sandboxedContent.config) plotlyConfig = sandboxedContent.config;
            console.log('Successfully extracted plotly variables:', sandboxedContent);
          } catch (e) {
            console.warn('Failed to extract Plotly variables:', e);
          }
        }
      });

      // If we found plotly data, create the chart
      if (plotlyData && plotlyLayout) {
        console.log('Creating plotly chart with extracted data');
        this.data = plotlyData;
        this.layout = plotlyLayout;
        this.config = plotlyConfig || {};
        this.createPlotlyChart();
      } else {
        console.log('No plotly data found, using HTML fallback');
        // Fallback: render the HTML directly in an iframe
        this.renderHTMLFallback();
      }
    } catch (error) {
      console.error('Error loading Plotly from HTML:', error);
      this.renderHTMLFallback();
    }
  }

  private extractPlotlyVariables(scriptContent: string): any {
    try {
      // Create a safe evaluation context
      const context = {
        data: null,
        layout: null,
        config: null
      };

      // Remove any dangerous functions and extract only data assignments
      const safeContent = scriptContent
        .replace(/document\.|window\.|eval\(|Function\(/g, '')
        .replace(/var\s+data\s*=\s*(\[.*?\]);/s, 'context.data = $1;')
        .replace(/var\s+layout\s*=\s*(\{.*?\});/s, 'context.layout = $1;')
        .replace(/var\s+config\s*=\s*(\{.*?\});/s, 'context.config = $1;');

      // Use Function constructor for safe evaluation
      const func = new Function('context', safeContent);
      func(context);

      return context;
    } catch (e) {
      console.warn('Failed to extract variables safely:', e);
      return {};
    }
  }

  private renderHTMLFallback() {
    console.log('Rendering HTML fallback for:', this.fileName);
    
    try {
      // Create blob URL for the HTML content
      const blob = new Blob([this.htmlContent], { type: 'text/html' });
      const url = URL.createObjectURL(blob);

      // Create iframe
      const iframe = document.createElement('iframe');
      iframe.src = url;
      iframe.style.width = this.width;
      iframe.style.height = this.height;
      iframe.style.border = 'none';
      iframe.frameBorder = '0';
      iframe.allow = 'fullscreen';

      // Add load event listener to mark as initialized
      iframe.onload = () => {
        console.log('HTML iframe loaded successfully');
        this.isInitialized = true;
        this.cdr.detectChanges();
      };

      iframe.onerror = (error) => {
        console.error('Error loading HTML iframe:', error);
        this.isInitialized = true; // Mark as initialized to stop loading spinner
        this.cdr.detectChanges();
      };

      // Clear container and add iframe
      this.plotlyContainer.nativeElement.innerHTML = '';
      this.plotlyContainer.nativeElement.appendChild(iframe);

      // Clean up blob URL after a delay
      setTimeout(() => URL.revokeObjectURL(url), 5000); // Increased timeout
    } catch (error) {
      console.error('Error creating HTML fallback:', error);
      this.isInitialized = true; // Mark as initialized to stop loading spinner
      this.cdr.detectChanges();
    }
  }

  private createPlotlyChart() {
    if (!this.plotlyContainer?.nativeElement) {
      console.log('Container not ready, retrying...');
      setTimeout(() => {
        this.createPlotlyChart();
      }, 100);
      return;
    }
    
    if (!this.data.length) {
      console.warn('No data available for chart');
      return;
    }

    // Check if Plotly is available
    if (typeof Plotly === 'undefined') {
      console.error('Plotly is not available. Falling back to HTML rendering.');
      this.renderHTMLFallback();
      return;
    }

    try {
      const layout = this.getThemedLayout();
      const config = this.getThemedConfig();

      Plotly.newPlot(
        this.plotlyContainer.nativeElement,
        this.data,
        layout,
        config
      ).then(() => {
        this.isInitialized = true;
        this.cdr.detectChanges();
      }).catch((error: any) => {
        console.error('Error creating Plotly chart:', error);
        this.isInitialized = true;
        this.cdr.detectChanges();
      });
    } catch (error) {
      console.error('Error in createPlotlyChart:', error);
      this.isInitialized = true;
      this.cdr.detectChanges();
    }
  }

  private updateChart() {
    if (!this.isInitialized || !this.plotlyContainer?.nativeElement) return;

    if (typeof Plotly === 'undefined') {
      console.warn('Plotly is not available for chart update');
      return;
    }

    try {
      const layout = this.getThemedLayout();
      const config = this.getThemedConfig();

      Plotly.react(
        this.plotlyContainer.nativeElement,
        this.data,
        layout,
        config
      );
    } catch (error) {
      console.error('Error updating Plotly chart:', error);
    }
  }

  private updatePlotlyTheme() {
    if (!this.isInitialized || !this.plotlyContainer?.nativeElement) return;

    if (typeof Plotly === 'undefined') {
      console.warn('Plotly is not available for theme update');
      return;
    }

    try {
      const layout = this.getThemedLayout();
      Plotly.relayout(this.plotlyContainer.nativeElement, layout);
    } catch (error) {
      console.error('Error updating Plotly theme:', error);
    }
  }

  private getThemedLayout(): any {
    const baseLayout = {
      autosize: true,
      responsive: true,
      ...this.layout
    };

    if (this.isDarkTheme) {
      return {
        ...baseLayout,
        paper_bgcolor: '#1e1e1e',
        plot_bgcolor: '#1e1e1e',
        font: {
          color: '#ffffff',
          ...baseLayout.font
        },
        xaxis: {
          gridcolor: '#444444',
          zerolinecolor: '#666666',
          ...baseLayout.xaxis
        },
        yaxis: {
          gridcolor: '#444444',
          zerolinecolor: '#666666',
          ...baseLayout.yaxis
        }
      };
    } else {
      return {
        ...baseLayout,
        paper_bgcolor: '#ffffff',
        plot_bgcolor: '#ffffff',
        font: {
          color: '#000000',
          ...baseLayout.font
        },
        xaxis: {
          gridcolor: '#e0e0e0',
          zerolinecolor: '#cccccc',
          ...baseLayout.xaxis
        },
        yaxis: {
          gridcolor: '#e0e0e0',
          zerolinecolor: '#cccccc',
          ...baseLayout.yaxis
        }
      };
    }
  }

  private getThemedConfig(): any {
    return {
      displayModeBar: true,
      displaylogo: false,
      modeBarButtonsToAdd: [
        'downloadImage',
        'pan2d',
        'select2d',
        'lasso2d',
        'resetScale2d',
        'autoScale2d',
        'hoverClosestCartesian',
        'hoverCompareCartesian',
        'toggleSpikelines'
      ],
      modeBarButtonsToRemove: [
        'sendDataToCloud',
        'editInChartStudio'
      ],
      responsive: true,
      toImageButtonOptions: {
        format: 'png',
        filename: this.fileName || 'chart',
        height: 800,
        width: 1200,
        scale: 2
      },
      ...this.config
    };
  }

  private destroyChart() {
    if (this.plotlyContainer?.nativeElement && this.isInitialized) {
      if (typeof Plotly === 'undefined') {
        console.warn('Plotly is not available for chart destruction');
        this.isInitialized = false;
        return;
      }

      try {
        Plotly.purge(this.plotlyContainer.nativeElement);
        this.isInitialized = false;
      } catch (error) {
        console.error('Error destroying Plotly chart:', error);
      }
    }
  }

  // Public method to resize chart (can be called from parent component)
  public resizeChart() {
    if (this.isInitialized && this.plotlyContainer?.nativeElement) {
      if (typeof Plotly === 'undefined') {
        console.warn('Plotly is not available for chart resize');
        return;
      }

      try {
        Plotly.Plots.resize(this.plotlyContainer.nativeElement);
      } catch (error) {
        console.error('Error resizing Plotly chart:', error);
      }
    }
  }
} 