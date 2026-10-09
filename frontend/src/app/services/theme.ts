import { Injectable, inject, signal, DestroyRef } from '@angular/core';
import { Storage } from './storage';
@Injectable({ providedIn: 'root' })
export class Theme {
  private storage = inject(Storage);
  private media = matchMedia('(prefers-color-scheme:dark)');
  readonly preference = signal('porcelain');
  constructor() {
    const value = this.storage.read<string>('salesway-angular-theme', 'porcelain');
    this.set(['porcelain', 'midnight', 'system'].includes(value) ? value : 'porcelain');
    const listener = () => {
      if (this.preference() === 'system') this.apply();
    };
    this.media.addEventListener('change', listener);
    inject(DestroyRef).onDestroy(() => this.media.removeEventListener('change', listener));
  }
  set(theme: string): void {
    this.preference.set(theme);
    this.storage.write('salesway-angular-theme', theme);
    this.apply();
  }
  private apply(): void {
    const theme =
      this.preference() === 'system'
        ? this.media.matches
          ? 'midnight'
          : 'porcelain'
        : this.preference();
    document.documentElement.dataset['theme'] = theme;
    document
      .querySelector('meta[name="theme-color"]')
      ?.setAttribute('content', theme === 'midnight' ? '#111522' : '#f3f4f8');
  }
}
