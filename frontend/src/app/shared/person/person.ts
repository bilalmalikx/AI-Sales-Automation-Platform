import { Component, computed, input } from '@angular/core';
import { Lead } from '../../models/workspace';
@Component({
  selector: 'app-person',
  standalone: true,
  imports: [],
  templateUrl: './person.html',
  styleUrl: './person.css',
})
export class Person {
  lead = input.required<Lead>();
  initials = computed(() =>
    this.lead()
      .name.split(' ')
      .map((x) => x[0])
      .slice(0, 2)
      .join(''),
  );
}
