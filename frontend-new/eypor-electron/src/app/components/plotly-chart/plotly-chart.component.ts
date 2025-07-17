import { Component, Input, OnInit, OnDestroy, ViewChild, ElementRef, AfterViewInit, OnChanges, SimpleChanges, ChangeDetectorRef } from '@angular/core';
import { Subscription } from 'rxjs';
import { ThemeService } from '../../services/theme.service';
import { PlotlySharedService } from '../../services/plotly-shared.service';

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
    private cdr: ChangeDetectorRef,
    private plotlyService: PlotlySharedService
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
    if (!this.plotlyService.isReady()) {
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
      console.error('Error in extractFromScript:', error);
      return {};
    }
  }

  private safeJSONParse(jsonString: string): any {
    try {
      // Clean the string for better parsing
      let cleanString = jsonString
        .replace(/,\s*}/g, '}') // Remove trailing commas in objects
        .replace(/,\s*]/g, ']') // Remove trailing commas in arrays
        .replace(/,\s*$/g, ''); // Remove trailing commas at end
      
      return JSON.parse(cleanString);
    } catch (error) {
      console.warn('Failed to parse JSON:', error);
      console.log('Problematic string:', jsonString);
      return null;
    }
  }

  private evaluateInSafeContext(expression: string): any {
    try {
      // Create a safe context for evaluation
      const safeContext = {
        data: null,
        layout: null,
        config: null,
        Plotly: this.plotlyService.isReady() ? this.plotlyService.getPlotly() : null
      };
      
      // Use Function constructor for safer evaluation
      const safeEval = new Function('data', 'layout', 'config', 'Plotly', expression);
      return safeEval.call(safeContext, safeContext.data, safeContext.layout, safeContext.config, safeContext.Plotly);
    } catch (error) {
      console.warn('Failed to evaluate expression:', error);
      return null;
    }
  }

  private renderHTMLFallback() {
    console.log('Rendering HTML fallback');
    
    if (this.plotlyContainer && this.htmlContent) {
      // Create a temporary div to parse the HTML
      const tempDiv = document.createElement('div');
      tempDiv.innerHTML = this.htmlContent;
      
      // Find the plotly div in the HTML
      const plotlyDiv = tempDiv.querySelector('.plotly, [id*="plotly"], div[style*="plotly"]');
      
      if (plotlyDiv) {
        // Copy the plotly div content to our container
        this.plotlyContainer.nativeElement.innerHTML = plotlyDiv.outerHTML;
        
        // Try to reinitialize plotly if needed
        if (this.plotlyService.isReady()) {
          const plotlyElements = this.plotlyContainer.nativeElement.querySelectorAll('.plotly');
          plotlyElements.forEach((element: any) => {
            if (element.data && element.layout) {
              this.plotlyService.newPlot(element, element.data, element.layout, element.config);
            }
          });
        }
      } else {
        // If no plotly div found, just render the HTML content
        this.plotlyContainer.nativeElement.innerHTML = this.htmlContent;
      }
      
      this.isInitialized = true;
      this.cdr.detectChanges();
    }
  }

  private createPlotlyChart() {
    if (!this.plotlyContainer || !this.data || this.data.length === 0) {
      console.warn('Cannot create plotly chart: missing container or data');
      return;
    }

    if (!this.plotlyService.isReady()) {
      console.warn('Plotly library not loaded');
      return;
    }

    try {
      console.log('Creating Plotly chart with data:', this.data);
      console.log('Layout:', this.layout);
      console.log('Config:', this.config);

      const themedLayout = this.getThemedLayout();
      const themedConfig = this.getThemedConfig();

      this.plotlyService.newPlot(
        this.plotlyContainer.nativeElement,
        this.data,
        themedLayout,
        themedConfig
      ).then(() => {
        console.log('Plotly chart created successfully');
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
    if (!this.plotlyContainer || !this.data || this.data.length === 0) {
      return;
    }

    if (!this.plotlyService.isReady()) {
      return;
    }

    try {
      const themedLayout = this.getThemedLayout();
      this.plotlyService.react(
        this.plotlyContainer.nativeElement,
        this.data,
        themedLayout,
        this.config
      );
    } catch (error) {
      console.error('Error updating Plotly chart:', error);
    }
  }

  private updatePlotlyTheme() {
    if (this.isInitialized && this.data && this.data.length > 0) {
      this.updateChart();
    }
  }

  private getThemedLayout(): any {
    const baseLayout = {
      ...this.layout,
      autosize: true,
      margin: {
        l: 50,
        r: 50,
        t: 50,
        b: 50,
        pad: 4
      }
    };

    if (this.isDarkTheme) {
      return {
        ...baseLayout,
        paper_bgcolor: '#1e1e1e',
        plot_bgcolor: '#1e1e1e',
        font: {
          color: '#ffffff'
        },
        xaxis: {
          ...baseLayout.xaxis,
          gridcolor: '#444444',
          zerolinecolor: '#444444'
        },
        yaxis: {
          ...baseLayout.yaxis,
          gridcolor: '#444444',
          zerolinecolor: '#444444'
        }
      };
    }

    return baseLayout;
  }

  private getThemedConfig(): any {
    const baseConfig = {
      ...this.config,
      responsive: true,
      displayModeBar: true,
      displaylogo: false,
      modeBarButtonsToRemove: ['pan2d', 'lasso2d', 'select2d'],
      toImageButtonOptions: {
        format: 'png',
        filename: this.fileName || 'chart',
        height: 600,
        width: 800,
        scale: 2
      }
    };

    if (this.isDarkTheme) {
      return {
        ...baseConfig,
        modeBarButtonsToAdd: [{
          name: 'Toggle Theme',
          icon: 'camera',
          click: () => {
            this.isDarkTheme = !this.isDarkTheme;
            this.updatePlotlyTheme();
          }
        }]
      };
    }

    return baseConfig;
  }

  private destroyChart() {
    if (this.plotlyContainer && this.plotlyService.isReady()) {
      try {
        this.plotlyService.purge(this.plotlyContainer.nativeElement);
      } catch (error) {
        console.warn('Error destroying Plotly chart:', error);
      }
    }
  }

  public resizeChart() {
    if (this.plotlyContainer && this.plotlyService.isReady()) {
      try {
        this.plotlyService.resize(this.plotlyContainer.nativeElement);
      } catch (error) {
        console.warn('Error resizing Plotly chart:', error);
      }
    }
  }
} 