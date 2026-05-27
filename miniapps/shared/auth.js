// Simple role-based access check for mini apps

const PROFILE_CACHE_KEY = 'vl_profile';
const PROFILE_CACHE_TTL = 5 * 60 * 1000; // 5 minutes

async function getProfile() {
  // Check in-memory cache first
  if (window._vlProfile) return window._vlProfile;

  // Check localStorage cache
  const cached = localStorage.getItem(PROFILE_CACHE_KEY);
  if (cached) {
    try {
      const { profile, timestamp } = JSON.parse(cached);
      const now = Date.now();
      if (now - timestamp < PROFILE_CACHE_TTL) {
        console.log('Using cached profile from localStorage');
        window._vlProfile = profile;
        return profile;
      } else {
        console.log('Profile cache expired, fetching fresh');
        localStorage.removeItem(PROFILE_CACHE_KEY);
      }
    } catch (e) {
      console.error('Error parsing cached profile:', e);
      localStorage.removeItem(PROFILE_CACHE_KEY);
    }
  }

  // Fetch from backend
  const user = window.Telegram?.WebApp?.initDataUnsafe?.user;
  if (!user) return null;
  try {
    const res = await fetch('/api/users/me/profile', {
      headers: { 'X-Telegram-User-Id': String(user.id) }
    });
    if (!res.ok) { console.error('Profile API failed:', res.status); return null; }
    const profile = await res.json();
    window._vlProfile = profile;

    // Cache in localStorage
    localStorage.setItem(PROFILE_CACHE_KEY, JSON.stringify({
      profile,
      timestamp: Date.now()
    }));

    return profile;
  } catch (e) {
    console.error('Profile fetch error:', e);
    return null;
  }
}

function clearProfileCache() {
  window._vlProfile = null;
  localStorage.removeItem(PROFILE_CACHE_KEY);
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
