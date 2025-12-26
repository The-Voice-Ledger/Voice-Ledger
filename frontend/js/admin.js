/**
 * Voice Ledger - Admin Dashboard JavaScript
 * Date: December 24, 2025
 * Lab 17: Admin Dashboard
 */

const API_BASE = window.location.origin;
let currentUser = null;
let currentTab = 'registrations';
let currentApprovalUserId = null;

// Initialize dashboard
document.addEventListener('DOMContentLoaded', () => {
  checkAuth();
  loadAdminInfo();
  loadStats();
  loadRegistrations();
});

// Check authentication
function checkAuth() {
  const token = localStorage.getItem('vl_token');
  if (!token) {
    window.location.href = '/login.html';
    return;
  }
  
  // Verify token and role
  fetch(`${API_BASE}/api/auth/me`, {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  })
  .then(response => {
    if (!response.ok) throw new Error('Unauthorized');
    return response.json();
  })
  .then(user => {
    if (user.role !== 'ADMIN') {
      alert('Access denied. Admin role required.');
      logout();
    }
    currentUser = user;
  })
  .catch(error => {
    console.error('Auth error:', error);
    alert('Session expired. Please login again.');
    logout();
  });
}

// Get auth headers
function getAuthHeaders() {
  const token = localStorage.getItem('vl_token');
  return {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  };
}

// Load admin info
function loadAdminInfo() {
  const user = JSON.parse(localStorage.getItem('vl_user') || '{}');
  document.getElementById('adminInfo').textContent = 
    `Logged in as: ${user.name || 'Admin'} (${user.phone_number || ''})`;
}

// Load dashboard statistics
async function loadStats() {
  try {
    const response = await fetch(`${API_BASE}/admin/analytics/summary`, {
      headers: getAuthHeaders()
    });
    
    const data = await response.json();
    
    const statsHTML = `
      <div class="stat-card">
        <div class="stat-label">Total Users</div>
        <div class="stat-value">${data.users.total}</div>
      </div>
      
      <div class="stat-card">
        <div class="stat-label">Pending Approval</div>
        <div class="stat-value">${data.users.pending_approval}</div>
      </div>
      
      <div class="stat-card">
        <div class="stat-label">Active RFQs</div>
        <div class="stat-value">${data.marketplace.active_rfqs}</div>
      </div>
      
      <div class="stat-card">
        <div class="stat-label">Total Batches</div>
        <div class="stat-value">${data.batches.total}</div>
      </div>
      
      <div class="stat-card">
        <div class="stat-label">Pending Settlements</div>
        <div class="stat-value">${data.settlements.pending}</div>
      </div>
    `;
    
    document.getElementById('statsGrid').innerHTML = statsHTML;
  } catch (error) {
    console.error('Failed to load stats:', error);
  }
}

// Switch tabs
function switchTab(tabName) {
  // Update active tab button
  document.querySelectorAll('.tab').forEach(tab => {
    tab.classList.remove('active');
  });
  document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
  
  // Hide all tab contents
  document.querySelectorAll('.tab-content').forEach(content => {
    content.style.display = 'none';
  });
  
  // Show selected tab
  document.getElementById(`${tabName}Tab`).style.display = 'block';
  currentTab = tabName;
  
  // Load data for the tab
  switch (tabName) {
    case 'registrations':
      loadRegistrations();
      break;
    case 'users':
      loadUsers();
      break;
    case 'rfqs':
      loadRFQs();
      break;
    case 'offers':
      loadOffers();
      break;
    case 'settlements':
      loadSettlements();
      break;
  }
}

