import { Shield, Award, Globe, Users, Star, CheckCircle } from 'lucide-react';

const badges = [
  { icon: Shield, label: '256-bit Encryption', description: 'Bank-grade security' },
  { icon: Award, label: 'SOC 2 Certified', description: 'Enterprise compliance' },
  { icon: Globe, label: 'Global CDN', description: '99.9% uptime' },
  { icon: Users, label: '50K+ Users', description: 'Trusted worldwide' },
];

const testimonials = [
  {
    content: 'The platform has transformed how we manage our smart home devices. The real-time alerts and analytics are invaluable.',
    author: 'Sarah Chen',
    role: 'Homeowner',
    avatar: 'SC',
    rating: 5,
  },
  {
    content: 'As a property manager, this tool saves me hours every day. The automation and insights are game-changing.',
    author: 'Michael Johnson',
    role: 'Property Manager',
    avatar: 'MJ',
    rating: 5,
  },
  {
    content: 'The security features give me peace of mind. Knowing my devices are protected 24/7 is priceless.',
    author: 'Emily Davis',
    role: 'Tech Enthusiast',
    avatar: 'ED',
    rating: 5,
  },
];

const stats = [
  { value: '50K+', label: 'Active Users' },
  { value: '1M+', label: 'Devices Monitored' },
  { value: '99.9%', label: 'Uptime Guarantee' },
  { value: '24/7', label: 'Support Available' },
];

export function TrustBadges() {
  return (
    <section className="py-24 bg-gradient-to-b from-[#060d17] to-[#0f2137]">
      <div className="container mx-auto px-4">
        <div className="text-center mb-16">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-white/5 border border-white/10 rounded-full mb-6">
            <span className="text-sm text-[#00d4ff] font-medium">Trusted by Thousands</span>
          </div>
          <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
            Join the
            <span className="bg-gradient-to-r from-[#00d4ff] to-[#00ff88] bg-clip-text text-transparent"> Community</span>
          </h2>
          <p className="text-[#6b7a9a] max-w-2xl mx-auto">
            Thousands of users trust our platform to keep their smart homes secure and connected.
          </p>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-6 mb-16">
          {stats.map((stat, index) => (
            <div
              key={index}
              className="bg-white/5 backdrop-blur-xl rounded-2xl p-6 border border-white/10 text-center"
            >
              <p className="text-3xl md:text-4xl font-bold bg-gradient-to-r from-[#00d4ff] to-[#00ff88] bg-clip-text text-transparent mb-2">
                {stat.value}
              </p>
              <p className="text-sm text-[#6b7a9a]">{stat.label}</p>
            </div>
          ))}
        </div>

        <div className="flex flex-wrap justify-center gap-8 mb-16">
          {badges.map((badge, index) => (
            <div
              key={index}
              className="flex items-center gap-3 px-6 py-3 bg-white/5 border border-white/10 rounded-full"
            >
              <badge.icon className="w-5 h-5 text-[#00d4ff]" />
              <div>
                <p className="text-sm font-semibold text-white">{badge.label}</p>
                <p className="text-xs text-[#6b7a9a]">{badge.description}</p>
              </div>
            </div>
          ))}
        </div>

        <div className="grid md:grid-cols-3 gap-8 max-w-4xl mx-auto">
          {testimonials.map((testimonial, index) => (
            <div
              key={index}
              className="bg-white/5 backdrop-blur-xl rounded-2xl p-6 border border-white/10 hover:border-white/20 transition-colors"
            >
              <div className="flex gap-1 mb-4">
                {[...Array(testimonial.rating)].map((_, i) => (
                  <Star key={i} className="w-4 h-4 text-[#ffa502] fill-[#ffa502]" />
                ))}
              </div>
              <p className="text-[#6b7a9a] mb-6 leading-relaxed">"{testimonial.content}"</p>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-gradient-to-r from-[#00d4ff] to-[#00ff88] flex items-center justify-center">
                  <span className="text-sm font-bold text-[#0a1628]">{testimonial.avatar}</span>
                </div>
                <div>
                  <p className="text-sm font-semibold text-white">{testimonial.author}</p>
                  <p className="text-xs text-[#6b7a9a]">{testimonial.role}</p>
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-16 bg-gradient-to-r from-[#00d4ff]/10 to-[#00ff88]/10 rounded-3xl p-8 md:p-12 border border-white/10">
          <div className="flex flex-col md:flex-row items-center justify-between gap-8">
            <div>
              <h3 className="text-2xl md:text-3xl font-bold text-white mb-2">
                Ready to Get Started?
              </h3>
              <p className="text-[#6b7a9a]">
                Join thousands of users who trust our platform for their smart home needs.
              </p>
            </div>
            <div className="flex flex-col sm:flex-row gap-4">
              <button className="px-8 py-4 bg-gradient-to-r from-[#00d4ff] to-[#00ff88] text-[#0a1628] font-semibold rounded-xl hover:opacity-90 transition-all duration-300 flex items-center justify-center gap-2 shadow-lg shadow-[#00d4ff]/25">
                <CheckCircle className="w-5 h-5" />
                Start Free Trial
              </button>
              <button className="px-8 py-4 bg-white/5 border border-white/10 text-white font-semibold rounded-xl hover:bg-white/10 hover:border-white/20 transition-all duration-300">
                Contact Sales
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}