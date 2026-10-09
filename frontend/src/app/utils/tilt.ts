import { Directive, ElementRef, HostListener, inject } from '@angular/core';
@Directive({ selector: '[appTilt]', standalone: true })
export class Tilt {
  private element = inject<ElementRef<HTMLElement>>(ElementRef);
  @HostListener('pointermove', ['$event'])
  move(event: PointerEvent): void {
    if (
      !matchMedia('(hover:hover) and (pointer:fine)').matches ||
      matchMedia('(prefers-reduced-motion:reduce)').matches
    )
      return;
    const r = this.element.nativeElement.getBoundingClientRect();
    this.element.nativeElement.style.transform = `perspective(1000px) rotateX(${-((event.clientY - r.top) / r.height - 0.5) * 9}deg) rotateY(${((event.clientX - r.left) / r.width - 0.5) * 9}deg)`;
  }
  @HostListener('pointerleave')
  reset(): void {
    this.element.nativeElement.style.transform = '';
  }
}
