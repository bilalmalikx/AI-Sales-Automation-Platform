import { Component, input } from '@angular/core';
@Component({
  selector: 'app-page-header',
  standalone: true,
  imports: [],
  templateUrl: './page-header.html',
  styleUrl: './page-header.css',
})
export class PageHeader {
  title = input.required<string>();
  description = input('');
  eyebrow = input('YOUR WORKSPACE');
}
