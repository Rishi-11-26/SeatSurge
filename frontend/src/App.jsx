import React, { useState, useEffect } from 'react';
import AppLayout from './components/layout/AppLayout';
import LandingPage from './pages/LandingPage';
import QueuePlaceholder from './pages/QueuePlaceholder';
import SeatsPlaceholder from './pages/SeatsPlaceholder';
import CheckoutPlaceholder from './pages/CheckoutPlaceholder';

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

  // Programmatic navigation updating the browser URL hash
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
      {activeRoute === 'landing' && <LandingPage onNavigate={navigateTo} />}
      {activeRoute === 'queue' && <QueuePlaceholder onNavigate={navigateTo} />}
      {activeRoute === 'seats' && <SeatsPlaceholder onNavigate={navigateTo} />}
      {activeRoute === 'checkout' && <CheckoutPlaceholder onNavigate={navigateTo} />}
    </AppLayout>
  );
}