// Load registrations
async function loadRegistrations() {
  const role = document.getElementById('roleFilter').value;
  const status = document.getElementById('statusFilter').value;
  
  const tbody = document.getElementById('registrationsBody');
  tbody.innerHTML = '<tr><td colspan="8" class="text-center"><div class="spinner"></div> Loading...</td></tr>';
  
  try {
    const params = new URLSearchParams();
    if (status) params.append('status', status);
    if (role) params.append('role', role);
    
    const response = await fetch(`${API_BASE}/admin/registrations?${params}`, {
      headers: getAuthHeaders()
    });
    
    const data = await response.json();
    
    document.getElementById('registrationCount').textContent = data.total;
    
    if (data.registrations.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" class="text-center">No registrations found</td></tr>';
      return;
    }
    
    tbody.innerHTML = data.registrations.map(reg => `
      <tr>
        <td>${reg.id}</td>
        <td>${reg.name || '-'}</td>
        <td>${reg.phone_number || '-'}</td>
        <td><span class="badge badge-info">${reg.role || 'None'}</span></td>
        <td>${reg.organization || '-'}</td>
        <td>${reg.preferred_language === 'am' ? '🇪🇹 Amharic' : '🇺🇸 English'}</td>
        <td>
          ${reg.is_approved 
            ? '<span class="badge badge-success">Approved</span>' 
            : '<span class="badge badge-warning">Pending</span>'}
        </td>
        <td>
          <div class="row-actions">
            ${!reg.is_approved ? `
              <button class="btn btn-success btn-sm" onclick="openApprovalModal(${reg.id}, '${reg.name || 'User'}')">
                ✅ Approve
              </button>
              <button class="btn btn-danger btn-sm" onclick="rejectRegistration(${reg.id})">
                ❌ Reject
              </button>
            ` : `
              <button class="btn btn-sm" onclick="viewUser(${reg.id})">
                👁️ View
              </button>
            `}
          </div>
        </td>
      </tr>
    `).join('');
  } catch (error) {
    console.error('Failed to load registrations:', error);
    tbody.innerHTML = '<tr><td colspan="8" class="text-center">Error loading registrations</td></tr>';
  }
}

// Load users
async function loadUsers() {
  const search = document.getElementById('userSearch').value.trim();
  const role = document.getElementById('userRoleFilter').value;
  
  const tbody = document.getElementById('usersBody');
  tbody.innerHTML = '<tr><td colspan="8" class="text-center"><div class="spinner"></div> Loading...</td></tr>';
  
  try {
    const params = new URLSearchParams({
      ...(search && { search }),
      ...(role && { role }),
      limit: 50
    });
    
    const response = await fetch(`${API_BASE}/admin/users?${params}`, {
      headers: getAuthHeaders()
    });
    
    const data = await response.json();
    
    document.getElementById('userCount').textContent = data.total;
    
    if (data.users.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" class="text-center">No users found</td></tr>';
      return;
    }
    
    tbody.innerHTML = data.users.map(user => `
      <tr>
        <td>${user.id}</td>
        <td>${user.name || '-'}</td>
        <td>${user.phone_number || '-'}</td>
        <td><span class="badge badge-info">${user.role || 'None'}</span></td>
        <td>${user.organization || '-'}</td>
        <td>${user.preferred_language === 'am' ? '🇪🇹 Amharic' : '🇺🇸 English'}</td>
        <td>
          ${user.is_approved 
            ? '<span class="badge badge-success">Approved</span>' 
            : '<span class="badge badge-warning">Pending</span>'}
        </td>
        <td>
          <button class="btn btn-sm" onclick="viewUser(${user.id})">
            👁️ View
          </button>
        </td>
      </tr>
    `).join('');
  } catch (error) {
    console.error('Failed to load users:', error);
    tbody.innerHTML = '<tr><td colspan="8" class="text-center">Error loading users</td></tr>';
  }
}

