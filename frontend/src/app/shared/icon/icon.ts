import { Component, inject, computed, input } from '@angular/core';
import { DomSanitizer } from '@angular/platform-browser';
import { ICONS } from '../../utils/icons';
@Component({
  selector: 'app-icon',
  standalone: true,
  imports: [],
  templateUrl: './icon.html',
  styleUrl: './icon.css',
})
export class Icon {
  name = input('overview');
  private sanitizer = inject(DomSanitizer);
  svg = computed(() =>
    this.sanitizer.bypassSecurityTrustHtml(
      '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">' +
        (ICONS[this.name()] || ICONS['overview']) +
        '</svg>',
    ),
  );
}
