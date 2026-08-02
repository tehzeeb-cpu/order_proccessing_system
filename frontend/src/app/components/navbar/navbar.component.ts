import { Component } from '@angular/core';
import { RouterModule } from '@angular/router';

@Component({
  selector: 'app-navbar',
  standalone: true,
  imports: [RouterModule],
  template: `
    <header class="navbar-header">
      <div class="brand-title">
        <span class="material-icons" style="font-size: 28px; color: #818cf8;">hub</span>
        <span>Order Saga Processing Engine</span>
      </div>
      <nav class="nav-links">
        <a routerLink="/dashboard" routerLinkActive="active" class="nav-link">
          <span class="material-icons" style="font-size: 18px;">dashboard</span> Dashboard
        </a>
        <a routerLink="/orders" routerLinkActive="active" class="nav-link">
          <span class="material-icons" style="font-size: 18px;">list_alt</span> Orders
        </a>
        <a routerLink="/needs-attention" routerLinkActive="active" class="nav-link" style="color: #fbbf24;">
          <span class="material-icons" style="font-size: 18px;">warning</span> Needs Attention
        </a>
        <a routerLink="/logs" routerLinkActive="active" class="nav-link">
          <span class="material-icons" style="font-size: 18px;">receipt_long</span> Audit Logs
        </a>
      </nav>
    </header>
  `
})
export class NavbarComponent {}
