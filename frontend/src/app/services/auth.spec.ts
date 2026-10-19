import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter, Router } from '@angular/router';
import { describe,it,expect,beforeEach,afterEach,vi } from 'vitest';
import { Auth } from './auth';

describe('Verified account sessions',()=>{
 let auth:Auth; let http:HttpTestingController;
 beforeEach(()=>{
  TestBed.configureTestingModule({providers:[provideHttpClient(),provideHttpClientTesting(),provideRouter([])]});
  auth=TestBed.inject(Auth);http=TestBed.inject(HttpTestingController);
 });
 afterEach(()=>http.verify());
 it('restores a server session with credentials rather than a local-storage token',async()=>{
  const pending=auth.restore();const req=http.expectOne(r=>r.url.endsWith('/auth/me'));
  expect(req.request.withCredentials).toBe(true);
  req.flush({email:'owner@example.com',name:'Owner',role:'owner'});
  expect(await pending).toBe(true);expect(auth.user()?.role).toBe('owner');
 });
 it('clears identity when the session is missing',async()=>{
  auth.user.set({email:'owner@example.com',name:'Owner',role:'owner'});
  const pending=auth.restore();http.expectOne(r=>r.url.endsWith('/auth/me')).flush({error:{message:'Please log in'}},{status:401,statusText:'Unauthorized'});
  expect(await pending).toBe(false);expect(auth.user()).toBeNull();
 });
 it('revokes the server session before logout navigation',async()=>{
  const navigate=vi.spyOn(TestBed.inject(Router),'navigateByUrl').mockResolvedValue(true);
  auth.user.set({email:'owner@example.com',name:'Owner',role:'owner'});
  const pending=auth.logout();const req=http.expectOne(r=>r.url.endsWith('/auth/logout'));
  expect(req.request.method).toBe('POST');req.flush({message:'Logged out'});
  await pending;expect(auth.user()).toBeNull();expect(navigate).toHaveBeenCalledWith('/login');
 });
});
