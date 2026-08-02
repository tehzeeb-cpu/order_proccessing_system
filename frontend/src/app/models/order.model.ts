export type OrderStatus = 'PENDING' | 'IN_PROGRESS' | 'PLACED' | 'SHIPPED' | 'CANCELLED' | 'NEEDS_ATTENTION';

export interface OrderItem {
  order_id: string;
  sku: string;
  qty: number;
  amount: number;
  status: OrderStatus;
  fail_at?: string;
  comp_fail_at?: string;
  created_at: string;
  updated_at: string;
}

export interface StepExecutionDetail {
  step_name: 'ORDER' | 'INVENTORY' | 'PAYMENT' | 'SHIPPING';
  status: 'PENDING' | 'SUCCESS' | 'FAILED' | 'COMPENSATED' | 'COMPENSATION_FAILED';
  retry_count: number;
  error_message?: string;
  execution_time_ms?: number;
  updated_at: string;
}

export interface LogEntry {
  id: number;
  order_id: string;
  level: string;
  event_type: string;
  message: string;
  created_at: string;
}

export interface OrderDetail extends OrderItem {
  steps: StepExecutionDetail[];
  logs: LogEntry[];
}

export interface DashboardStats {
  total_orders: number;
  placed_count: number;
  shipped_count: number;
  cancelled_count: number;
  needs_attention_count: number;
  in_progress_count: number;
}

export interface PaginatedOrdersResponse {
  items: OrderItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}
