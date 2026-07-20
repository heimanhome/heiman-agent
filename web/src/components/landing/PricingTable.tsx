import { Check, X, Zap } from 'lucide-react';

const plans = [
  {
    name: 'Starter',
    description: 'Perfect for small homes',
    price: 'Free',
    period: 'forever',
    color: '#6b7a9a',
    popular: false,
    features: [
      { text: 'Up to 10 devices', included: true },
      { text: 'Basic analytics', included: true },
      { text: 'Email alerts', included: true },
      { text: '7-day data retention', included: true },
      { text: 'Community support', included: true },
      { text: 'Advanced analytics', included: false },
      { text: 'API access', included: false },
      { text: 'Priority support', included: false },
    ],
  },
  {
    name: 'Pro',
    description: 'For growing smart homes',
    price: '$29',
    period: 'per month',
    color: '#00d4ff',
    popular: true,
    features: [
      { text: 'Up to 50 devices', included: true },
      { text: 'Advanced analytics', included: true },
      { text: 'SMS & push alerts', included: true },
      { text: '30-day data retention', included: true },
      { text: 'Email support', included: true },
      { text: 'Custom rules', included: true },
      { text: 'API access', included: true },
      { text: 'Priority support', included: false },
    ],
  },
  {
    name: 'Enterprise',
    description: 'For businesses & organizations',
    price: '$99',
    period: 'per month',
    color: '#00ff88',
    popular: false,
    features: [
      { text: 'Unlimited devices', included: true },
      { text: 'Custom analytics', included: true },
      { text: 'All alert channels', included: true },
      { text: 'Unlimited retention', included: true },
      { text: 'Dedicated support', included: true },
      { text: 'SLA guarantee', included: true },
      { text: 'Custom integrations', included: true },
      { text: 'Priority support', included: true },
    ],
  },
];

export function PricingTable() {
  return (
    <section className="py-24 bg-gradient-to-b from-[#0a1628] to-[#060d17]">
      <div className="container mx-auto px-4">
        <div className="text-center mb-16">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-white/5 border border-white/10 rounded-full mb-6">
            <span className="text-sm text-[#00ff88] font-medium">Simple Pricing</span>
          </div>
          <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
            Choose Your
            <span className="bg-gradient-to-r from-[#00d4ff] to-[#00ff88] bg-clip-text text-transparent"> Plan</span>
          </h2>
          <p className="text-[#6b7a9a] max-w-2xl mx-auto">
            Start free and scale as you grow. No hidden fees, no surprises.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
          {plans.map((plan, index) => (
            <div
              key={index}
              className={`relative bg-white/5 backdrop-blur-xl rounded-3xl p-8 border transition-all duration-300 hover:-translate-y-2 ${
                plan.popular
                  ? 'border-[#00d4ff]/50 shadow-xl shadow-[#00d4ff]/10'
                  : 'border-white/10 hover:border-white/20'
              }`}
            >
              {plan.popular && (
                <div className="absolute -top-4 left-1/2 -translate-x-1/2">
                  <div className="flex items-center gap-1 px-4 py-1 bg-gradient-to-r from-[#00d4ff] to-[#00ff88] rounded-full">
                    <Zap className="w-3 h-3 text-[#0a1628]" />
                    <span className="text-xs font-bold text-[#0a1628]">Most Popular</span>
                  </div>
                </div>
              )}

              <div className="mb-8">
                <h3 className="text-xl font-bold text-white mb-2">{plan.name}</h3>
                <p className="text-sm text-[#6b7a9a]">{plan.description}</p>
              </div>

              <div className="mb-8">
                <span className="text-5xl font-bold text-white">{plan.price}</span>
                <span className="text-[#6b7a9a] ml-1">/{plan.period}</span>
              </div>

              <ul className="space-y-4 mb-8">
                {plan.features.map((feature, featureIndex) => (
                  <li key={featureIndex} className="flex items-start gap-3">
                    {feature.included ? (
                      <Check className="w-5 h-5 text-[#00ff88] shrink-0 mt-0.5" />
                    ) : (
                      <X className="w-5 h-5 text-[#6b7a9a] shrink-0 mt-0.5" />
                    )}
                    <span className={feature.included ? 'text-white' : 'text-[#6b7a9a]'}>
                      {feature.text}
                    </span>
                  </li>
                ))}
              </ul>

              <button
                className={`w-full py-3 rounded-xl font-semibold transition-all duration-300 ${
                  plan.popular
                    ? 'bg-gradient-to-r from-[#00d4ff] to-[#00ff88] text-[#0a1628] hover:opacity-90 shadow-lg shadow-[#00d4ff]/25'
                    : 'bg-white/5 border border-white/20 text-white hover:bg-white/10'
                }`}
              >
                {plan.price === 'Free' ? 'Get Started' : 'Start Trial'}
              </button>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}