import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { ApiService } from '../../services/api.service';
import { LogEntry } from '../../models/order.model';

@Component({
  selector: 'app-logs',
  standalone: true,
  imports: [CommonModule, RouterModule],
  template: `
    <div class="container">
      <div class="card">
        <div class="card-header">
          <div>
            <h1 style="font-size: 1.5rem; font-weight: 800; color: #0f172a; margin: 0;">Distributed Audit Log Stream</h1>
            <p style="color: #64748b; font-size: 0.875rem; margin: 0.25rem 0 0 0;">Real-time audit log event history across Saga state transitions.</p>
          </div>
          <button class="btn btn-outline" (click)="loadLogs()">
            <span class="material-icons" style="font-size: 18px;">refresh</span> Refresh Logs
          </button>
        </div>

        <div style="display: flex; flex-direction: column; gap: 0.5rem;">
          <div *ngFor="let log of logs" style="padding: 0.875rem; background: #f8fafc; border-radius: 8px; border-left: 4px solid #cbd5e1; font-family: monospace;"
               [style.border-left-color]="log.level === 'ERROR' ? '#ef4444' : (log.level === 'WARN' ? '#f59e0b' : '#10b981')">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.25rem;">
              <span style="font-weight: 700; color: #1e293b; font-size: 0.8125rem;">
                [{{ log.level }}] {{ log.event_type }}
                <a [routerLink]="['/orders', log.order_id]" style="color: #4f46e5; margin-left: 0.5rem;">
                  ({{ log.order_id }})
                </a>
              </span>
              <span style="font-size: 0.75rem; color: #64748b;">{{ log.created_at | date:'medium' }}</span>
            </div>
            <div style="font-size: 0.875rem; color: #334155;">{{ log.message }}</div>
          </div>
        </div>
      </div>
    </div>
  `
})
export class LogsComponent implements OnInit {
  logs: LogEntry[] = [];

  constructor(private apiService: ApiService) {}

  ngOnInit(): void {
    this.loadLogs();
  }

  loadLogs(): void {
    this.apiService.getLogs(1, 50).subscribe({
      next: (data: LogEntry[]) => this.logs = data,
      error: (err: any) => console.error('Failed to load logs', err)
    });
  }
}
