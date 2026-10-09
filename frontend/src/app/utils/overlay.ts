import { afterNextRender, Directive, DestroyRef, ElementRef, inject, input } from '@angular/core';
/** Keep menus in the browser top layer so dialogs and scrolling cards cannot clip them. */
@Directive({ selector: '[appOverlay]', standalone: true })
export class Overlay {
  appOverlay = input.required<HTMLElement>();
  overlayWidth = input(0);
  private element = inject<ElementRef<HTMLElement>>(ElementRef).nativeElement;
  constructor() {
    const position = () => {
      const anchor = this.appOverlay().getBoundingClientRect();
      const width = Math.min(this.overlayWidth() || anchor.width, innerWidth - 32);
      const height = this.element.getBoundingClientRect().height;
      const below = innerHeight - anchor.bottom - 16;
      const top =
        below >= height || anchor.top < height + 16
          ? Math.min(anchor.bottom + 8, Math.max(16, innerHeight - height - 16))
          : anchor.top - height - 8;
      Object.assign(this.element.style, {
        position: 'fixed',
        margin: '0',
        inset: 'auto',
        width: `${width}px`,
        maxWidth: 'none',
        left: `${Math.max(16, Math.min(anchor.left, innerWidth - width - 16))}px`,
        top: `${Math.max(16, top)}px`,
      });
    };
    afterNextRender(() => {
      this.element.showPopover();
      position();
    });
    const scroll = (event: Event) => {
      if (!this.element.contains(event.target as Node)) position();
    };
    window.addEventListener('resize', position);
    document.addEventListener('scroll', scroll, true);
    inject(DestroyRef).onDestroy(() => {
      window.removeEventListener('resize', position);
      document.removeEventListener('scroll', scroll, true);
    });
  }
}
