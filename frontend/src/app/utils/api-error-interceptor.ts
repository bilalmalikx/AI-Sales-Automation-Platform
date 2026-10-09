import { HttpInterceptorFn, HttpErrorResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError } from 'rxjs';
import { Notification } from '../services/notification';
export const apiErrorInterceptor: HttpInterceptorFn = (request, next) => {
  const notify = inject(Notification);
  return next(request).pipe(
    catchError((error: HttpErrorResponse) => {
      notify.show(
        error.status === 0
          ? 'Unable to reach the server. Please try again.'
          : 'The request could not be completed. Please try again.',
      );
      return throwError(() => error);
    }),
  );
};
