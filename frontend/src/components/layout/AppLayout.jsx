import React from 'react';
import Navbar from './Navbar';
import Footer from './Footer';

export default function AppLayout({ activeRoute, onNavigate, children }) {
  return (
    <div className="min-h-screen flex flex-col bg-[#F4EFE6] text-[#15130F]">
      <Navbar activeRoute={activeRoute} onNavigate={onNavigate} />
      <main className="flex-grow">
        {children}
      </main>
      <Footer />
    </div>
  );
}