// Load RFQs
async function loadRFQs() {
  const tbody = document.getElementById('rfqsBody');
  tbody.innerHTML = '<tr><td colspan="6" class="text-center"><div class="spinner"></div> Loading...</td></tr>';
  
  try {
    const response = await fetch(`${API_BASE}/admin/rfqs?limit=50`, {
      headers: getAuthHeaders()
    });
    
    const data = await response.json();
    
    document.getElementById('rfqCount').textContent = data.total;
    
    if (data.rfqs.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" class="text-center">No RFQs found</td></tr>';
      return;
    }
    
    tbody.innerHTML = data.rfqs.map(rfq => `
      <tr>
        <td>${rfq.id}</td>
        <td>${rfq.buyer_name || `Buyer #${rfq.buyer_id}`}</td>
        <td>${rfq.quantity_kg.toLocaleString()}</td>
        <td><span class="badge badge-info">${rfq.grade}</span></td>
        <td><span class="badge badge-${rfq.status === 'ACTIVE' ? 'success' : 'warning'}">${rfq.status}</span></td>
        <td>${rfq.offers_count}</td>
      </tr>
    `).join('');
  } catch (error) {
    console.error('Failed to load RFQs:', error);
    tbody.innerHTML = '<tr><td colspan="6" class="text-center">Error loading RFQs</td></tr>';
  }
}

// Load offers
async function loadOffers() {
  const tbody = document.getElementById('offersBody');
  tbody.innerHTML = '<tr><td colspan="5" class="text-center"><div class="spinner"></div> Loading...</td></tr>';
  
  try {
    const response = await fetch(`${API_BASE}/admin/offers?limit=50`, {
      headers: getAuthHeaders()
    });
    
    const data = await response.json();
    
    document.getElementById('offerCount').textContent = data.total;
    
    if (data.offers.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" class="text-center">No offers found</td></tr>';
      return;
    }
    
    tbody.innerHTML = data.offers.map(offer => `
      <tr>
        <td>${offer.id}</td>
        <td>${offer.rfq_id}</td>
        <td>${offer.cooperative_id}</td>
        <td>$${offer.price_per_kg.toFixed(2)}</td>
        <td><span class="badge badge-info">${offer.status}</span></td>
      </tr>
    `).join('');
  } catch (error) {
    console.error('Failed to load offers:', error);
    tbody.innerHTML = '<tr><td colspan="5" class="text-center">Error loading offers</td></tr>';
  }
}

// Load settlements
async function loadSettlements() {
  const tbody = document.getElementById('settlementsBody');
  tbody.innerHTML = '<tr><td colspan="5" class="text-center"><div class="spinner"></div> Loading...</td></tr>';
  
  try {
    const response = await fetch(`${API_BASE}/admin/settlements?limit=50`, {
      headers: getAuthHeaders()
    });
    
    const data = await response.json();
    
    document.getElementById('settlementCount').textContent = data.total;
    
    if (data.settlements.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" class="text-center">No settlements found</td></tr>';
      return;
    }
    
    tbody.innerHTML = data.settlements.map(settlement => `
      <tr>
        <td>${settlement.id}</td>
        <td>${settlement.rfq_id}</td>
        <td>${settlement.offer_id}</td>
        <td>${settlement.total_value_usd ? `$${settlement.total_value_usd.toFixed(2)}` : '-'}</td>
        <td><span class="badge badge-${settlement.status === 'PENDING' ? 'warning' : 'success'}">${settlement.status}</span></td>
      </tr>
    `).join('');
  } catch (error) {
    console.error('Failed to load settlements:', error);
    tbody.innerHTML = '<tr><td colspan="5" class="text-center">Error loading settlements</td></tr>';
  }
}

// Open approval modal
function openApprovalModal(userId, userName) {
  currentApprovalUserId = userId;
  document.getElementById('approvalUserInfo').textContent = `${userName} (ID: ${userId})`;
  document.getElementById('approvalModal').style.display = 'flex';
  
  // TODO: Load organizations for dropdown
}

// Close approval modal
function closeApprovalModal() {
  document.getElementById('approvalModal').style.display = 'none';
  currentApprovalUserId = null;
  document.getElementById('organizationId').value = '';
  document.getElementById('comments').value = '';
}

// Confirm approval
async function confirmApproval() {
  if (!currentApprovalUserId) return;
  
  const organizationId = document.getElementById('organizationId').value;
  const comments = document.getElementById('comments').value;
  
  const btn = document.getElementById('confirmApproveBtn');
  btn.disabled = true;
  btn.textContent = 'Approving...';
  
  try {
    const response = await fetch(
      `${API_BASE}/admin/registrations/${currentApprovalUserId}/approve`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          organization_id: organizationId ? parseInt(organizationId) : null,
          comments
        })
      }
    );
    
    const data = await response.json();
    
    if (data.success) {
      alert('Registration approved successfully!');
      closeApprovalModal();
      loadRegistrations();
      loadStats();
    } else {
      alert('Failed to approve registration');
    }
  } catch (error) {
    console.error('Approval error:', error);
    alert('Failed to approve registration');
  } finally {
    btn.disabled = false;
    btn.textContent = '✅ Approve';
  }
}

// Reject registration
async function rejectRegistration(userId) {
  if (!confirm('Are you sure you want to reject this registration?')) {
    return;
  }
  
  const comments = prompt('Reason for rejection (optional):');
  
  try {
    const response = await fetch(
      `${API_BASE}/admin/registrations/${userId}/reject`,
      {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ comments })
      }
    );
    
    const data = await response.json();
    
    if (data.success) {
      alert('Registration rejected');
      loadRegistrations();
      loadStats();
    } else {
      alert('Failed to reject registration');
    }
  } catch (error) {
    console.error('Rejection error:', error);
    alert('Failed to reject registration');
  }
}

// View user detail (placeholder)
function viewUser(userId) {
  alert(`User detail view not yet implemented. User ID: ${userId}`);
  // TODO: Implement user detail modal
}

// Logout
function logout() {
  localStorage.removeItem('vl_token');
  localStorage.removeItem('vl_user');
  window.location.href = '/login.html';
}
