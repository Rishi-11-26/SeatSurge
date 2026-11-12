import React, { useState, useEffect } from 'react';
import AppLayout from './components/layout/AppLayout';
import LandingPage from './pages/LandingPage';
import QueuePage from './pages/QueuePage';
import SeatsPage from './pages/SeatsPage';
import CheckoutPage from './pages/CheckoutPage';

// Supported route identifiers
const VALID_ROUTES = ['landing', 'queue', 'seats', 'checkout'];

function parseHash(hash) {
  const clean = hash.replace(/^#\/?/, '').toLowerCase().trim();
  return VALID_ROUTES.includes(clean) ? clean : 'landing';
}

export default function App() {
  const [activeRoute, setActiveRoute] = useState(() => {
    return parseHash(window.location.hash);
  });

  // Synchronize route with URL hash changes (back/forward, direct link, refresh)
  useEffect(() => {
    const handleHashChange = () => {
      setActiveRoute(parseHash(window.location.hash));
    };

    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  // Programmatic navigation — updates browser URL hash
  const navigateTo = (route) => {
    const targetHash = route === 'landing' ? '#/' : `#/${route}`;
    if (window.location.hash !== targetHash) {
      window.location.hash = targetHash;
    } else {
      setActiveRoute(route);
    }
  };

  return (
    <AppLayout activeRoute={activeRoute} onNavigate={navigateTo}>
      {activeRoute === 'landing'  && <LandingPage  onNavigate={navigateTo} />}
      {activeRoute === 'queue'    && <QueuePage    onNavigate={navigateTo} />}
      {activeRoute === 'seats'    && <SeatsPage    onNavigate={navigateTo} />}
      {activeRoute === 'checkout' && <CheckoutPage onNavigate={navigateTo} />}
    </AppLayout>
  );
}
