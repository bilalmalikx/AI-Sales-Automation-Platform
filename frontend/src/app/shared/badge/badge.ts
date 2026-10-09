import { Component, computed, input } from '@angular/core';
@Component({
  selector: 'app-badge',
  standalone: true,
  imports: [],
  templateUrl: './badge.html',
  styleUrl: './badge.css',
})
export class Badge {
  text = input('');
  warning = computed(() => ['New', 'Draft', 'Needs review'].includes(this.text()));
}
