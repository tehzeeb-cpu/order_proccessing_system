import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { ApiService } from '../../services/api.service';
import { DashboardStats } from '../../models/order.model';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, RouterModule],
  template: `
    <div class="container">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem;">
        <div>
          <h1 style="font-size: 1.75rem; font-weight: 700; color: #0f172a; margin: 0;">Saga Control Dashboard</h1>
          <p style="color: #64748b; margin-top: 0.25rem;">Real-time metrics, concurrent order ingestion, and status monitoring.</p>
        </div>
        <div style="display: flex; gap: 0.75rem;">
          <button class="btn btn-outline" (click)="resetDemo()">
            <span class="material-icons" style="font-size: 18px;">restart_alt</span> Reset Demo State
          </button>
          <button class="btn btn-outline" (click)="loadStats()">
            <span class="material-icons" style="font-size: 18px;">refresh</span> Refresh Metrics
          </button>
        </div>
      </div>

      <!-- Stats Grid -->
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1.25rem; margin-bottom: 2rem;">
        <div class="card" style="margin: 0; border-top: 4px solid #6366f1;">
          <span style="font-size: 0.75rem; font-weight: 700; color: #64748b; text-transform: uppercase;">Total Orders</span>
          <div style="font-size: 2rem; font-weight: 800; color: #1e293b; margin-top: 0.25rem;">{{ stats?.total_orders || 0 }}</div>
        </div>
        <div class="card" style="margin: 0; border-top: 4px solid #10b981;">
          <span style="font-size: 0.75rem; font-weight: 700; color: #64748b; text-transform: uppercase;">Placed</span>
          <div style="font-size: 2rem; font-weight: 800; color: #047857; margin-top: 0.25rem;">{{ stats?.placed_count || 0 }}</div>
        </div>
        <div class="card" style="margin: 0; border-top: 4px solid #06b6d4;">
          <span style="font-size: 0.75rem; font-weight: 700; color: #64748b; text-transform: uppercase;">Shipped</span>
          <div style="font-size: 2rem; font-weight: 800; color: #0891b2; margin-top: 0.25rem;">{{ stats?.shipped_count || 0 }}</div>
        </div>
        <div class="card" style="margin: 0; border-top: 4px solid #ef4444;">
          <span style="font-size: 0.75rem; font-weight: 700; color: #64748b; text-transform: uppercase;">Cancelled</span>
          <div style="font-size: 2rem; font-weight: 800; color: #b91c1c; margin-top: 0.25rem;">{{ stats?.cancelled_count || 0 }}</div>
        </div>
        <div class="card" style="margin: 0; border-top: 4px solid #f59e0b; background: #fffbeb;">
          <span style="font-size: 0.75rem; font-weight: 700; color: #b45309; text-transform: uppercase;">Needs Attention</span>
          <div style="font-size: 2rem; font-weight: 800; color: #b45309; margin-top: 0.25rem;">{{ stats?.needs_attention_count || 0 }}</div>
        </div>
        <div class="card" style="margin: 0; border-top: 4px solid #6366f1;">
          <span style="font-size: 0.75rem; font-weight: 700; color: #64748b; text-transform: uppercase;">In Progress</span>
          <div style="font-size: 2rem; font-weight: 800; color: #4338ca; margin-top: 0.25rem;">{{ stats?.in_progress_count || 0 }}</div>
        </div>
      </div>

      <!-- File Ingest Card -->
      <div class="card">
        <div class="card-header">
          <div class="card-title" style="display: flex; align-items: center; gap: 0.5rem;">
            <span class="material-icons" style="color: #4f46e5;">upload_file</span>
            Stream Ingest Orders CSV
          </div>
        </div>
        <p style="font-size: 0.875rem; color: #64748b; margin-top: 0;">
          Upload <code>orders_bulk.csv</code> to trigger high-concurrency Saga Orchestration (2,500+ records processed in parallel via asyncio stream).
        </p>

        <div style="display: flex; gap: 1rem; align-items: center; background: #f8fafc; padding: 1.5rem; border-radius: 8px; border: 2px dashed #cbd5e1;">
          <input type="file" #fileInput (change)="onFileSelected($event)" accept=".csv" style="font-size: 0.875rem;" />
          <button class="btn btn-primary" [disabled]="!selectedFile || isUploading" (click)="uploadCsv()">
            <span class="material-icons" style="font-size: 18px;">cloud_upload</span>
            {{ isUploading ? 'Streaming Orders...' : 'Process Bulk CSV' }}
          </button>
        </div>

        <div *ngIf="uploadMessage" style="margin-top: 1rem; padding: 0.875rem; border-radius: 6px; font-weight: 600;"
             [style.background]="isError ? '#fee2e2' : '#d1fae5'"
             [style.color]="isError ? '#b91c1c' : '#047857'">
          {{ uploadMessage }}
        </div>
      </div>
    </div>
  `
})
export class DashboardComponent implements OnInit {
  stats: DashboardStats | null = null;
  selectedFile: File | null = null;
  isUploading = false;
  uploadMessage = '';
  isError = false;

  constructor(private apiService: ApiService) {}

  ngOnInit(): void {
    this.loadStats();
  }

  loadStats(): void {
    this.apiService.getDashboardStats().subscribe({
      next: (data: DashboardStats) => this.stats = data,
      error: (err: any) => console.error('Failed to load stats', err)
    });
  }

  onFileSelected(event: any): void {
    const file: File = event.target.files[0];
    if (file) {
      this.selectedFile = file;
    }
  }

  resetDemo(): void {
    if (confirm('Are you sure you want to reset the demo state? This clears all orders and re-seeds stock to 50,000 per SKU.')) {
      this.apiService.resetDemo().subscribe({
        next: (res: any) => {
          alert(res.message);
          this.loadStats();
        },
        error: (err: any) => alert(err.error?.detail || 'Failed to reset demo state.')
      });
    }
  }

  uploadCsv(): void {
    if (!this.selectedFile) return;
    this.isUploading = true;
    this.uploadMessage = '';

    this.apiService.uploadBulkCsv(this.selectedFile).subscribe({
      next: (res: any) => {
        this.isUploading = false;
        this.isError = false;
        this.uploadMessage = res.message || 'CSV streaming started successfully!';
        this.loadStats();
      },
      error: (err: any) => {
        this.isUploading = false;
        this.isError = true;
        this.uploadMessage = err.error?.detail || 'Failed to upload CSV file.';
      }
    });
  }
}
