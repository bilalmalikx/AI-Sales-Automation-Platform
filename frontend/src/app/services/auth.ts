import { Injectable, inject, signal } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { Api } from './api';
export interface Account { email: string; name: string; role: string; }
@Injectable({providedIn:'root'})
export class Auth {
  private api = inject(Api);
  private router = inject(Router);
  user = signal<Account | null>(null);
  async restore(): Promise<boolean> {
    try { this.user.set(await this.api.get<Account>('auth/me')); return true; }
    catch { this.user.set(null); return false; }
  }
  async login(email: string, password: string): Promise<void> {
    this.user.set(await this.api.post<Account>('auth/login',{email,password}));
    await this.router.navigateByUrl('/overview');
  }
  async logout(): Promise<void> {
    await this.api.post('auth/logout'); this.user.set(null);
    await this.router.navigateByUrl('/login');
  }
  signup(name:string,email:string,password:string) { return this.api.post<{message:string}>('auth/signup',{name,email,password}); }
  resend(email:string) { return this.api.post<{message:string}>('auth/resend-verification',{email}); }
  verify(token:string) { return this.api.post<{message:string}>('auth/verify-email',{token}); }
  invite(email:string) { return this.api.post<{message:string}>('auth/invitations',{email}); }
}
export const authGuard: CanActivateFn = async () => {
  const auth = inject(Auth); const router = inject(Router);
  return await auth.restore() || router.createUrlTree(['/login']);
};
