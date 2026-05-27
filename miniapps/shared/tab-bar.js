/**
 * Voice Ledger Mini-App - Shared Tab Bar
 *
 * Usage:  <script src="/miniapps/shared/tab-bar.js"></script>
 * Then call:  vlTabBar('home')      // highlights Home
 * Inserts the tab bar into the page automatically.
 */

window.vlTabBar = async function (activePage) {
  const T = window.vlI18n ? window.vlI18n.t : k => k;
  const tabs = [
    { key: 'home',      href: '/miniapps/index.html',          icon: 'M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z',                                                                                      roles: null },
    { key: 'batches',   href: '/miniapps/batch_browser.html',   icon: 'M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z',       roles: ['FARMER'] },
    { key: 'assistant', href: '/miniapps/assistant.html',       icon: 'M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14l-5-4.87 6.91-1.01L12 2',                                      roles: null },
    { key: 'market',    href: '/miniapps/marketplace.html',     icon: 'M12 1v22M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6',                                                                         roles: ['BUYER', 'COOPERATIVE_MANAGER'] },
    { key: 'profile',   href: '/miniapps/profile.html',         icon: 'M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2 M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0',                                                      roles: null },
  ];

  const profile = typeof getProfile === 'function' ? await getProfile() : null;
  const role = profile ? profile.role : null;

  const visibleTabs = tabs.filter(tab => !tab.roles || (role && tab.roles.includes(role)));

  const nav = document.createElement('nav');
  nav.className = 'vl-tab-bar';
  nav.innerHTML = visibleTabs.map(tab => {
    const isActive = tab.key === activePage;
    return `<a href="${tab.href}"${isActive ? ' class="active"' : ''}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="${tab.icon}"/></svg>
      <span data-i18n="${tab.key}">${T(tab.key)}</span>
    </a>`;
  }).join('');

  document.body.appendChild(nav);
};
