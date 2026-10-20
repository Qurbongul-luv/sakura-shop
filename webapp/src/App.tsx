import React, { useState, useEffect } from 'react';
import { Product, Category, CartSummary, ShopSettings, Review, TelegramUser } from './types';
import { Header } from './components/Header';
import { BottomNav, TabType } from './components/BottomNav';
import { HomePage } from './pages/HomePage';
import { ProductDetailPage } from './pages/ProductDetailPage';
import { BagPage } from './pages/BagPage';
import { WishlistPage } from './pages/WishlistPage';
import { ReviewsPage } from './pages/ReviewsPage';
import { SettingsPage } from './pages/SettingsPage';
import { AdminPage } from './pages/AdminPage';
import { ContestPage } from './pages/ContestPage';
import { Language, translations } from './i18n';
import { getTelegramWebApp, initTelegramApp, haptic } from './utils/telegram';

export const App: React.FC = () => {
  const [lang, setLang] = useState<Language>('uz');
  const [currentTab, setCurrentTab] = useState<TabType>('home');
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);

  // Shop Data
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [heroProduct, setHeroProduct] = useState<Product | null>(null);
  const [cart, setCart] = useState<CartSummary | null>(null);
  const [wishlistIds, setWishlistIds] = useState<number[]>([]);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [shopSettings, setShopSettings] = useState<ShopSettings>({
    cargo_rate: 12000,
    delivery_days: '10–15 kun',
    delivery_scope: "O'zbekiston bo'ylab",
    payment_terms: "100% oldindan to'lov",
    location: 'Toshkent',
    contact_username: 'fkhrdnvvvva',
    channel_url: 'https://t.me/sakuraaa_chinese_shop',
    has_linked_channel: false,
    welcome_text: 'Sakura shop ga xush kelibsiz! 🌸',
  });

  // User State
  const [telegramUser, setTelegramUser] = useState<TelegramUser | null>(null);
  const [initData, setInitData] = useState<string>('');
  const [isAdmin, setIsAdmin] = useState(false);

  // Filters & Visuals
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [petalsEnabled, setPetalsEnabled] = useState(true);
  const [reducedMotion, setReducedMotion] = useState(false);
  const [loading, setLoading] = useState(true);

  const t = translations[lang];

  // Initialize Telegram WebApp
  useEffect(() => {
    initTelegramApp();
    const tg = getTelegramWebApp();
    let rawInitData = tg?.initData || '';
    if (!rawInitData && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')) {
      rawInitData = 'dev_browser_mode';
    }
    setInitData(rawInitData);

    if (tg?.initDataUnsafe?.user) {
      const u = tg.initDataUnsafe.user;
      setTelegramUser({
        id: u.id,
        first_name: u.first_name,
        last_name: u.last_name,
        username: u.username,
        language_code: u.language_code || 'uz',
      });
      if (['uz', 'ru', 'en'].includes(u.language_code)) {
        setLang(u.language_code as Language);
      }
    } else if (rawInitData === 'dev_browser_mode') {
      setTelegramUser({
        id: 12345678,
        first_name: 'Sakura',
        last_name: 'Admin',
        username: 'fkhrdnvvvva',
        language_code: 'uz',
      });
    }

    // Handle deep links in URL query (e.g. ?product=1 or ?tab=admin or startapp=product_1)
    const urlParams = new URLSearchParams(window.location.search);
    const prodParam = urlParams.get('product') || urlParams.get('startapp');
    const tabParam = urlParams.get('tab') as TabType;

    if (tabParam) {
      setCurrentTab(tabParam);
    }

    fetchInitialData(rawInitData, prodParam);
  }, []);

  // Telegram BackButton management
  useEffect(() => {
    const tg = getTelegramWebApp();
    if (!tg?.BackButton) return;

    if (selectedProduct) {
      tg.BackButton.show();
      const handleBack = () => setSelectedProduct(null);
      tg.BackButton.onClick(handleBack);
      return () => {
        tg.BackButton.offClick(handleBack);
        tg.BackButton.hide();
      };
    } else {
      tg.BackButton.hide();
    }
  }, [selectedProduct]);

  const fetchInitialData = async (rawInitData: string, initialProductParam?: string | null) => {
    setLoading(true);
    const authHeaders: Record<string, string> = rawInitData
      ? { 'X-Telegram-Init-Data': rawInitData }
      : {};

    try {
      // 1. Fetch public settings
      const settingsResp = await fetch('/api/settings');
      if (settingsResp.ok) {
        setShopSettings(await settingsResp.json());
      }

      // 2. Fetch categories
      const catResp = await fetch('/api/categories');
      if (catResp.ok) {
        setCategories(await catResp.json());
      }

      // 3. Fetch products
      const prodResp = await fetch('/api/products');
      if (prodResp.ok) {
        const prodData: Product[] = await prodResp.json();
        setProducts(prodData);

        // Check if direct deep link to product was requested
        if (initialProductParam) {
          const cleanId = initialProductParam.replace('product_', '');
          const target = prodData.find((p) => p.id === parseInt(cleanId));
          if (target) {
            setSelectedProduct(target);
          }
        }
      }

      // 4. Fetch hero product
      const heroResp = await fetch('/api/products/hero');
      if (heroResp.ok) {
        setHeroProduct(await heroResp.json());
      }

      // 5. Fetch reviews
      const revResp = await fetch('/api/reviews');
      if (revResp.ok) {
        setReviews(await revResp.json());
      }

      // 6. If user authenticated, fetch cart & wishlist & admin check
      if (rawInitData) {
        const cartResp = await fetch('/api/cart', { headers: authHeaders });
        if (cartResp.ok) {
          setCart(await cartResp.json());
        }

        const wishResp = await fetch('/api/wishlist/ids', { headers: authHeaders });
        if (wishResp.ok) {
          setWishlistIds(await wishResp.json());
        }

        // Test admin access
        const adminCheckResp = await fetch('/api/admin/stats', { headers: authHeaders });
        if (adminCheckResp.ok) {
          setIsAdmin(true);
        }
      }
    } catch (e) {
      console.error('Error fetching initial data:', e);
    } finally {
      setLoading(false);
    }
  };

  const refreshProducts = async () => {
    try {
      const prodResp = await fetch('/api/products');
      if (prodResp.ok) {
        setProducts(await prodResp.json());
      }
    } catch (e) {
      console.error(e);
    }
  };

  const refreshCategories = async () => {
    try {
      const catResp = await fetch('/api/categories');
      if (catResp.ok) {
        setCategories(await catResp.json());
      }
    } catch (e) {
      console.error(e);
    }
  };

  const refreshReviews = async () => {
    try {
      const revResp = await fetch('/api/reviews');
      if (revResp.ok) {
        setReviews(await revResp.json());
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleToggleWishlist = async (productId: number) => {
    if (!initData) {
      // Offline/demo fallback toggle
      setWishlistIds((prev) =>
        prev.includes(productId) ? prev.filter((id) => id !== productId) : [...prev, productId]
      );
      return;
    }

    try {
      const resp = await fetch('/api/wishlist/toggle', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Telegram-Init-Data': initData,
        },
        body: JSON.stringify({ product_id: productId }),
      });
      if (resp.ok) {
        const data = await resp.json();
        setWishlistIds((prev) =>
          data.is_wishlisted ? [...prev, productId] : prev.filter((id) => id !== productId)
        );
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleAddToCart = async (product: Product, size?: string, color?: string) => {
    if (!initData) {
      // Mock cart update for browser preview
      const newItem = {
        id: Date.now(),
        product_id: product.id,
        product_title: product.title,
        product_price: product.price,
        product_photo: product.photos?.[0],
        size,
        color,
        qty: 1,
        weight_grams: product.weight_grams,
        item_total: product.price,
        formatted_item_total: `${product.price.toLocaleString()} so'm`,
      };
      setCart((prev) => {
        const items = prev ? [...prev.items, newItem] : [newItem];
        const subtotal = items.reduce((acc, it) => acc + it.item_total, 0);
        return {
          items,
          total_items: items.length,
          subtotal,
          formatted_subtotal: `${subtotal.toLocaleString()} so'm`,
          estimated_cargo: 24000,
          formatted_estimated_cargo: "24.000 so'm",
          grand_total: subtotal + 24000,
          formatted_grand_total: `${(subtotal + 24000).toLocaleString()} so'm`,
        };
      });
      return;
    }

    try {
      const resp = await fetch('/api/cart', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Telegram-Init-Data': initData,
        },
        body: JSON.stringify({
          product_id: product.id,
          size: size || null,
          color: color || null,
          qty: 1,
        }),
      });
      if (resp.ok) {
        setCart(await resp.json());
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleUpdateCartQty = async (itemId: number, newQty: number) => {
    if (!initData) {
      setCart((prev) => {
        if (!prev) return null;
        const items = prev.items.map((it) =>
          it.id === itemId
            ? { ...it, qty: newQty, item_total: it.product_price * newQty }
            : it
        );
        const subtotal = items.reduce((acc, it) => acc + it.item_total, 0);
        return {
          ...prev,
          items,
          subtotal,
          formatted_subtotal: `${subtotal.toLocaleString()} so'm`,
          grand_total: subtotal + prev.estimated_cargo,
          formatted_grand_total: `${(subtotal + prev.estimated_cargo).toLocaleString()} so'm`,
        };
      });
      return;
    }

    try {
      const resp = await fetch(`/api/cart/${itemId}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'X-Telegram-Init-Data': initData,
        },
        body: JSON.stringify({ qty: newQty }),
      });
      if (resp.ok) {
        setCart(await resp.json());
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleRemoveCartItem = async (itemId: number) => {
    if (!initData) {
      setCart((prev) => {
        if (!prev) return null;
        const items = prev.items.filter((it) => it.id !== itemId);
        const subtotal = items.reduce((acc, it) => acc + it.item_total, 0);
        return {
          ...prev,
          items,
          total_items: items.length,
          subtotal,
          formatted_subtotal: `${subtotal.toLocaleString()} so'm`,
          grand_total: subtotal + prev.estimated_cargo,
          formatted_grand_total: `${(subtotal + prev.estimated_cargo).toLocaleString()} so'm`,
        };
      });
      return;
    }

    try {
      const resp = await fetch(`/api/cart/${itemId}`, {
        method: 'DELETE',
        headers: { 'X-Telegram-Init-Data': initData },
      });
      if (resp.ok) {
        setCart(await resp.json());
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleClearCart = async () => {
    if (!initData) {
      setCart(null);
      return;
    }
    try {
      const resp = await fetch('/api/cart', {
        method: 'DELETE',
        headers: { 'X-Telegram-Init-Data': initData },
      });
      if (resp.ok) {
        setCart(await resp.json());
      }
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="min-h-screen bg-sakura-cream dark:bg-sakura-darkbg text-sakura-plum dark:text-sakura-blush">
      {/* Main Top Header */}
      {!selectedProduct && (
        <Header
          lang={lang}
          onLanguageChange={setLang}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          petalsEnabled={petalsEnabled && !reducedMotion}
        />
      )}

      {/* Main Content Router */}
      <main className="max-w-md mx-auto">
        {selectedProduct ? (
          <ProductDetailPage
            product={selectedProduct}
            settings={shopSettings}
            isWishlisted={wishlistIds.includes(selectedProduct.id)}
            onToggleWishlist={handleToggleWishlist}
            onAddToCart={handleAddToCart}
            onBack={() => setSelectedProduct(null)}
            t={t}
          />
        ) : (
          <>
            {currentTab === 'home' && (
              <HomePage
                products={products}
                categories={categories}
                heroProduct={heroProduct}
                wishlistIds={wishlistIds}
                onToggleWishlist={handleToggleWishlist}
                onSelectProduct={setSelectedProduct}
                searchQuery={searchQuery}
                selectedCategory={selectedCategory}
                onSelectCategory={setSelectedCategory}
                t={t}
                loading={loading}
              />
            )}

            {currentTab === 'contest' && (
              <ContestPage
                initData={initData}
                t={t}
                onExploreProducts={() => setCurrentTab('home')}
              />
            )}

            {currentTab === 'wishlist' && (
              <WishlistPage
                products={products}
                wishlistIds={wishlistIds}
                onToggleWishlist={handleToggleWishlist}
                onSelectProduct={setSelectedProduct}
                onExplore={() => setCurrentTab('home')}
                t={t}
              />
            )}

            {currentTab === 'bag' && (
              <BagPage
                cart={cart}
                settings={shopSettings}
                onUpdateQty={handleUpdateCartQty}
                onRemoveItem={handleRemoveCartItem}
                onClearCart={handleClearCart}
                onOrderSuccess={() => {
                  setCart(null);
                }}
                onContinueShopping={() => setCurrentTab('home')}
                t={t}
                initData={initData}
              />
            )}

            {currentTab === 'reviews' && (
              <ReviewsPage
                reviews={reviews}
                onReviewSubmitted={(rev) => setReviews([rev, ...reviews])}
                t={t}
                initData={initData}
              />
            )}

            {currentTab === 'settings' && (
              <SettingsPage
                settings={shopSettings}
                currentLang={lang}
                onLanguageChange={setLang}
                petalsEnabled={petalsEnabled}
                onTogglePetals={() => setPetalsEnabled(!petalsEnabled)}
                reducedMotion={reducedMotion}
                onToggleReducedMotion={() => setReducedMotion(!reducedMotion)}
                t={t}
              />
            )}

            {currentTab === 'admin' && (
              <AdminPage
                products={products}
                categories={categories}
                initData={initData}
                onRefreshProducts={refreshProducts}
                onRefreshCategories={refreshCategories}
                onRefreshReviews={refreshReviews}
                t={t}
              />
            )}
          </>
        )}
      </main>

      {/* Floating Bottom Navigation */}
      {!selectedProduct && (
        <BottomNav
          currentTab={currentTab}
          onTabChange={setCurrentTab}
          cartCount={cart?.total_items || 0}
          wishlistCount={wishlistIds.length}
          isAdmin={isAdmin}
          labels={{
            home: t.home,
            contest: t.contest,
            wishlist: t.wishlist,
            bag: t.bag,
            reviews: t.reviews,
            settings: t.settings,
            adminPanel: t.adminPanel,
          }}
        />
      )}
    </div>
  );
};
