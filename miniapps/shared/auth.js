// Simple role-based access check for mini apps

async function getProfile() {
  if (window._vlProfile) return window._vlProfile;
  const user = window.Telegram?.WebApp?.initDataUnsafe?.user;
  if (!user) return null;
  try {
    const res = await fetch('/api/users/me/profile', {
      headers: { 'X-Telegram-User-Id': String(user.id) }
    });
    if (!res.ok) { console.error('Profile API failed:', res.status); return null; }
    window._vlProfile = await res.json();
    return window._vlProfile;
  } catch (e) {
    console.error('Profile fetch error:', e);
    return null;
  }
}

async function checkUserRole(accessType) {
  const profile = await getProfile();
  if (!profile) return false;
  
  try {
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
