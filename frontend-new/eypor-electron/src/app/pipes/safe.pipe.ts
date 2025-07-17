import { Pipe, PipeTransform } from '@angular/core';
import { DomSanitizer, SafeHtml, SafeResourceUrl } from '@angular/platform-browser';

@Pipe({
  name: 'safe'
})
export class SafePipe implements PipeTransform {

  constructor(private sanitizer: DomSanitizer) {}

  transform(value: string, type: 'html' | 'url' = 'html'): SafeHtml | SafeResourceUrl {
    if (type === 'url') {
      return this.sanitizer.bypassSecurityTrustResourceUrl(value);
    } else {
      return this.sanitizer.bypassSecurityTrustHtml(value);
    }
  }
} 