import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Auth } from '../../services/auth';
@Component({selector:'app-auth', imports:[FormsModule,RouterLink], templateUrl:'./auth.html',styleUrl:'./auth.css'})
export class AuthPage {
  private route = inject(ActivatedRoute);
  auth = inject(Auth);
  mode = this.route.snapshot.routeConfig?.path || 'login';
  name = ''; email = ''; password = '';
  busy = signal(false); message = signal(''); error = signal(''); verified = signal(false);
  async submit(): Promise<void> {
    if(this.busy()) return;
    this.busy.set(true); this.error.set(''); this.message.set('');
    try {
      if(this.mode==='signup') this.message.set((await this.auth.signup(this.name.trim(),this.email.trim(),this.password)).message);
      else if(this.mode==='verify-email') {
        const token = this.route.snapshot.queryParamMap.get('token') || '';
        if(!token) throw new Error('Verification link is missing. Request a new email below.');
        this.message.set((await this.auth.verify(token)).message); this.verified.set(true);
      } else await this.auth.login(this.email.trim(),this.password);
    } catch(e) { this.error.set((e as Error).message); }
    finally { this.busy.set(false); }
  }
  async resend(): Promise<void> {
    if(this.busy() || !this.email.trim()) return;
    this.busy.set(true); this.error.set('');
    try { this.message.set((await this.auth.resend(this.email.trim())).message); }
    catch(e) { this.error.set((e as Error).message); }
    finally { this.busy.set(false); }
  }
}
