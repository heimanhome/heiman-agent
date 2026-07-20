import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Navbar } from '../components/landing/Navbar';
import { Hero } from '../components/landing/Hero';
import { Features } from '../components/landing/Features';
import { PricingTable } from '../components/landing/PricingTable';
import { TrustBadges } from '../components/landing/TrustBadges';
import { Footer } from '../components/landing/Footer';
import { authManager } from '../api/auth-manager';

export function Landing() {
  const navigate = useNavigate();

  useEffect(() => {
    if (authManager.isAuthenticated()) {
      navigate('/dashboard');
    }
  }, [navigate]);

  return (
    <div className="min-h-screen">
      <Navbar />
      <main>
        <Hero />
        <div id="features">
          <Features />
        </div>
        <div id="pricing">
          <PricingTable />
        </div>
        <div id="about">
          <TrustBadges />
        </div>
      </main>
      <Footer />
    </div>
  );
}