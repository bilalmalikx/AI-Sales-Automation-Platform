import {
  Component,
  inject,
  signal,
  effect,
  ElementRef,
  DestroyRef,
  viewChild,
  HostListener,
} from '@angular/core';
import { RouterOutlet, RouterLink, RouterLinkActive, Router, NavigationEnd } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { filter } from 'rxjs';
import { Icon } from '../../shared/icon/icon';
import { Intro } from '../../shared/intro/intro';
import { Toast } from '../../shared/toast/toast';
import { WorkspaceDialog } from '../workspace-dialog/workspace-dialog';
import { Theme } from '../../services/theme';
import { Dialog } from '../../services/dialog';
import { Workspace } from '../../services/workspace';
import { Storage } from '../../services/storage';
import { NAVIGATION } from '../../models/workspace';
@Component({
  selector: 'app-app-shell',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, Icon, WorkspaceDialog, Toast, Intro],
  templateUrl: './app-shell.html',
  styleUrl: './app-shell.css',
})
export class AppShell {
  theme = inject(Theme);
  dialog = inject(Dialog);
  store = inject(Workspace);
  private storage = inject(Storage);
  private router = inject(Router);
  navigation = NAVIGATION;
  collapsed = signal(this.storage.read('salesway-angular-collapsed', false));
  mobile = signal(innerWidth <= 900);
  drawerOpen = signal(false);
  scrolled = signal(false);
  pageTitle = signal('Overview');
  sidebar = viewChild<ElementRef<HTMLElement>>('sidebar');
  main = viewChild<ElementRef<HTMLElement>>('main');
  private focusTimer: ReturnType<typeof setTimeout> | undefined;
  constructor() {
    history.scrollRestoration = 'manual';
    effect(() => {
      document.body.classList.toggle('collapsed', this.collapsed());
      document.body.style.overflow = this.drawerOpen() ? 'hidden' : '';
    });
    this.router.events
      .pipe(
        filter((e) => e instanceof NavigationEnd),
        takeUntilDestroyed(),
      )
      .subscribe((e) => {
        const path = (e as NavigationEnd).urlAfterRedirects.split('?')[0].slice(1);
        const title = this.navigation.find((p) => p.id === path)?.label || 'Overview';
        this.pageTitle.set(title);
        document.title = title + ' · Salesway';
        this.drawer(false);
        scrollTo(0, 0);
        this.main()?.nativeElement.focus({ preventScroll: true });
      });
    inject(DestroyRef).onDestroy(() => {
      clearTimeout(this.focusTimer);
      document.body.classList.remove('collapsed');
      document.body.style.overflow = '';
    });
  }
  toggleCollapse(): void {
    this.collapsed.update((v) => !v);
    this.storage.write('salesway-angular-collapsed', this.collapsed());
  }
  drawer(open: boolean): void {
    this.drawerOpen.set(open);
    clearTimeout(this.focusTimer);
    if (open)
      this.focusTimer = setTimeout(
        () =>
          this.sidebar()?.nativeElement.querySelector<HTMLButtonElement>('#close-menu')?.focus(),
        260,
      );
    else if (this.mobile()) document.querySelector<HTMLButtonElement>('#menu')?.focus();
  }
  @HostListener('window:resize')
  resize(): void {
    this.mobile.set(innerWidth <= 900);
    if (!this.mobile()) this.drawer(false);
  }
  @HostListener('window:scroll')
  scroll(): void {
    this.scrolled.set(scrollY > 10);
  }
  @HostListener('document:keydown', ['$event'])
  key(event: KeyboardEvent): void {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      if (!this.dialog.current()) this.dialog.open('search');
    }
    if (!this.drawerOpen()) return;
    if (event.key === 'Escape') {
      this.drawer(false);
      return;
    }
    if (event.key === 'Tab') {
      const nodes = [
        ...(this.sidebar()?.nativeElement.querySelectorAll<HTMLElement>('a,button') || []),
      ].filter((el) => el.offsetParent !== null);
      const first = nodes[0],
        last = nodes.at(-1);
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    }
  }
}
