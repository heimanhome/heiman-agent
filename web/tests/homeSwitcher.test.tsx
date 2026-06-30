import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { HomeSwitcher } from '@/components/HomeSwitcher';
import type { HomeData } from '@/api/client';

const mockHomes: HomeData[] = [
  {
    id: 'home-1',
    name: '家庭一',
    address: '北京市朝阳区',
    members: [
      { id: 'member-1', name: '张三', role: 'owner', avatar: 'Z' },
      { id: 'member-2', name: '李四', role: 'admin', avatar: 'L' },
    ],
    devices: 5,
    createdAt: '2024-01-01',
  },
  {
    id: 'home-2',
    name: '家庭二',
    address: '上海市浦东新区',
    members: [
      { id: 'member-3', name: '王五', role: 'member', avatar: 'W' },
    ],
    devices: 3,
    createdAt: '2024-02-01',
  },
  {
    id: 'home-3',
    name: '家庭三',
    address: '广州市天河区',
    members: [],
    devices: 0,
    createdAt: '2024-03-01',
  },
];

describe('HomeSwitcher Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render current home name when there are multiple homes', () => {
    render(
      <HomeSwitcher
        currentHomeId="home-1"
        homes={mockHomes}
        onSwitch={vi.fn()}
      />,
    );

    expect(screen.getByText('家庭一')).toBeInTheDocument();
    expect(screen.getByTestId('home-icon')).toBeInTheDocument();
    expect(screen.getByTestId('chevron-down-icon')).toBeInTheDocument();
  });

  it('should not show chevron when only one home exists', () => {
    render(
      <HomeSwitcher
        currentHomeId="home-1"
        homes={[mockHomes[0]]}
        onSwitch={vi.fn()}
      />,
    );

    expect(screen.getByText('家庭一')).toBeInTheDocument();
    expect(screen.queryByTestId('chevron-down-icon')).not.toBeInTheDocument();
  });

  it('should show home list dropdown when clicking the button', async () => {
    render(
      <HomeSwitcher
        currentHomeId="home-1"
        homes={mockHomes}
        onSwitch={vi.fn()}
      />,
    );

    const button = screen.getByText('家庭一');
    fireEvent.click(button);

    await waitFor(() => {
      expect(screen.getByText('家庭二')).toBeInTheDocument();
      expect(screen.getByText('家庭三')).toBeInTheDocument();
    });
  });

  it('should call onSwitch when selecting a different home', async () => {
    const mockOnSwitch = vi.fn();
    render(
      <HomeSwitcher
        currentHomeId="home-1"
        homes={mockHomes}
        onSwitch={mockOnSwitch}
      />,
    );

    const button = screen.getByText('家庭一');
    fireEvent.click(button);

    await waitFor(() => {
      const home2Button = screen.getByText('家庭二');
      fireEvent.click(home2Button);
    });

    expect(mockOnSwitch).toHaveBeenCalledWith('home-2');
  });

  it('should close dropdown when clicking outside', async () => {
    render(
      <HomeSwitcher
        currentHomeId="home-1"
        homes={mockHomes}
        onSwitch={vi.fn()}
      />,
    );

    const button = screen.getByText('家庭一');
    fireEvent.click(button);

    await waitFor(() => {
      expect(screen.getByText('家庭二')).toBeInTheDocument();
    });

    fireEvent.mouseDown(document, { target: document.body });

    await waitFor(() => {
      expect(screen.queryByText('家庭二')).not.toBeInTheDocument();
    });
  });

  it('should highlight selected home in dropdown', async () => {
    render(
      <HomeSwitcher
        currentHomeId="home-2"
        homes={mockHomes}
        onSwitch={vi.fn()}
      />,
    );

    const button = screen.getByText('家庭二');
    fireEvent.click(button);

    await waitFor(() => {
      const homeButtons = screen.getAllByRole('option');
      const home2Button = homeButtons.find((btn) => btn.textContent?.includes('家庭二'));
      expect(home2Button).toHaveAttribute('aria-selected', 'true');
    });
  });

  it('should display device count for each home', async () => {
    render(
      <HomeSwitcher
        currentHomeId="home-1"
        homes={mockHomes}
        onSwitch={vi.fn()}
      />,
    );

    const button = screen.getByText('家庭一');
    fireEvent.click(button);

    await waitFor(() => {
      expect(screen.getByText(/5/)).toBeInTheDocument();
      expect(screen.getByText(/3/)).toBeInTheDocument();
      expect(screen.getByText(/0/)).toBeInTheDocument();
    });
  });

  it('should render null when no homes provided', () => {
    const { container } = render(
      <HomeSwitcher
        currentHomeId="home-1"
        homes={[]}
        onSwitch={vi.fn()}
      />,
    );

    expect(container.firstChild).toBeNull();
  });

  it('should use first home when currentHomeId does not match any home', () => {
    render(
      <HomeSwitcher
        currentHomeId="invalid-home"
        homes={mockHomes}
        onSwitch={vi.fn()}
      />,
    );

    expect(screen.getByText('家庭一')).toBeInTheDocument();
  });

  it('should show title attribute for switch button', () => {
    render(
      <HomeSwitcher
        currentHomeId="home-1"
        homes={mockHomes}
        onSwitch={vi.fn()}
      />,
    );

    const button = screen.getByRole('button');
    expect(button).toHaveAttribute('title', 'homeSwitch.switch');
  });

  it('should show different title when only one home', () => {
    render(
      <HomeSwitcher
        currentHomeId="home-1"
        homes={[mockHomes[0]]}
        onSwitch={vi.fn()}
      />,
    );

    const button = screen.getByRole('button');
    expect(button).toHaveAttribute('title', 'homeSwitch.onlyOne');
  });
});
