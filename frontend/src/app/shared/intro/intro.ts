import { Component, inject, signal, DestroyRef } from '@angular/core';
@Component({
  selector: 'app-intro',
  standalone: true,
  imports: [],
  templateUrl: './intro.html',
  styleUrl: './intro.css',
})
export class Intro {
  visible = signal(true);
  fading = signal(false);
  constructor() {
    const fade = setTimeout(() => this.fading.set(true), 3000);
    const remove = setTimeout(() => this.visible.set(false), 3700);
    inject(DestroyRef).onDestroy(() => {
      clearTimeout(fade);
      clearTimeout(remove);
    });
  }
}
