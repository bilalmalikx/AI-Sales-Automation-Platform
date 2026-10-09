import { Injectable, signal } from '@angular/core';
@Injectable({ providedIn: 'root' })
export class Dialog {
  readonly current = signal<{
    kind: string;
    id?: string;
    lead?: string;
  } | null>(null);
  open(kind: string, id?: string, lead?: string): void {
    this.current.set({ kind, id, lead });
  }
  close(): void {
    this.current.set(null);
  }
}
