import { Component, inject, computed } from '@angular/core';
import { Notification } from '../../services/notification';
@Component({
  selector: 'app-toast',
  standalone: true,
  imports: [],
  templateUrl: './toast.html',
  styleUrl: './toast.css',
})
export class Toast {
  notify = inject(Notification);
  warning = computed(() =>
    /unavailable|first|stopped|limit|choose|already|overlap/i.test(this.notify.message()),
  );
}
