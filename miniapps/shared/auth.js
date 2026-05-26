// Simple role-based access check for mini apps
async function checkUserRole(accessType) {
  const user = window.Telegram?.WebApp?.initDataUnsafe?.user;
  if (!user) return false;
  
  try {
    const res = await fetch('/api/users/me/profile', {
      headers: { 'X-Telegram-User-Id': String(user.id) }
    });
    if (!res.ok) {
    console.error('Profile API failed:', res.status);
    return false;
  }
  const profile = await res.json();
    
    if (accessType === 'marketplace') {
      if (!profile.is_approved) {
        alert('Your account is pending approval. Please wait for admin approval before accessing marketplace.');
        return false;
      }
      if (profile.role !== 'BUYER' && profile.role !== 'COOPERATIVE_MANAGER') {
        alert('Marketplace access requires BUYER or COOPERATIVE_MANAGER role. Your current role: ' + (profile.role || 'Unknown'));
        return false;
      }
      return true;
    }
    
    if (accessType === 'farmer') {
      if (profile.role !== 'FARMER') {
        alert('Batch Browser access requires FARMER role. Your current role: ' + (profile.role || 'Unknown'));
        return false;
      }
      return true;
    }
    
    if (accessType === 'admin') {
      if (!profile.is_approved) {
        alert('Your account is pending approval. Please wait for admin approval before accessing admin panel.');
        return false;
      }
      if (profile.role !== 'ADMIN') {
        alert('Admin Panel access requires ADMIN role. Your current role: ' + (profile.role || 'Unknown'));
        return false;
      }
      return true;
    }
    
    return true;
  } catch (e) {
    console.error('Role check error:', e);
    alert('Unable to verify access. Please try again.');
    return false;
  }
}
