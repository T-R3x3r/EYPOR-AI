import { Component, Input, OnInit, OnDestroy, OnChanges, SimpleChanges, ChangeDetectorRef } from '@angular/core';
import { Subscription } from 'rxjs';
import { ThemeService } from '../../services/theme.service';

@Component({
  selector: 'app-plotly-chart',
  templateUrl: './plotly-chart.component.html',
  styleUrls: ['./plotly-chart.component.css']
})
export class PlotlyChartComponent implements OnInit, OnDestroy, OnChanges {
  @Input() htmlContent: string = '';
  @Input() fileName: string = '';
  @Input() width: string = '100%';
  @Input() height: string = '400px';
  
  // Plotly data properties
  public data: any[] = [];
  public layout: any = {};
  public config: any = {};
  public revision: number = 0;
  
  private themeSubscription: Subscription = new Subscription();
  private isDarkTheme: boolean = false;
  public isInitialized: boolean = false;
  public isLoading: boolean = true;
  public error: string = '';

  constructor(
    private themeService: ThemeService,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit() {
    // Subscribe to theme changes
    this.themeSubscription = this.themeService.darkMode$.subscribe((isDark: boolean) => {
      this.isDarkTheme = isDark;
      if (this.isInitialized) {
        this.updateTheme();
      }
    });
  }

  ngOnChanges(changes: SimpleChanges) {
    if (changes['htmlContent'] && changes['htmlContent'].currentValue) {
      this.processHtmlContent();
    }
  }

  ngOnDestroy() {
    if (this.themeSubscription) {
      this.themeSubscription.unsubscribe();
    }
  }

  private processHtmlContent() {
    if (!this.htmlContent) {
      this.error = 'No HTML content provided';
      this.isLoading = false;
      this.cdr.detectChanges();
      return;
    }

    try {
      console.log('Processing HTML content for Plotly chart');
      const extractedData = this.extractPlotlyDataFromHTML(this.htmlContent);
      
      if (extractedData.data && extractedData.layout) {
        console.log('Successfully extracted Plotly data');
        this.data = extractedData.data;
        this.layout = this.applyTheme(extractedData.layout);
        this.config = extractedData.config || this.getDefaultConfig();
        this.isInitialized = true;
        this.isLoading = false;
        this.error = '';
        this.revision++; // Trigger re-render
        this.cdr.detectChanges();
      } else {
        console.log('Could not extract Plotly data from HTML');
        this.error = 'Could not extract chart data from HTML content';
        this.isLoading = false;
        this.cdr.detectChanges();
      }
    } catch (error) {
      console.error('Error processing HTML content:', error);
      this.error = 'Error processing chart data';
      this.isLoading = false;
      this.cdr.detectChanges();
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
      
      // Method 3: Extract from script tags
      const scriptRegex = /<script[^>]*>([\s\S]*?)<\/script>/gi;
      let scriptMatch;
      
      while ((scriptMatch = scriptRegex.exec(htmlContent)) !== null) {
        const scriptContent = scriptMatch[1];
        
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
      let cleanScript = scriptContent
        .replace(/\/\*[\s\S]*?\*\//g, '')
        .replace(/\/\/.*$/gm, '');
      
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
      let cleanString = jsonString
        .replace(/,\s*}/g, '}')
        .replace(/,\s*]/g, ']')
        .replace(/,\s*$/g, '');
      
      return JSON.parse(cleanString);
    } catch (error) {
      console.warn('Failed to parse JSON:', error);
      return null;
    }
  }

  private applyTheme(layout: any): any {
    const baseLayout = {
      ...layout,
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

  private getDefaultConfig(): any {
    return {
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
  }

  private updateTheme() {
    if (this.isInitialized && this.data && this.data.length > 0) {
      this.layout = this.applyTheme(this.layout);
      this.revision++; // Trigger re-render
      this.cdr.detectChanges();
    }
  }

  public onPlotlyClick(event: any) {
    console.log('Plotly click event:', event);
  }

  public onPlotlyHover(event: any) {
    console.log('Plotly hover event:', event);
  }

  public onPlotlyRelayout(event: any) {
    console.log('Plotly relayout event:', event);
  }
} 