import { Overlay } from '../../utils/overlay';
import {
  Component,
  inject,
  signal,
  computed,
  input,
  output,
  ElementRef,
  HostListener,
} from '@angular/core';
import { Icon } from '../icon/icon';
import { today, dateLabel } from '../../utils/date';
@Component({
  selector: 'app-date-picker',
  standalone: true,
  imports: [Icon, Overlay],
  templateUrl: './date-picker.html',
  styleUrl: './date-picker.css',
})
export class DatePicker {
  value = input('');
  min = input('');
  label = input('Date');
  changed = output<string>();
  open = signal(false);
  year = signal(new Date().getFullYear());
  month = signal(new Date().getMonth());
  private host = inject<ElementRef<HTMLElement>>(ElementRef);
  dateLabel = dateLabel;
  today = today();
  weekdays = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'];
  title = computed(() =>
    new Date(this.year(), this.month(), 1).toLocaleDateString('en', {
      month: 'long',
      year: 'numeric',
    }),
  );
  days = computed(() => {
    const offset = (new Date(this.year(), this.month(), 1).getDay() + 6) % 7;
    return [
      ...Array.from({ length: offset }, () => null),
      ...Array.from({ length: new Date(this.year(), this.month() + 1, 0).getDate() }, (_, i) => {
        const date = `${this.year()}-${String(this.month() + 1).padStart(2, '0')}-${String(i + 1).padStart(2, '0')}`;
        return {
          day: i + 1,
          value: date,
          label: new Date(date + 'T12:00:00').toLocaleDateString('en', {
            day: 'numeric',
            month: 'long',
            year: 'numeric',
          }),
        };
      }),
    ];
  });
  toggle(): void {
    if (!this.open()) {
      const d = new Date((this.value() || this.today) + 'T12:00:00');
      this.year.set(d.getFullYear());
      this.month.set(d.getMonth());
    }
    this.open.update((v) => !v);
    if (this.open())
      setTimeout(
        () =>
          this.host.nativeElement
            .querySelector<HTMLButtonElement>(
              '.calendar-day.selected:not(:disabled),.calendar-day.today:not(:disabled),.calendar-day:not(:disabled)',
            )
            ?.focus(),
        0,
      );
  }
  move(n: number): void {
    const d = new Date(this.year(), this.month() + n, 1);
    this.year.set(d.getFullYear());
    this.month.set(d.getMonth());
  }
  select(value: string): void {
    if (this.min() && value < this.min()) return;
    this.changed.emit(value);
    this.close();
  }
  close(): void {
    this.open.set(false);
    this.host.nativeElement.querySelector<HTMLButtonElement>('.date-trigger')?.focus();
  }
  key(e: KeyboardEvent): void {
    if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      this.close();
      return;
    }
    const element = e.target as HTMLElement;
    const value = element.dataset['date'];
    if (
      value &&
      ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End'].includes(e.key)
    ) {
      e.preventDefault();
      const date = new Date(value + 'T12:00:00'),
        delta: Record<string, number> = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 };
      if (e.key === 'Home') date.setDate(1);
      else if (e.key === 'End') date.setMonth(date.getMonth() + 1, 0);
      else date.setDate(date.getDate() + delta[e.key]);
      this.year.set(date.getFullYear());
      this.month.set(date.getMonth());
      const next = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
      setTimeout(
        () =>
          this.host.nativeElement
            .querySelector<HTMLButtonElement>(`[data-date="${next}"]:not(:disabled)`)
            ?.focus(),
        0,
      );
    }
  }
  @HostListener('document:pointerdown', ['$event'])
  outside(e: PointerEvent): void {
    if (!this.host.nativeElement.contains(e.target as Node)) this.open.set(false);
  }
}
