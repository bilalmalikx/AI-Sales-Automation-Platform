import { Component, inject, input } from '@angular/core';
import { Lead } from '../../models/workspace';
import { Person } from '../person/person';
import { Badge } from '../badge/badge';
import { Dialog } from '../../services/dialog';
@Component({
  selector: 'app-lead-table',
  standalone: true,
  imports: [Person, Badge],
  templateUrl: './lead-table.html',
  styleUrl: './lead-table.css',
})
export class LeadTable {
  leads = input.required<Lead[]>();
  dialog = inject(Dialog);
}
