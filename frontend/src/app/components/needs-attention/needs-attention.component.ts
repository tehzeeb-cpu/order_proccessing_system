import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { ApiService } from '../../services/api.service';
import { OrderItem } from '../../models/order.model';

@Component({
  selector: 'app-needs-attention',
  standalone: true,
  imports: [CommonModule, RouterModule],
  template: `
    <div class="container">
      <div class="card" style="border-left: 6px solid #f59e0b; background: #fffbeb;">
        <div class="card-header">
          <div>
            <h1 style="font-size: 1.5rem; font-weight: 800; color: #b45309; margin: 0; display: flex; align-items: center; gap: 0.5rem;">
              <span class="material-icons">warning</span> Operational Exception Queue (Needs Attention)
            </h1>
            <p style="color: #92400e; font-size: 0.875rem; margin: 0.25rem 0 0 0;">
              Orders listed below encountered a compensation failure during rollback (e.g., simulated release stock failure). Operators can inspect details or manually trigger an undo retry.
            </p>
          </div>
          <button class="btn btn-outline" (click)="loadOrders()">
            <span class="material-icons" style="font-size: 18px;">refresh</span> Refresh Queue
          </button>
        </div>
      </div>

      <div class="card">
        <div class="table-container">
          <table class="data-table">
            <thead>
              <tr>
                <th>Order ID</th>
                <th>SKU</th>
                <th>Qty</th>
                <th>Amount</th>
                <th>Simulated Failure</th>
                <th>Simulated Comp Failure</th>
                <th>Created At</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              <tr *ngFor="let order of orders">
                <td style="font-weight: 700;">
                  <a [routerLink]="['/orders', order.order_id]" style="color: #4f46e5;">{{ order.order_id }}</a>
                </td>
                <td><code>{{ order.sku }}</code></td>
                <td>{{ order.qty }}</td>
                <td>\${{ order.amount.toFixed(2) }}</td>
                <td style="color: #ef4444; font-size: 0.8125rem;">{{ order.fail_at || '—' }}</td>
                <td style="color: #f59e0b; font-size: 0.8125rem; font-weight: 600;">{{ order.comp_fail_at || '—' }}</td>
                <td style="font-size: 0.8125rem; color: #64748b;">{{ order.created_at | date:'short' }}</td>
                <td>
                  <button class="btn btn-danger" (click)="retryUndo(order.order_id)" style="padding: 0.35rem 0.75rem; font-size: 0.8125rem;">
                    <span class="material-icons" style="font-size: 16px;">replay</span> Retry Undo
                  </button>
                </td>
              </tr>
              <tr *ngIf="orders.length === 0">
                <td colspan="8" style="text-align: center; color: #047857; padding: 2.5rem; background: #ecfdf5; font-weight: 600;">
                  🎉 All operational queues are clear! No orders require manual attention.
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `
})
export class NeedsAttentionComponent implements OnInit {
  orders: OrderItem[] = [];

  constructor(private apiService: ApiService) {}

  ngOnInit(): void {
    this.loadOrders();
  }

  loadOrders(): void {
    this.apiService.getOrders(1, 100, 'NEEDS_ATTENTION').subscribe({
      next: (res: any) => this.orders = res.items,
      error: (err: any) => console.error('Failed to load needs attention orders', err)
    });
  }

  retryUndo(orderId: string): void {
    this.apiService.retryUndo(orderId).subscribe({
      next: (res: any) => {
        alert(res.message);
        this.loadOrders();
      },
      error: (err: any) => alert(err.error?.detail || 'Failed to retry undo.')
    });
  }
}
