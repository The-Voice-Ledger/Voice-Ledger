// Simple role-based access check for mini apps
async function checkUserRole(accessType) {
  const user = window.Telegram?.WebApp?.initDataUnsafe?.user;
  if (!user) return false;
  
  try {
    const res = await fetch('/api/users/me/profile', {
      headers: { 'X-Telegram-User-Id': String(user.id) }
    });
    const profile = res.ok ? await res.json() : { role: 'FARMER', is_approved: false };
    
    if (accessType === 'marketplace') {
      if (!profile.is_approved) {
        alert('Your account is pending approval. Please wait for admin approval before accessing marketplace.');
        return false;
      }
      if (!['BUYER', 'COOPERATIVE_MANAGER'].includes(profile.role)) {
        alert('Marketplace access requires BUYER or COOPERATIVE_MANAGER role. Your current role: ' + (profile.role || 'Unknown'));
        return false;
      }
      return true;
    }
    
    if (accessType === 'farmer') {
      if (!profile.is_approved) {
        alert('Your account is pending approval. Please wait for admin approval before accessing batch management.');
        return false;
      }
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
