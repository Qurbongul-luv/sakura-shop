import React from 'react';
import { Home, Heart, ShoppingBag, Star, Settings, ShieldCheck, Gift } from 'lucide-react';
import { haptic } from '../utils/telegram';

export type TabType = 'home' | 'wishlist' | 'bag' | 'contest' | 'reviews' | 'settings' | 'admin';

interface BottomNavProps {
  currentTab: TabType;
  onTabChange: (tab: TabType) => void;
  cartCount: number;
  wishlistCount: number;
  isAdmin: boolean;
  labels: {
    home: string;
    wishlist: string;
    bag: string;
    contest: string;
    reviews: string;
    settings: string;
    adminPanel: string;
  };
}

export const BottomNav: React.FC<BottomNavProps> = ({
  currentTab,
  onTabChange,
  cartCount,
  wishlistCount,
  isAdmin,
  labels,
}) => {
  const handleTabClick = (tab: TabType) => {
    haptic.selection();
    onTabChange(tab);
  };

  const tabs: { id: TabType; label: string; icon: React.ReactNode; badge?: number }[] = [
    { id: 'home', label: labels.home, icon: <Home className="w-5 h-5" /> },
    { id: 'contest', label: labels.contest, icon: <Gift className="w-5 h-5" /> },
    { id: 'bag', label: labels.bag, icon: <ShoppingBag className="w-5 h-5" />, badge: cartCount },
    { id: 'wishlist', label: labels.wishlist, icon: <Heart className="w-5 h-5" />, badge: wishlistCount },
    { id: 'reviews', label: labels.reviews, icon: <Star className="w-5 h-5" /> },
    { id: 'settings', label: labels.settings, icon: <Settings className="w-5 h-5" /> },
  ];

  if (isAdmin) {
    tabs.push({
      id: 'admin',
      label: labels.adminPanel,
      icon: <ShieldCheck className="w-5 h-5" />,
    });
  }

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-40 bg-white/95 dark:bg-sakura-darkcard/95 backdrop-blur-lg border-t border-sakura-pink/30 pb-safe shadow-sakura-lg">
      <div className="max-w-md mx-auto flex items-center justify-around py-1.5 px-2">
        {tabs.map((tab) => {
          const isActive = currentTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => handleTabClick(tab.id)}
              className={`relative flex flex-col items-center justify-center py-1 px-2.5 rounded-2xl transition-all duration-200 active:scale-90 ${
                isActive
                  ? 'text-sakura-rose dark:text-sakura-pink font-extrabold'
                  : 'text-sakura-plum/60 dark:text-sakura-blush/60 font-medium hover:text-sakura-rose'
              }`}
            >
              {/* Icon Container with Badge */}
              <div className="relative">
                <div
                  className={`p-1 rounded-xl transition-all ${
                    isActive ? 'bg-sakura-blush/80 dark:bg-sakura-darkcardsoft scale-110' : ''
                  }`}
                >
                  {tab.icon}
                </div>

                {/* Badge Counter */}
                {tab.badge !== undefined && tab.badge > 0 && (
                  <span className="absolute -top-1 -right-1.5 min-w-[17px] h-[17px] flex items-center justify-center px-1 rounded-full bg-sakura-rose text-white text-[10px] font-black shadow-sm animate-scale-in">
                    {tab.badge > 99 ? '99+' : tab.badge}
                  </span>
                )}
              </div>

              {/* Label */}
              <span className="text-[10px] mt-0.5 tracking-tight">{tab.label}</span>
            </button>
          );
        })}
      </div>
    </nav>
  );
};
