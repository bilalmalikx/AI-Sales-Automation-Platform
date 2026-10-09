import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { environment } from '../../environments/environment';
import { firstValueFrom } from 'rxjs';
import { Page } from '../models/backend';
@Injectable({ providedIn: 'root' })
export class Api {
  private http = inject(HttpClient);
  readonly baseUrl = environment.apiBaseUrl;
  async request<T>(
    method: string,
    path: string,
    body?: unknown,
    headers?: Record<string, string>,
  ): Promise<T> {
    try {
      return await firstValueFrom(
        this.http.request<T>(method, this.url(path), { body, headers, withCredentials: true }),
      );
    } catch (error) {
      if (error instanceof HttpErrorResponse)
        throw new Error(
          error.error?.error?.message ||
            (error.status === 0
              ? 'Backend is unavailable. Check the API connection.'
              : `Request failed (${error.status}).`),
        );
      throw error;
    }
  }
  get<T>(path: string): Promise<T> {
    return this.request<T>('GET', path);
  }
  post<T>(path: string, body?: unknown, headers?: Record<string, string>): Promise<T> {
    return this.request<T>('POST', path, body, headers);
  }
  put<T>(path: string, body: unknown): Promise<T> {
    return this.request<T>('PUT', path, body);
  }
  patch<T>(path: string, body: unknown): Promise<T> {
    return this.request<T>('PATCH', path, body);
  }
  delete<T>(path: string): Promise<T> {
    return this.request<T>('DELETE', path);
  }
  async all<T>(path: string): Promise<T[]> {
    const rows: T[] = [];
    let page = 1;
    while (true) {
      const data = await this.get<Page<T>>(
        `${path}${path.includes('?') ? '&' : '?'}page=${page}&page_size=100`,
      );
      rows.push(...data.items);
      if (page >= data.pages) break;
      page++;
    }
    return rows;
  }
  private url(path: string): string {
    return this.baseUrl.replace(/\/$/, '') + '/' + path.replace(/^\//, '');
  }
}
