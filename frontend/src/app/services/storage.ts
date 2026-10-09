import { Injectable, signal } from '@angular/core';
@Injectable({ providedIn: 'root' })
export class Storage {
  available = signal(true);
  read<T>(key: string, fallback: T): T {
    try {
      const raw = localStorage.getItem(key);
      return raw ? (JSON.parse(raw) as T) : fallback;
    } catch {
      this.available.set(false);
      return fallback;
    }
  }
  write(key: string, value: unknown): void {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      this.available.set(false);
    }
  }
}
