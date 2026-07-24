import { Shield, Mail, Phone, MapPin } from 'lucide-react';

const footerLinks = {
  product: [
    { name: 'Features', href: '#features' },
    { name: 'Pricing', href: '#pricing' },
    { name: 'API', href: '#api' },
    { name: 'Integrations', href: '#integrations' },
  ],
  company: [
    { name: 'About', href: '#about' },
    { name: 'Blog', href: '#blog' },
    { name: 'Careers', href: '#careers' },
    { name: 'Press', href: '#press' },
  ],
  resources: [
    { name: 'Documentation', href: '#docs' },
    { name: 'Help Center', href: '#help' },
    { name: 'Community', href: '#community' },
    { name: 'Status', href: '#status' },
  ],
  legal: [
    { name: 'Privacy', href: '#privacy' },
    { name: 'Terms', href: '#terms' },
    { name: 'Security', href: '#security' },
    { name: 'Compliance', href: '#compliance' },
  ],
};

export function Footer() {
  return (
    <footer className="bg-[#060d17] border-t border-white/10">
      <div className="container mx-auto px-4 py-16">
        <div className="grid md:grid-cols-2 lg:grid-cols-6 gap-12">
          <div className="lg:col-span-2">
            <div className="flex items-center gap-2 mb-6">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#00d4ff] to-[#00ff88] flex items-center justify-center">
                <Shield className="w-6 h-6 text-[#0a1628]" />
              </div>
              <span className="text-xl font-bold text-white">Heiman</span>
            </div>
            <p className="text-[#6b7a9a] text-sm mb-6 leading-relaxed">
              Comprehensive security and analytics platform for connected devices. Real-time monitoring, intelligent alerts, and powerful insights at your fingertips.
            </p>
            <div className="space-y-3">
              <div className="flex items-center gap-3 text-[#6b7a9a] text-sm">
                <Mail className="w-4 h-4 text-[#00d4ff]" />
                <span>help@heimanhome.com</span>
              </div>
              <div className="flex items-center gap-3 text-[#6b7a9a] text-sm">
                <Phone className="w-4 h-4 text-[#00d4ff]" />
                <span>+8618312377810</span>
              </div>
              <div className="flex items-center gap-3 text-[#6b7a9a] text-sm">
                <MapPin className="w-4 h-4 text-[#00d4ff]" />
                <span>Copyright © Shenzhen Heiman Technology Co., Ltd. Privacy</span>
              </div>
            </div>
          </div>

          <div>
            <h4 className="text-white font-semibold mb-4">Product</h4>
            <ul className="space-y-3">
              {footerLinks.product.map((link) => (
                <li key={link.name}>
                  <a href={link.href} className="text-[#6b7a9a] hover:text-white text-sm transition-colors">
                    {link.name}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h4 className="text-white font-semibold mb-4">Company</h4>
            <ul className="space-y-3">
              {footerLinks.company.map((link) => (
                <li key={link.name}>
                  <a href={link.href} className="text-[#6b7a9a] hover:text-white text-sm transition-colors">
                    {link.name}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h4 className="text-white font-semibold mb-4">Resources</h4>
            <ul className="space-y-3">
              {footerLinks.resources.map((link) => (
                <li key={link.name}>
                  <a href={link.href} className="text-[#6b7a9a] hover:text-white text-sm transition-colors">
                    {link.name}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h4 className="text-white font-semibold mb-4">Legal</h4>
            <ul className="space-y-3">
              {footerLinks.legal.map((link) => (
                <li key={link.name}>
                  <a href={link.href} className="text-[#6b7a9a] hover:text-white text-sm transition-colors">
                    {link.name}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="mt-12 pt-8 border-t border-white/10 flex flex-col md:flex-row items-center justify-between gap-4">
          <p className="text-[#6b7a9a] text-sm">
            2024 Heiman. All rights reserved.
          </p>
          <div className="flex items-center gap-6">
            <a href="#privacy" className="text-[#6b7a9a] hover:text-white text-sm transition-colors">Privacy Policy</a>
            <a href="#terms" className="text-[#6b7a9a] hover:text-white text-sm transition-colors">Terms of Service</a>
            <a href="#cookies" className="text-[#6b7a9a] hover:text-white text-sm transition-colors">Cookie Settings</a>
          </div>
        </div>
      </div>
    </footer>
  );
}
