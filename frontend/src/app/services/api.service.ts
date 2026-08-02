import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { DashboardStats, PaginatedOrdersResponse, OrderDetail, LogEntry } from '../models/order.model';

@Injectable({
  providedIn: 'root'
})
export class ApiService {
  private baseUrl = 'http://localhost:8000/api/v1/coordinator';

  constructor(private http: HttpClient) {}

  uploadBulkCsv(file: File): Observable<any> {
    const formData = new FormData();
    formData.append('file', file);
    return this.http.post(`${this.baseUrl}/upload-bulk`, formData);
  }

  getDashboardStats(): Observable<DashboardStats> {
    return this.http.get<DashboardStats>(`${this.baseUrl}/dashboard/stats`);
  }

  getOrders(page: number = 1, pageSize: number = 20, status: string = 'ALL', search: string = ''): Observable<PaginatedOrdersResponse> {
    let params = new HttpParams()
      .set('page', page.toString())
      .set('page_size', pageSize.toString());

    if (status && status !== 'ALL') {
      params = params.set('status', status);
    }
    if (search) {
      params = params.set('search', search);
    }

    return this.http.get<PaginatedOrdersResponse>(`${this.baseUrl}/orders`, { params });
  }

  getOrderDetails(orderId: string): Observable<OrderDetail> {
    return this.http.get<OrderDetail>(`${this.baseUrl}/orders/${orderId}`);
  }

  retryUndo(orderId: string): Observable<any> {
    return this.http.post(`${this.baseUrl}/orders/${orderId}/retry-undo`, {});
  }

  markShipped(orderId: string): Observable<any> {
    return this.http.post(`${this.baseUrl}/orders/${orderId}/mark-shipped`, {});
  }

  getLogs(page: number = 1, pageSize: number = 50): Observable<LogEntry[]> {
    let params = new HttpParams()
      .set('page', page.toString())
      .set('page_size', pageSize.toString());
    return this.http.get<LogEntry[]>(`${this.baseUrl}/logs`, { params });
  }

  resetDemo(): Observable<any> {
    return this.http.post(`${this.baseUrl}/reset-demo`, {});
  }
}
