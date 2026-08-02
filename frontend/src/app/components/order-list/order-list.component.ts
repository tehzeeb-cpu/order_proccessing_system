import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { ApiService } from '../../services/api.service';
import { OrderItem } from '../../models/order.model';

@Component({
  selector: 'app-order-list',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  template: `
    <div class="container">
      <div class="card">
        <div class="card-header" style="flex-wrap: wrap; gap: 1rem;">
          <div>
            <h2 class="card-title" style="margin: 0;">Order Stream Explorer</h2>
            <p style="color: #64748b; font-size: 0.875rem; margin: 0.25rem 0 0 0;">View, filter, and inspect Saga workflow execution status across orders.</p>
          </div>

          <!-- Controls -->
          <div style="display: flex; gap: 0.75rem; align-items: center;">
            <input type="text" [(ngModel)]="searchQuery" (keyup.enter)="loadOrders(1)" placeholder="Search Order ID..."
                   style="padding: 0.5rem 0.875rem; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 0.875rem; width: 200px;" />

            <select [(ngModel)]="statusFilter" (change)="loadOrders(1)"
                    style="padding: 0.5rem 0.875rem; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 0.875rem; background: white;">
              <option value="ALL">All Statuses</option>
              <option value="PLACED">Placed</option>
              <option value="SHIPPED">Shipped</option>
              <option value="CANCELLED">Cancelled</option>
              <option value="NEEDS_ATTENTION">Needs Attention</option>
              <option value="IN_PROGRESS">In Progress</option>
            </select>

            <button class="btn btn-primary" (click)="loadOrders(1)">
              <span class="material-icons" style="font-size: 18px;">search</span> Filter
            </button>
          </div>
        </div>

        <!-- Table -->
        <div class="table-container">
          <table class="data-table">
            <thead>
              <tr>
                <th>Order ID</th>
                <th>SKU</th>
                <th>Qty</th>
                <th>Amount</th>
                <th>Status</th>
                <th>Failure Markers</th>
                <th>Created At</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr *ngFor="let order of orders">
                <td style="font-weight: 700; color: #1e293b;">
                  <a [routerLink]="['/orders', order.order_id]" style="color: #4f46e5; text-decoration: none;">
                    {{ order.order_id }}
                  </a>
                </td>
                <td><code>{{ order.sku }}</code></td>
                <td>{{ order.qty }}</td>
                <td style="font-weight: 600;">\${{ order.amount.toFixed(2) }}</td>
                <td>
                  <span [class]="'badge badge-' + order.status">{{ order.status }}</span>
                </td>
                <td style="font-size: 0.75rem; color: #64748b;">
                  <span *ngIf="order.fail_at" style="color: #ef4444; display: block;">Fail: {{ order.fail_at }}</span>
                  <span *ngIf="order.comp_fail_at" style="color: #f59e0b; display: block;">CompFail: {{ order.comp_fail_at }}</span>
                  <span *ngIf="!order.fail_at && !order.comp_fail_at">—</span>
                </td>
                <td style="font-size: 0.8125rem; color: #64748b;">{{ order.created_at | date:'short' }}</td>
                <td>
                  <div style="display: flex; gap: 0.5rem;">
                    <a [routerLink]="['/orders', order.order_id]" class="btn btn-outline" style="padding: 0.25rem 0.5rem; font-size: 0.75rem;">
                      Details
                    </a>
                    <button *ngIf="order.status === 'PLACED'" class="btn btn-primary" (click)="markShipped(order.order_id)" style="padding: 0.25rem 0.5rem; font-size: 0.75rem;">
                      Ship
                    </button>
                    <button *ngIf="order.status === 'NEEDS_ATTENTION'" class="btn btn-danger" (click)="retryUndo(order.order_id)" style="padding: 0.25rem 0.5rem; font-size: 0.75rem;">
                      Retry Undo
                    </button>
                  </div>
                </td>
              </tr>
              <tr *ngIf="orders.length === 0">
                <td colspan="8" style="text-align: center; color: #64748b; padding: 2rem;">
                  No orders found matching the filter criteria.
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Pagination -->
        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 1.25rem;">
          <span style="font-size: 0.875rem; color: #64748b;">
            Showing page {{ currentPage }} of {{ totalPages }} ({{ totalOrders }} total orders)
          </span>
          <div style="display: flex; gap: 0.5rem;">
            <button class="btn btn-outline" [disabled]="currentPage <= 1" (click)="loadOrders(currentPage - 1)">
              Previous
            </button>
            <button class="btn btn-outline" [disabled]="currentPage >= totalPages" (click)="loadOrders(currentPage + 1)">
              Next
            </button>
          </div>
        </div>
      </div>
    </div>
  `
})
export class OrderListComponent implements OnInit {
  orders: OrderItem[] = [];
  currentPage = 1;
  pageSize = 20;
  totalOrders = 0;
  totalPages = 1;
  statusFilter = 'ALL';
  searchQuery = '';

  constructor(private apiService: ApiService) {}

  ngOnInit(): void {
    this.loadOrders(1);
  }

  loadOrders(page: number): void {
    this.currentPage = page;
    this.apiService.getOrders(this.currentPage, this.pageSize, this.statusFilter, this.searchQuery).subscribe({
      next: (res: any) => {
        this.orders = res.items;
        this.totalOrders = res.total;
        this.totalPages = res.total_pages;
      },
      error: (err: any) => console.error('Failed to fetch orders', err)
    });
  }

  markShipped(orderId: string): void {
    this.apiService.markShipped(orderId).subscribe({
      next: () => this.loadOrders(this.currentPage),
      error: (err: any) => alert(err.error?.detail || 'Failed to mark as shipped.')
    });
  }

  retryUndo(orderId: string): void {
    this.apiService.retryUndo(orderId).subscribe({
      next: (res: any) => {
        alert(res.message);
        this.loadOrders(this.currentPage);
      },
      error: (err: any) => alert(err.error?.detail || 'Failed to retry undo.')
    });
  }
}
