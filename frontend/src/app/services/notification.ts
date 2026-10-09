import { Injectable, inject, signal, DestroyRef } from '@angular/core';
@Injectable({ providedIn: 'root' })
export class Notification {
  message = signal('');
  private timer: ReturnType<typeof setTimeout> | undefined;
  constructor() {
    inject(DestroyRef).onDestroy(() => clearTimeout(this.timer));
  }
  show(message: string): void {
    this.message.set(message);
    clearTimeout(this.timer);
    this.timer = setTimeout(() => this.dismiss(), 4000);
  }
  dismiss(): void {
    this.message.set('');
  }
}
