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
import { SelectOption } from '../../models/workspace';
@Component({
  selector: 'app-dropdown',
  standalone: true,
  imports: [Overlay],
  templateUrl: './dropdown.html',
  styleUrl: './dropdown.css',
})
export class Dropdown {
  options = input.required<SelectOption[]>();
  value = input('');
  label = input('Select option');
  disabled = input(false);
  changed = output<string>();
  opened = signal(false);
  active = signal(0);
  upward = signal(false);
  private host = inject<ElementRef<HTMLElement>>(ElementRef);
  selected = computed(
    () => this.options().find((o) => o.value === this.value())?.label || 'Choose an option',
  );
  toggle(): void {
    if (this.disabled()) return;
    this.opened.update((v) => !v);
    if (this.opened()) {
      const r = this.host.nativeElement.getBoundingClientRect();
      this.upward.set(innerHeight - r.bottom < 250 && r.top > 250);
      this.active.set(
        Math.max(
          0,
          this.options().findIndex((o) => o.value === this.value()),
        ),
      );
      setTimeout(() => this.focusOption(), 0);
    }
  }
  choose(option: SelectOption): void {
    if (option.disabled) return;
    this.changed.emit(option.value);
    this.close();
  }
  close(): void {
    this.opened.set(false);
    this.host.nativeElement.querySelector<HTMLButtonElement>('.dropdown-trigger')?.focus();
  }
  focusOption(): void {
    this.host.nativeElement
      .querySelectorAll<HTMLButtonElement>('.dropdown-option')
      [this.active()]?.focus();
  }
  key(e: KeyboardEvent): void {
    if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      this.close();
    } else if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(e.key)) {
      e.preventDefault();
      if (!this.opened()) this.toggle();
      else {
        const size = this.options().length;
        if (!size) return;
        this.active.set(
          e.key === 'Home'
            ? 0
            : e.key === 'End'
              ? size - 1
              : (this.active() + (e.key === 'ArrowDown' ? 1 : -1) + size) % size,
        );
        this.focusOption();
      }
    } else if (e.key === 'Tab') this.opened.set(false);
  }
  @HostListener('document:pointerdown', ['$event'])
  outside(e: PointerEvent): void {
    if (!this.host.nativeElement.contains(e.target as Node)) this.opened.set(false);
  }
}
