import { useEffect, useState, useRef } from 'react';
import { Activity, Shield, Zap, ArrowRight, TrendingUp, Users, Server } from 'lucide-react';
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler } from 'chart.js';
import { Line } from 'react-chartjs-2';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler);

export function Hero() {
  const [activeUsers, setActiveUsers] = useState(12489);
  const [devicesConnected, setDevicesConnected] = useState(89456);
  const [eventsProcessed, setEventsProcessed] = useState(1234567);
  const chartRef = useRef(null);

  useEffect(() => {
    const interval = setInterval(() => {
      setActiveUsers(prev => prev + Math.floor(Math.random() * 50) - 20);
      setDevicesConnected(prev => prev + Math.floor(Math.random() * 100) - 30);
      setEventsProcessed(prev => prev + Math.floor(Math.random() * 500));
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  const data = {
    labels: ['12:00', '14:00', '16:00', '18:00', '20:00', '22:00', '00:00'],
    datasets: [
      {
        label: 'Active Sessions',
        data: [4500, 6200, 7800, 9200, 11000, 12489, 11800],
        borderColor: '#00d4ff',
        backgroundColor: 'rgba(0, 212, 255, 0.1)',
        fill: true,
        tension: 0.4,
        pointRadius: 0,
        pointHoverRadius: 6,
        pointHoverBackgroundColor: '#00d4ff',
      },
    ],
  };

  const options = {
    responsive: true,
    plugins: {
      legend: {
        display: false,
      },
      tooltip: {
        backgroundColor: 'rgba(15, 33, 55, 0.9)',
        titleColor: '#fff',
        bodyColor: '#00d4ff',
        borderColor: 'rgba(0, 212, 255, 0.3)',
        borderWidth: 1,
        padding: 12,
        cornerRadius: 8,
      },
    },
    scales: {
      x: {
        grid: {
          color: 'rgba(255, 255, 255, 0.05)',
        },
        ticks: {
          color: '#6b7a9a',
          font: { size: 11 },
        },
      },
      y: {
        grid: {
          color: 'rgba(255, 255, 255, 0.05)',
        },
        ticks: {
          color: '#6b7a9a',
          font: { size: 11 },
        },
      },
    },
  };

  const stats = [
    { icon: Users, label: 'Active Users', value: activeUsers.toLocaleString(), trend: '+12.5%', color: '#00d4ff' },
    { icon: Server, label: 'Devices Connected', value: devicesConnected.toLocaleString(), trend: '+8.3%', color: '#00ff88' },
    { icon: Activity, label: 'Events Processed', value: eventsProcessed.toLocaleString(), trend: '+24.1%', color: '#ffa502' },
  ];

  return (
    <section className="relative min-h-screen flex items-center justify-center overflow-hidden bg-gradient-to-br from-[#060d17] via-[#0a1628] to-[#0f2137]">
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-[#00d4ff]/20 rounded-full blur-3xl animate-pulse" />
        <div className="absolute top-1/2 -left-40 w-96 h-96 bg-[#00ff88]/15 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '1s' }} />
        <div className="absolute -bottom-40 right-1/4 w-72 h-72 bg-[#ffa502]/10 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '2s' }} />
      </div>

      <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHZpZXdCb3g9IjAgMCA2MCA2MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48ZyBmaWxsPSJub25lIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiPjxnIGZpbGw9IiNmZmYiIGZpbGwtb3BhY2l0eT0iMC4wMyI+PHBhdGggZD0iTTMwIDBjMTYuNTY5IDAgMzAgMTMuNDMxIDMwIDMwIDAgMTYuNTY5LTEzLjQzMSAzMC0zMCAzMEMxMy40MzEgNjAgMCA0Ni41NjkgMCAzMCAwIDEzLjQzMSAxMy40MzEgMCAzMCAwem0wIDU2Yy0xNC4zNjkgMC0yNi0xMS42MzEtMjYtMjYgMC0xNC4zNjkgMTEuNjMxLTI2IDI2LTI2IDE0LjM2OSAwIDI2IDExLjYzMSAyNiAyNiAwIDE0LjM2OS0xMS42MzEgMjYtMjYgMjZ6Ii8+PC9nPjwvZz48L3N2Zz4=')] opacity-50" />

      <div className="relative z-10 container mx-auto px-4 py-20">
        <div className="grid lg:grid-cols-2 gap-12 items-center">
          <div className="text-center lg:text-left">
            <div className="inline-flex items-center gap-2 px-4 py-2 bg-white/5 border border-white/10 rounded-full mb-6">
              <div className="w-2 h-2 bg-[#00ff88] rounded-full animate-pulse" />
              <span className="text-sm text-[#6b7a9a]">Real-time IoT Analytics Platform</span>
            </div>

            <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold text-white leading-tight mb-6">
              Monitor Your
              <span className="bg-gradient-to-r from-[#00d4ff] to-[#00ff88] bg-clip-text text-transparent"> Smart Home </span>
              Anywhere
            </h1>

            <p className="text-lg text-[#6b7a9a] mb-8 max-w-xl mx-auto lg:mx-0">
              Comprehensive security and analytics platform for connected devices. Real-time monitoring, intelligent alerts, and powerful insights at your fingertips.
            </p>

            <div className="flex flex-col sm:flex-row gap-4 justify-center lg:justify-start">
              <button className="group px-8 py-4 bg-gradient-to-r from-[#00d4ff] to-[#00ff88] text-[#0a1628] font-semibold rounded-xl hover:opacity-90 transition-all duration-300 flex items-center justify-center gap-2 shadow-lg shadow-[#00d4ff]/25">
                Get Started
                <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
              </button>
              <button className="px-8 py-4 bg-white/5 border border-white/10 text-white font-semibold rounded-xl hover:bg-white/10 hover:border-white/20 transition-all duration-300 flex items-center justify-center gap-2">
                View Demo
              </button>
            </div>
          </div>

          <div className="relative">
            <div className="bg-white/5 backdrop-blur-xl rounded-3xl p-6 border border-white/10 shadow-2xl shadow-black/20">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h3 className="text-lg font-semibold text-white">Live Dashboard</h3>
                  <p className="text-sm text-[#6b7a9a]">Real-time session metrics</p>
                </div>
                <div className="flex items-center gap-2 px-3 py-1 bg-[#00ff88]/10 rounded-full">
                  <div className="w-2 h-2 bg-[#00ff88] rounded-full animate-pulse" />
                  <span className="text-xs text-[#00ff88] font-medium">Live</span>
                </div>
              </div>

              <div className="h-64 mb-6">
                <Line ref={chartRef} data={data} options={options} />
              </div>

              <div className="grid grid-cols-3 gap-4">
                {stats.map((stat, index) => (
                  <div
                    key={index}
                    className="bg-white/5 rounded-xl p-4 border border-white/5 hover:border-white/10 transition-colors"
                  >
                    <stat.icon className={`w-5 h-5 mb-2`} style={{ color: stat.color }} />
                    <p className="text-xs text-[#6b7a9a] mb-1">{stat.label}</p>
                    <p className="text-lg font-bold text-white">{stat.value}</p>
                    <p className="text-xs mt-1 flex items-center gap-1" style={{ color: stat.color }}>
                      <TrendingUp className="w-3 h-3" />
                      {stat.trend}
                    </p>
                  </div>
                ))}
              </div>
            </div>

            <div className="absolute -top-4 -right-4 bg-white/5 backdrop-blur-xl rounded-2xl p-4 border border-white/10 shadow-xl">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-[#00d4ff]/10 rounded-xl flex items-center justify-center">
                  <Shield className="w-5 h-5 text-[#00d4ff]" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-white">Secure Connection</p>
                  <p className="text-xs text-[#6b7a9a]">256-bit encryption</p>
                </div>
              </div>
            </div>

            <div className="absolute -bottom-4 -left-4 bg-white/5 backdrop-blur-xl rounded-2xl p-4 border border-white/10 shadow-xl">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-[#00ff88]/10 rounded-xl flex items-center justify-center">
                  <Zap className="w-5 h-5 text-[#00ff88]" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-white">Low Latency</p>
                  <p className="text-xs text-[#6b7a9a]">&lt; 50ms response</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}