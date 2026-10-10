import { Component, inject, computed, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { PageHeader } from '../../shared/page-header/page-header';
import { Badge } from '../../shared/badge/badge';
import { Dropdown } from '../../shared/dropdown/dropdown';
import { Discovery as DiscoveryService } from '../../services/discovery';
import { DiscoveryInput, Prospect } from '../../models/backend';
import { label } from '../../services/workspace';
@Component({
  selector: 'app-discovery',
  imports: [FormsModule, RouterLink, PageHeader, Badge, Dropdown],
  templateUrl: './discovery.html',
  styleUrl: './discovery.css',
})
export class Discovery {
  discovery = inject(DiscoveryService);
  label = label;
  countries = [
    { value: 'GB', label: 'United Kingdom' },
    { value: 'US', label: 'United States' },
  ];
  runOptions = computed(() => [
    { value: 'all', label: 'All businesses · all runs' },
    ...this.discovery
      .runs()
      .map((r) => ({
        value: r.id,
        label: r.parameters.industry + ' · ' + r.parameters.location + ' · ' + label(r.status),
      })),
  ]);
  changeCountry(value: string): void {
    if (value === 'GB' || value === 'US') this.form.country = value;
  }
  websiteLabel(value: string): string {
    try {
      const u = new URL(value);
      return u.hostname + (u.pathname === '/' ? '' : u.pathname);
    } catch {
      return value;
    }
  }

  form: DiscoveryInput = {
    industry: 'car wash',
    location: 'London',
    country: 'GB',
    limit: 50,
    mode: 'fresh',
    generate_drafts: true,
  };
  run = computed(() => this.discovery.runs().find((r) => r.id === this.discovery.selected()));
  active = computed(
    () =>
      !!this.run() &&
      !['completed', 'completed_with_errors', 'failed', 'cancelled'].includes(this.run()!.status),
  );
  contactsOnly = signal(false);
  contactCount = computed(
    () =>
      this.discovery
        .prospects()
        .filter((p) => p.contact_available && !['excluded', 'cancelled'].includes(p.status)).length,
  );
  emailCount = computed(
    () =>
      this.discovery
        .prospects()
        .filter(
          (p) =>
            p.contact_available && p.emails.length && !['excluded', 'cancelled'].includes(p.status),
        ).length,
  );
  crmCount = computed(() => this.discovery.prospects().filter((p) => !!p.lead_id).length);
  visibleProspects = computed(() =>
    this.discovery
      .prospects()
      .filter(
        (p) =>
          !this.contactsOnly() ||
          (p.contact_available && !['excluded', 'cancelled'].includes(p.status)),
      ),
  );
  selected = signal<Prospect | null>(null);
  selectedProspect = computed(() => {
    const selection = this.selected();
    return this.discovery.prospects().find((p) => p.id === selection?.id) || selection;
  });
  stages = [
    'Maps discovery',
    'Website inspection',
    'App verification',
    'Qualification',
    'Contact validation',
    'Review draft',
  ];
  async start(): Promise<void> {
    this.selected.set(null);
    await this.discovery.start({ ...this.form, limit: Number(this.form.limit) });
  }
  safeUrl(value: string | null): string | null {
    if (!value) return null;
    try {
      const u = new URL(value);
      return ['http:', 'https:'].includes(u.protocol) ? u.href : null;
    } catch {
      return null;
    }
  }
  websitePhones(p: Prospect): { phone: string; source_url: string }[] {
    const site = p.evidence['website'] as
      | { phones?: { phone: string; source_url: string }[] }
      | undefined;
    return site?.phones || [];
  }
  contactLinks(p: Prospect): string[] {
    const site = p.evidence['website'] as { contact_links?: string[] } | undefined;
    return (site?.contact_links || []).filter((url) => !!this.safeUrl(url));
  }
  evidenceText(p: Prospect): string {
    return JSON.stringify(p.evidence, null, 2);
  }
}
