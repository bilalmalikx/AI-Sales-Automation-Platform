import { Component, input } from '@angular/core';
import { Metric } from '../../models/workspace';
import { Icon } from '../icon/icon';
import { Tilt } from '../../utils/tilt';
@Component({
  selector: 'app-metric-grid',
  standalone: true,
  imports: [Icon, Tilt],
  templateUrl: './metric-grid.html',
  styleUrl: './metric-grid.css',
})
export class MetricGrid {
  items = input.required<Metric[]>();
}
