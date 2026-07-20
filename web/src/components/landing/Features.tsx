import { Shield, Zap, BarChart3, Bell, Smartphone, Cloud, Lock, Eye } from 'lucide-react';

const features = [
  {
    icon: Shield,
    title: 'Advanced Security',
    description: 'Bank-grade encryption and multi-factor authentication protect your devices and data.',
    color: '#00d4ff',
  },
  {
    icon: Zap,
    title: 'Real-time Monitoring',
    description: 'Instant notifications for device status changes with sub-second latency.',
    color: '#00ff88',
  },
  {
    icon: BarChart3,
    title: 'Analytics Dashboard',
    description: 'Comprehensive insights into device usage, events, and system performance.',
    color: '#ffa502',
  },
  {
    icon: Bell,
    title: 'Smart Alerts',
    description: 'Intelligent notification system that learns your preferences over time.',
    color: '#ff6b6b',
  },
  {
    icon: Smartphone,
    title: 'Cross-platform',
    description: 'Access your dashboard from any device - desktop, tablet, or mobile.',
    color: '#a855f7',
  },
  {
    icon: Cloud,
    title: 'Cloud Sync',
    description: 'Your data is securely backed up and synchronized across all your devices.',
    color: '#3b82f6',
  },
  {
    icon: Lock,
    title: 'Privacy First',
    description: 'End-to-end encryption ensures your data stays private and secure.',
    color: '#ec4899',
  },
  {
    icon: Eye,
    title: 'Remote Access',
    description: 'Control and monitor your devices from anywhere in the world.',
    color: '#14b8a6',
  },
];

export function Features() {
  return (
    <section className="py-24 bg-gradient-to-b from-[#0f2137] to-[#0a1628]">
      <div className="container mx-auto px-4">
        <div className="text-center mb-16">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-white/5 border border-white/10 rounded-full mb-6">
            <span className="text-sm text-[#00d4ff] font-medium">Why Choose Us</span>
          </div>
          <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
            Powerful Features for
            <span className="bg-gradient-to-r from-[#00d4ff] to-[#00ff88] bg-clip-text text-transparent"> Smart Living</span>
          </h2>
          <p className="text-[#6b7a9a] max-w-2xl mx-auto">
            Our platform offers everything you need to manage and secure your connected devices with ease.
          </p>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
          {features.map((feature, index) => (
            <div
              key={index}
              className="group bg-white/5 backdrop-blur-xl rounded-2xl p-6 border border-white/10 hover:border-white/20 transition-all duration-300 hover:-translate-y-1"
            >
              <div
                className="w-14 h-14 rounded-xl flex items-center justify-center mb-4 transition-transform duration-300 group-hover:scale-110"
                style={{ backgroundColor: `${feature.color}15` }}
              >
                <feature.icon className="w-7 h-7" style={{ color: feature.color }} />
              </div>
              <h3 className="text-lg font-semibold text-white mb-2">{feature.title}</h3>
              <p className="text-sm text-[#6b7a9a] leading-relaxed">{feature.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}