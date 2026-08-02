import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterModule } from '@angular/router';
import { ApiService } from '../../services/api.service';
import { OrderDetail } from '../../models/order.model';

@Component({
  selector: 'app-order-details',
  standalone: true,
  imports: [CommonModule, RouterModule],
  template: `
    <div class="container" *ngIf="order">
      <!-- Top Navigation -->
      <div style="margin-bottom: 1rem;">
        <a routerLink="/orders" class="btn btn-outline" style="padding: 0.35rem 0.75rem;">
          <span class="material-icons" style="font-size: 18px;">arrow_back</span> Back to Orders
        </a>
      </div>

      <!-- Header Card -->
      <div class="card">
        <div class="card-header">
          <div>
            <span style="font-size: 0.875rem; font-weight: 700; color: #64748b; text-transform: uppercase;">Order Execution Record</span>
            <h1 style="font-size: 1.75rem; font-weight: 800; color: #0f172a; margin: 0.25rem 0 0 0;">{{ order.order_id }}</h1>
          </div>
          <div>
            <span [class]="'badge badge-' + order.status" style="font-size: 1rem; padding: 0.5rem 1rem;">{{ order.status }}</span>
          </div>
        </div>

        <!-- Metadata Summary -->
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 1.5rem; background: #f8fafc; padding: 1.25rem; border-radius: 8px;">
          <div>
            <span style="font-size: 0.75rem; color: #64748b; font-weight: 600; text-transform: uppercase;">SKU</span>
            <div style="font-weight: 700; font-size: 1.1rem; color: #1e293b; margin-top: 0.25rem;">{{ order.sku }}</div>
          </div>
          <div>
            <span style="font-size: 0.75rem; color: #64748b; font-weight: 600; text-transform: uppercase;">Quantity</span>
            <div style="font-weight: 700; font-size: 1.1rem; color: #1e293b; margin-top: 0.25rem;">{{ order.qty }}</div>
          </div>
          <div>
            <span style="font-size: 0.75rem; color: #64748b; font-weight: 600; text-transform: uppercase;">Amount</span>
            <div style="font-weight: 700; font-size: 1.1rem; color: #1e293b; margin-top: 0.25rem;">\${{ order.amount.toFixed(2) }}</div>
          </div>
          <div>
            <span style="font-size: 0.75rem; color: #64748b; font-weight: 600; text-transform: uppercase;">Simulated Failure</span>
            <div style="font-weight: 600; font-size: 0.875rem; color: #ef4444; margin-top: 0.25rem;">
              {{ order.fail_at || 'None' }}
            </div>
          </div>
          <div>
            <span style="font-size: 0.75rem; color: #64748b; font-weight: 600; text-transform: uppercase;">Simulated Comp Failure</span>
            <div style="font-weight: 600; font-size: 0.875rem; color: #f59e0b; margin-top: 0.25rem;">
              {{ order.comp_fail_at || 'None' }}
            </div>
          </div>
        </div>
      </div>

      <!-- Saga Step Execution Timeline -->
      <div class="card">
        <div class="card-title" style="margin-bottom: 1rem; display: flex; align-items: center; gap: 0.5rem;">
          <span class="material-icons" style="color: #4f46e5;">account_tree</span> Parallel Step Execution Timeline
        </div>

        <div class="table-container">
          <table class="data-table">
            <thead>
              <tr>
                <th>Step Name</th>
                <th>Target Service</th>
                <th>Status</th>
                <th>Latency (ms)</th>
                <th>Error Traceback / Details</th>
                <th>Updated At</th>
              </tr>
            </thead>
            <tbody>
              <tr *ngFor="let step of order.steps">
                <td style="font-weight: 700;">{{ step.step_name }}</td>
                <td style="font-size: 0.8125rem; color: #64748b;">
                  <code *ngIf="step.step_name === 'ORDER'">Order Service (8001)</code>
                  <code *ngIf="step.step_name === 'INVENTORY'">Inventory Service (8002)</code>
                  <code *ngIf="step.step_name === 'PAYMENT'">Payment Service (8003)</code>
                  <code *ngIf="step.step_name === 'SHIPPING'">Shipping Service (8004)</code>
                </td>
                <td>
                  <span [class]="'badge badge-' + step.status">{{ step.status }}</span>
                </td>
                <td>
                  <span *ngIf="step.execution_time_ms">{{ step.execution_time_ms }} ms</span>
                  <span *ngIf="!step.execution_time_ms">—</span>
                </td>
                <td style="font-size: 0.8125rem; color: #ef4444;">
                  {{ step.error_message || 'OK' }}
                </td>
                <td style="font-size: 0.8125rem; color: #64748b;">{{ step.updated_at | date:'mediumTime' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Order Audit Log -->
      <div class="card">
        <div class="card-title" style="margin-bottom: 1rem; display: flex; align-items: center; gap: 0.5rem;">
          <span class="material-icons" style="color: #4f46e5;">receipt_long</span> Order Audit Log History
        </div>

        <div style="display: flex; flex-direction: column; gap: 0.75rem;">
          <div *ngFor="let log of order.logs" style="padding: 0.875rem; background: #f8fafc; border-radius: 8px; border-left: 4px solid #cbd5e1;"
               [style.border-left-color]="log.level === 'ERROR' ? '#ef4444' : (log.level === 'WARN' ? '#f59e0b' : '#10b981')">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <span style="font-weight: 700; font-size: 0.875rem; color: #1e293b;">{{ log.event_type }}</span>
              <span style="font-size: 0.75rem; color: #64748b;">{{ log.created_at | date:'medium' }}</span>
            </div>
            <p style="margin: 0.25rem 0 0 0; font-size: 0.875rem; color: #475569;">{{ log.message }}</p>
          </div>
        </div>
      </div>
    </div>
  `
})
export class OrderDetailsComponent implements OnInit {
  order: OrderDetail | null = null;

  constructor(
    private route: ActivatedRoute,
    private apiService: ApiService
  ) {}

  ngOnInit(): void {
    const orderId = this.route.snapshot.paramMap.get('id');
    if (orderId) {
      this.apiService.getOrderDetails(orderId).subscribe({
        next: (data: OrderDetail) => this.order = data,
        error: (err: any) => console.error('Failed to fetch order details', err)
      });
    }
  }
}
