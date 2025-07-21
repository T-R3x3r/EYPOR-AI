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

    try {
      // Enhanced extraction with better parsing
      const extractedData = this.extractPlotlyDataFromHTML(this.htmlContent);
      
      if (extractedData.data && extractedData.layout) {
        console.log('Successfully extracted Plotly data from HTML');
        console.log('Data traces:', extractedData.data.length);
        console.log('Sample data:', extractedData.data[0]);
        
        this.data = extractedData.data;
        this.layout = extractedData.layout;
        this.config = extractedData.config || {};
        this.createPlotlyChart();
      } else {
        console.log('Could not extract Plotly data, using HTML fallback');
        this.renderHTMLFallback();
      }
    } catch (error) {
      console.error('Error loading Plotly from HTML:', error);
      this.renderHTMLFallback();
    }
  }

  private extractPlotlyDataFromHTML(htmlContent: string): any {
    try {
      console.log('Extracting Plotly data from HTML...');
      
      // Method 1: Look for Plotly.newPlot direct calls
      const newPlotRegex = /Plotly\.newPlot\s*\(\s*["']([^"']+)["']\s*,\s*(\[[\s\S]*?\])\s*,\s*(\{[\s\S]*?\})\s*(?:,\s*(\{[\s\S]*?\}))?\s*\)/;
      const newPlotMatch = htmlContent.match(newPlotRegex);
      
      if (newPlotMatch) {
        console.log('Found Plotly.newPlot call');
        try {
          const data = this.safeJSONParse(newPlotMatch[2]);
          const layout = this.safeJSONParse(newPlotMatch[3]);
          const config = newPlotMatch[4] ? this.safeJSONParse(newPlotMatch[4]) : {};
          
          if (data && layout) {
            console.log('Successfully parsed from newPlot call');
            return { data, layout, config };
          }
        } catch (e) {
          console.warn('Failed to parse newPlot call:', e);
        }
      }
      
      // Method 2: Look for variable assignments (data, layout, config)
      const dataMatch = htmlContent.match(/(?:var\s+|let\s+|const\s+)?data\s*=\s*(\[[\s\S]*?\]);/);
      const layoutMatch = htmlContent.match(/(?:var\s+|let\s+|const\s+)?layout\s*=\s*(\{[\s\S]*?\});/);
      const configMatch = htmlContent.match(/(?:var\s+|let\s+|const\s+)?config\s*=\s*(\{[\s\S]*?\});/);
      
      if (dataMatch && layoutMatch) {
        console.log('Found variable assignments');
        try {
          const data = this.safeJSONParse(dataMatch[1]);
          const layout = this.safeJSONParse(layoutMatch[1]);
          const config = configMatch ? this.safeJSONParse(configMatch[1]) : {};
          
          if (data && layout) {
            console.log('Successfully parsed from variable assignments');
            return { data, layout, config };
          }
        } catch (e) {
          console.warn('Failed to parse variable assignments:', e);
        }
      }
      
      // Method 3: Extract from script tags and try advanced parsing
      const scriptRegex = /<script[^>]*>([\s\S]*?)<\/script>/gi;
      let scriptMatch;
      
      while ((scriptMatch = scriptRegex.exec(htmlContent)) !== null) {
        const scriptContent = scriptMatch[1];
        
        // Skip empty scripts or scripts that don't contain Plotly
        if (!scriptContent.includes('Plotly') && !scriptContent.includes('data')) {
          continue;
        }
        
        const extracted = this.extractFromScript(scriptContent);
        if (extracted.data && extracted.layout) {
          console.log('Successfully extracted from script tag');
          return extracted;
        }
      }
      
      console.warn('Could not extract Plotly data from any method');
      return { data: null, layout: null, config: null };
      
    } catch (error) {
      console.error('Error in extractPlotlyDataFromHTML:', error);
      return { data: null, layout: null, config: null };
    }
  }
  
  private extractFromScript(scriptContent: string): any {
    try {
      // Clean the script content for better parsing
      let cleanScript = scriptContent
        .replace(/\/\*[\s\S]*?\*\//g, '') // Remove block comments
        .replace(/\/\/.*$/gm, ''); // Remove line comments
      
      // Try to find and extract data/layout/config with improved regex
      const patterns = {
        data: [
          /(?:var\s+|let\s+|const\s+)?data\s*=\s*(\[[\s\S]*?\]);/,
          /["']data["']\s*:\s*(\[[\s\S]*?\])(?:\s*[,}])/,
          /"data":\s*(\[[\s\S]*?\])(?:\s*[,}])/
        ],
        layout: [
          /(?:var\s+|let\s+|const\s+)?layout\s*=\s*(\{[\s\S]*?\});/,
          /["']layout["']\s*:\s*(\{[\s\S]*?\})(?:\s*[,}])/,
          /"layout":\s*(\{[\s\S]*?\})(?:\s*[,}])/
        ],
        config: [
          /(?:var\s+|let\s+|const\s+)?config\s*=\s*(\{[\s\S]*?\});/,
          /["']config["']\s*:\s*(\{[\s\S]*?\})(?:\s*[,}])/,
          /"config":\s*(\{[\s\S]*?\})(?:\s*[,}])/
        ]
      };
      
      const result: any = {};
      
      for (const [key, patternList] of Object.entries(patterns)) {
        for (const pattern of patternList) {
          const match = cleanScript.match(pattern);
          if (match && match[1]) {
            try {
              const parsed = this.safeJSONParse(match[1]);
              if (parsed) {
                result[key] = parsed;
                console.log(`Successfully extracted ${key}`);
                break;
              }
            } catch (e) {
              console.warn(`Failed to parse ${key}:`, e);
            }
          }
        }
      }
      
      return result;
    } catch (error) {
      console.error('Error extracting from script:', error);
      return {};
    }
  }
  
  private safeJSONParse(jsonString: string): any {
    try {
      // Clean the JSON string
      let cleaned = jsonString
        .trim()
        .replace(/,\s*([}\]])/g, '$1') // Remove trailing commas
        .replace(/([{,]\s*)(\w+):/g, '$1"$2":') // Quote unquoted keys
        .replace(/:\s*'([^']*)'/g, ':"$1"') // Convert single quotes to double quotes
        .replace(/:\s*([^",{\[\s][^,}\]]*[^",}\]\s])/g, (match, value) => {
          // Handle unquoted string values
          const trimmed = value.trim();
          if (trimmed === 'true' || trimmed === 'false' || trimmed === 'null' || 
              !isNaN(Number(trimmed)) || trimmed.startsWith('{') || trimmed.startsWith('[')) {
            return ':' + trimmed;
          }
          return ':"' + trimmed + '"';
        });
      
      return JSON.parse(cleaned);
    } catch (error) {
      console.warn('JSON parse failed, attempting alternative parsing:', error);
      
      // Alternative: try eval in a controlled environment (safer approach)
      try {
        return this.evaluateInSafeContext(jsonString);
      } catch (evalError) {
        console.warn('Safe evaluation also failed:', evalError);
        return null;
      }
    }
  }
  
  private evaluateInSafeContext(expression: string): any {
    try {
      // Create a controlled evaluation context
      const context = {
        Array: Array, 
        Object: Object, 
        Number: Number, 
        String: String, 
        Boolean: Boolean, 
        Math: Math, 
        Date: Date,
        undefined: undefined, 
        null: null, 
        true: true, 
        false: false,
        result: null
      };
      
      // Remove potentially dangerous elements
      const safeExpression = expression
        .replace(/window\.|document\.|eval\(|Function\(/g, '')
        .replace(/import\s|require\(|process\.|global\./g, '');
      
      // Wrap in assignment
      const wrappedCode = `context.result = ${safeExpression};`;
      
      // Use Function constructor for controlled evaluation
      const func = new Function('context', wrappedCode);
      func(context);
      
      return context.result;
    } catch (error) {
      console.warn('Safe context evaluation failed:', error);
      return null;
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