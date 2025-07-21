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
        console.log('Could not extract Plotly data from HTML, trying iframe fallback');
        this.renderHtmlFallback();
      }
    } catch (error) {
      console.error('Error processing HTML content:', error);
      this.renderHtmlFallback();
    }
  }
  
  private renderHtmlFallback() {
    try {
      console.log('Rendering HTML fallback for complex chart');
      
      // Create a blob URL for the HTML content
      const blob = new Blob([this.htmlContent], { type: 'text/html' });
      const url = URL.createObjectURL(blob);
      
      // Create iframe element
      const iframe = document.createElement('iframe');
      iframe.src = url;
      iframe.style.width = '100%';
      iframe.style.height = '100%';
      iframe.style.border = 'none';
      iframe.frameBorder = '0';
      iframe.allow = 'fullscreen';
      
      // Add load event listener
      iframe.onload = () => {
        console.log('HTML iframe loaded successfully');
        this.isInitialized = true;
        this.isLoading = false;
        this.error = '';
        this.cdr.detectChanges();
      };
      
      iframe.onerror = (error) => {
        console.error('Error loading HTML iframe:', error);
        this.error = 'Failed to load chart content';
        this.isLoading = false;
        this.cdr.detectChanges();
      };
      
      // Clear container and add iframe
      const container = document.querySelector('.plotly-chart-container');
      if (container) {
        container.innerHTML = '';
        container.appendChild(iframe);
      }
      
      // Clean up blob URL after a delay
      setTimeout(() => URL.revokeObjectURL(url), 10000);
      
    } catch (error) {
      console.error('Error creating HTML fallback:', error);
      this.error = 'Could not display chart content';
      this.isLoading = false;
      this.cdr.detectChanges();
    }
  }

  private extractPlotlyDataFromHTML(htmlContent: string): any {
    try {
      console.log('Extracting Plotly data from HTML...');
      
      // Method 1: Enhanced Plotly.newPlot extraction with better regex
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
      
      // Method 2: Enhanced script tag extraction for complex structures
      const scriptRegex = /<script[^>]*>([\s\S]*?)<\/script>/gi;
      let scriptMatch;
      
      while ((scriptMatch = scriptRegex.exec(htmlContent)) !== null) {
        const scriptContent = scriptMatch[1];
        
        // Skip scripts that don't contain Plotly data
        if (!scriptContent.includes('Plotly') && !scriptContent.includes('data') && !scriptContent.includes('layout')) {
          continue;
        }
        
        console.log('Processing script tag with Plotly content');
        const extracted = this.extractFromComplexScript(scriptContent);
        if (extracted.data && extracted.layout) {
          console.log('Successfully extracted from complex script tag');
          return extracted;
        }
      }
      
      // Method 3: Fallback to simple variable assignments
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
      
      // Method 4: Last resort - try to extract from the specific structure in your HTML
      console.log('Trying last resort extraction method...');
      const lastResort = this.extractFromLastResort(htmlContent);
      if (lastResort.data && lastResort.layout) {
        console.log('Successfully extracted using last resort method');
        return lastResort;
      }
      
      console.warn('Could not extract Plotly data from any method');
      return { data: null, layout: null, config: null };
      
    } catch (error) {
      console.error('Error in extractPlotlyDataFromHTML:', error);
      return { data: null, layout: null, config: null };
    }
  }
  
  private extractFromComplexScript(scriptContent: string): any {
    try {
      console.log('Extracting from complex script content...');
      
      // Clean the script content
      let cleanScript = scriptContent
        .replace(/\/\*[\s\S]*?\*\//g, '') // Remove block comments
        .replace(/\/\/.*$/gm, ''); // Remove line comments
      
      // Method 1: Try to find the exact Plotly.newPlot call structure
      const newPlotPattern = /Plotly\.newPlot\s*\(\s*["']([^"']+)["']\s*,\s*(\[[\s\S]*?\])\s*,\s*(\{[\s\S]*?\})\s*(?:,\s*(\{[\s\S]*?\}))?\s*\)/;
      const newPlotMatch = cleanScript.match(newPlotPattern);
      
      if (newPlotMatch) {
        console.log('Found Plotly.newPlot call in complex script');
        try {
          const data = this.safeJSONParse(newPlotMatch[2]);
          const layout = this.safeJSONParse(newPlotMatch[3]);
          const config = newPlotMatch[4] ? this.safeJSONParse(newPlotMatch[4]) : {};
          
          if (data && layout) {
            console.log('Successfully parsed from newPlot call in complex script');
            return { data, layout, config };
          }
        } catch (e) {
          console.warn('Failed to parse newPlot call in complex script:', e);
        }
      }
      
      // Method 2: Look for data and layout arrays/objects in the script
      // This handles cases where the data is embedded in the script but not in a newPlot call
      const dataPatterns = [
        /(\[[\s\S]*?\])\s*,\s*\{[\s\S]*?"type":\s*"bar"[\s\S]*?\}/, // Array with bar type
        /(\[[\s\S]*?\])\s*,\s*\{[\s\S]*?"type":\s*"scatter"[\s\S]*?\}/, // Array with scatter type
        /(\[[\s\S]*?\])\s*,\s*\{[\s\S]*?"type":\s*"line"[\s\S]*?\}/, // Array with line type
        /(\[[\s\S]*?\])\s*,\s*\{[\s\S]*?"marker"[\s\S]*?\}/, // Array with marker
        /(\[[\s\S]*?\])\s*,\s*\{[\s\S]*?"x":\s*\[[\s\S]*?\]/ // Array with x values
      ];
      
      const layoutPatterns = [
        /(\{[\s\S]*?"title"[\s\S]*?\})\s*,\s*\{[\s\S]*?"responsive"[\s\S]*?\}/, // Layout with title and responsive
        /(\{[\s\S]*?"xaxis"[\s\S]*?"yaxis"[\s\S]*?\})/, // Layout with axes
        /(\{[\s\S]*?"template"[\s\S]*?\})/, // Layout with template
        /(\{[\s\S]*?"margin"[\s\S]*?\})/, // Layout with margin
        /(\{[\s\S]*?"barmode"[\s\S]*?\})/ // Layout with barmode
      ];
      
      // Try to find data and layout using these patterns
      for (const dataPattern of dataPatterns) {
        const dataMatch = cleanScript.match(dataPattern);
        if (dataMatch) {
          try {
            const data = this.safeJSONParse(dataMatch[1]);
            if (data && Array.isArray(data) && data.length > 0) {
              console.log('Found data array in complex script');
              
              // Now look for layout
              for (const layoutPattern of layoutPatterns) {
                const layoutMatch = cleanScript.match(layoutPattern);
                if (layoutMatch) {
                  try {
                    const layout = this.safeJSONParse(layoutMatch[1]);
                    if (layout && typeof layout === 'object') {
                      console.log('Found layout object in complex script');
                      return { data, layout, config: {} };
                    }
                  } catch (e) {
                    console.warn('Failed to parse layout:', e);
                  }
                }
              }
            }
          } catch (e) {
            console.warn('Failed to parse data:', e);
          }
        }
      }
      
      // Method 3: Fallback to the original simple patterns
      return this.extractFromScript(scriptContent);
      
    } catch (error) {
      console.error('Error in extractFromComplexScript:', error);
      return {};
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
  
  private extractFromLastResort(htmlContent: string): any {
    try {
      console.log('Attempting last resort extraction...');
      
      // Look for the specific structure in your HTML file
      // The data is in the form: [{"customdata":[...], "hovertemplate":..., "marker":..., "name":..., "x":[...], "y":[...], "type":"bar"}, ...]
      
      // Find the data array that contains the actual chart data
      const dataArrayPattern = /\[\s*\{[\s\S]*?"type":\s*"bar"[\s\S]*?\}\s*(?:,\s*\{[\s\S]*?"type":\s*"bar"[\s\S]*?\}\s*)*\]/;
      const dataMatch = htmlContent.match(dataArrayPattern);
      
      if (dataMatch) {
        console.log('Found data array in last resort method');
        try {
          const data = this.safeJSONParse(dataMatch[0]);
          if (data && Array.isArray(data) && data.length > 0) {
            console.log('Successfully parsed data array');
            
            // Now look for the layout object
            // The layout contains: {"template":{...}, "margin":{...}, "barmode":"group", "title":{...}, "xaxis":{...}, "yaxis":{...}, ...}
            const layoutPattern = /\{\s*"template":\s*\{[\s\S]*?\}\s*,\s*"margin":\s*\{[\s\S]*?\}\s*,\s*"barmode":\s*"group"[\s\S]*?\}/;
            const layoutMatch = htmlContent.match(layoutPattern);
            
            if (layoutMatch) {
              try {
                const layout = this.safeJSONParse(layoutMatch[0]);
                if (layout && typeof layout === 'object') {
                  console.log('Successfully parsed layout object');
                  return { data, layout, config: { responsive: true } };
                }
              } catch (e) {
                console.warn('Failed to parse layout in last resort:', e);
              }
            }
            
            // If layout parsing fails, try a simpler layout pattern
            const simpleLayoutPattern = /\{\s*"title":\s*\{[\s\S]*?\}\s*,\s*"xaxis":\s*\{[\s\S]*?\}\s*,\s*"yaxis":\s*\{[\s\S]*?\}[\s\S]*?\}/;
            const simpleLayoutMatch = htmlContent.match(simpleLayoutPattern);
            
            if (simpleLayoutMatch) {
              try {
                const layout = this.safeJSONParse(simpleLayoutMatch[0]);
                if (layout && typeof layout === 'object') {
                  console.log('Successfully parsed simple layout object');
                  return { data, layout, config: { responsive: true } };
                }
              } catch (e) {
                console.warn('Failed to parse simple layout in last resort:', e);
              }
            }
          }
        } catch (e) {
          console.warn('Failed to parse data in last resort:', e);
        }
      }
      
      return { data: null, layout: null, config: null };
      
    } catch (error) {
      console.error('Error in extractFromLastResort:', error);
      return { data: null, layout: null, config: null };
    }
  }
} 