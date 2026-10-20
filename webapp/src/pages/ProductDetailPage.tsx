import React, { useState } from 'react';
import { ArrowLeft, Heart, ShoppingBag, Send, Package, Clock, Truck, CreditCard, MapPin, ZoomIn, Check } from 'lucide-react';
import { Product, ShopSettings } from '../types';
import { formatPrice, calculateCargo, getMediaUrl } from '../utils/format';
import { haptic, openTelegramLink } from '../utils/telegram';
import { triggerPetalBurst } from '../components/PetalBurst';
import { Translations } from '../i18n';

interface ProductDetailPageProps {
  product: Product;
  settings: ShopSettings;
  isWishlisted: boolean;
  onToggleWishlist: (productId: number) => void;
  onAddToCart: (product: Product, size?: string, color?: string) => void;
  onBack: () => void;
  t: Translations;
}

export const ProductDetailPage: React.FC<ProductDetailPageProps> = ({
  product,
  settings,
  isWishlisted,
  onToggleWishlist,
  onAddToCart,
  onBack,
  t,
}) => {
  const [activePhotoIndex, setActivePhotoIndex] = useState(0);
  const [selectedSize, setSelectedSize] = useState<string | undefined>(product.sizes?.[0]);
  const [selectedColor, setSelectedColor] = useState<string | undefined>(product.colors?.[0]);
  const [isZoomOpen, setIsZoomOpen] = useState(false);
  const [justAdded, setJustAdded] = useState(false);

  const photos = product.photos && product.photos.length > 0 ? product.photos : ['placeholder'];
  const cargoEstimate = calculateCargo(product.weight_grams, settings.cargo_rate || 12000);

  const handleAddToCart = (e: React.MouseEvent) => {
    if (!product.in_stock) return;
    haptic.notification('success');
    triggerPetalBurst(0.5, 0.7);
    onAddToCart(product, selectedSize, selectedColor);

    setJustAdded(true);
    setTimeout(() => setJustAdded(false), 2000);
  };

  const handleDirectAsk = () => {
    haptic.impact('light');
    const contact = (settings.contact_username || 'fkhrdnvvvva').replace('@', '');
    const text = encodeURIComponent(
      `Assalomu alaykum! 🌸 Sakura shop do'konidan ushbu mahsulot haqida so'ramoqchi edim:\n\n` +
      `✨ ${product.title}\n` +
      `💰 Narxi: ${formatPrice(product.price)}\n` +
      (selectedSize ? `📏 O'lcham: ${selectedSize}\n` : '') +
      (selectedColor ? `🎨 Rang: ${selectedColor}\n` : '') +
      `\nMavjudmi? 💌`
    );
    openTelegramLink(`https://t.me/${contact}?text=${text}`);
  };

  return (
    <div className="pb-32 bg-sakura-cream dark:bg-sakura-darkbg min-h-screen">
      {/* Top Floating Back Bar */}
      <div className="sticky top-0 z-30 flex items-center justify-between p-3.5 bg-white/80 dark:bg-sakura-darkcard/80 backdrop-blur-md border-b border-sakura-pink/20">
        <button
          onClick={onBack}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-2xl bg-sakura-blush/60 dark:bg-sakura-darkcardsoft text-sakura-plum dark:text-sakura-pink font-bold text-xs shadow-xs active:scale-95"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Orqaga</span>
        </button>

        <span className="text-xs font-bold text-sakura-rose uppercase">
          #{product.category}
        </span>

        <button
          onClick={() => {
            haptic.impact('medium');
            onToggleWishlist(product.id);
          }}
          className={`p-2 rounded-2xl shadow-xs transition-all active:scale-125 ${
            isWishlisted
              ? 'bg-sakura-rose text-white shadow-sakura animate-heart-pop'
              : 'bg-sakura-blush/60 dark:bg-sakura-darkcardsoft text-sakura-plum/70'
          }`}
        >
          <Heart className={`w-4 h-4 ${isWishlisted ? 'fill-white stroke-white' : ''}`} />
        </button>
      </div>

      {/* Main Image Gallery */}
      <div className="relative mx-4 mt-2 rounded-3xl overflow-hidden bg-sakura-blush/40 dark:bg-sakura-darkcard shadow-sakura-sm">
        <div className="w-full aspect-square relative">
          <img
            src={getMediaUrl(photos[activePhotoIndex])}
            alt={product.title}
            className="w-full h-full object-cover"
          />

          {!product.in_stock && (
            <div className="absolute inset-0 bg-sakura-darkbg/70 backdrop-blur-[2px] flex items-center justify-center">
              <span className="px-4 py-1.5 rounded-full bg-sakura-rose text-white text-sm font-extrabold shadow-md">
                ❌ {t.soldOut}
              </span>
            </div>
          )}

          {/* Zoom button */}
          <button
            onClick={() => setIsZoomOpen(true)}
            className="absolute bottom-3 right-3 p-2 rounded-full bg-white/80 dark:bg-sakura-darkcard/80 backdrop-blur-md text-sakura-plum dark:text-white shadow-sm active:scale-90"
          >
            <ZoomIn className="w-4 h-4" />
          </button>
        </div>

        {/* Thumbnail Dots / Strips */}
        {photos.length > 1 && (
          <div className="flex gap-2 p-3 overflow-x-auto justify-center bg-white/50 dark:bg-sakura-darkcard/50 backdrop-blur-sm">
            {photos.map((p, idx) => (
              <button
                key={idx}
                onClick={() => setActivePhotoIndex(idx)}
                className={`w-12 h-12 rounded-xl overflow-hidden border-2 transition-all shrink-0 ${
                  activePhotoIndex === idx
                    ? 'border-sakura-rose scale-105 shadow-sakura-sm'
                    : 'border-transparent opacity-60'
                }`}
              >
                <img src={getMediaUrl(p)} alt="" className="w-full h-full object-cover" />
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Zoom Modal */}
      {isZoomOpen && (
        <div
          onClick={() => setIsZoomOpen(false)}
          className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center p-4 backdrop-blur-md"
        >
          <img
            src={getMediaUrl(photos[activePhotoIndex])}
            alt={product.title}
            className="max-w-full max-h-[85vh] object-contain rounded-2xl"
          />
          <button
            onClick={() => setIsZoomOpen(false)}
            className="absolute top-4 right-4 text-white text-lg font-bold bg-white/20 p-2 rounded-full w-10 h-10 flex items-center justify-center"
          >
            ✕
          </button>
        </div>
      )}

      {/* Product Information */}
      <div className="mx-4 mt-4 p-4 rounded-3xl bg-white/90 dark:bg-sakura-darkcard/90 backdrop-blur-md shadow-sakura-sm border border-sakura-pink/20">
        <h2 className="text-lg sm:text-xl font-extrabold text-sakura-plum dark:text-white leading-tight">
          {product.title}
        </h2>

        {/* Price Row */}
        <div className="mt-2.5 flex items-baseline gap-2 flex-wrap">
          <span className="text-xl sm:text-2xl font-black text-sakura-rose dark:text-sakura-pink">
            {formatPrice(product.price)}
          </span>
          {product.old_price && product.old_price > product.price && (
            <span className="text-sm text-sakura-plum/40 line-through">
              {formatPrice(product.old_price)}
            </span>
          )}
          {cargoEstimate > 0 && (
            <span className="ml-auto text-xs font-bold text-sakura-plum/70 dark:text-sakura-blush/70 bg-sakura-blush/60 dark:bg-sakura-darkcardsoft px-2.5 py-1 rounded-full">
              📦 Kargo: ~{formatPrice(cargoEstimate)}
            </span>
          )}
        </div>

        {/* Size Picker */}
        {product.sizes && product.sizes.length > 0 && (
          <div className="mt-4">
            <span className="text-xs font-bold text-sakura-plum/80 dark:text-sakura-blush/80 block mb-1.5">
              {t.selectSize}
            </span>
            <div className="flex flex-wrap gap-2">
              {product.sizes.map((s) => (
                <button
                  key={s}
                  onClick={() => {
                    haptic.selection();
                    setSelectedSize(s);
                  }}
                  className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all ${
                    selectedSize === s
                      ? 'bg-sakura-rose text-white shadow-sakura scale-105'
                      : 'bg-sakura-cream dark:bg-sakura-darkcardsoft border border-sakura-pink/40 text-sakura-plum dark:text-sakura-blush'
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Color Picker */}
        {product.colors && product.colors.length > 0 && (
          <div className="mt-3.5">
            <span className="text-xs font-bold text-sakura-plum/80 dark:text-sakura-blush/80 block mb-1.5">
              {t.selectColor}
            </span>
            <div className="flex flex-wrap gap-2">
              {product.colors.map((c) => (
                <button
                  key={c}
                  onClick={() => {
                    haptic.selection();
                    setSelectedColor(c);
                  }}
                  className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all ${
                    selectedColor === c
                      ? 'bg-sakura-rose text-white shadow-sakura scale-105'
                      : 'bg-sakura-cream dark:bg-sakura-darkcardsoft border border-sakura-pink/40 text-sakura-plum dark:text-sakura-blush'
                  }`}
                >
                  {c}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Description */}
        {product.description && (
          <div className="mt-4 pt-3 border-t border-sakura-pink/20">
            <p className="text-xs sm:text-sm text-sakura-plum/80 dark:text-sakura-blush/80 whitespace-pre-line leading-relaxed">
              {product.description}
            </p>
          </div>
        )}

        {/* Compulsory Order line on every product */}
        <div className="mt-4 p-3 rounded-2xl bg-sakura-blush/70 dark:bg-sakura-darkcardsoft text-center border border-sakura-pink/40">
          <p className="text-xs sm:text-sm font-extrabold text-sakura-darkrose dark:text-sakura-pink">
            {t.orderNotice}
          </p>
        </div>
      </div>

      {/* Fixed Shop Terms Card (Matching Channel Terms) */}
      <div className="mx-4 mt-3 p-4 rounded-3xl bg-white/90 dark:bg-sakura-darkcard/90 backdrop-blur-md shadow-sakura-sm border border-sakura-pink/20">
        <h4 className="text-xs font-extrabold text-sakura-plum dark:text-white uppercase tracking-wider mb-2.5">
          {t.deliveryTerms}
        </h4>
        <div className="grid grid-cols-2 gap-2.5 text-xs">
          <div className="flex items-center gap-2 p-2 rounded-xl bg-sakura-cream/80 dark:bg-sakura-darkcardsoft">
            <Package className="w-4 h-4 text-sakura-rose shrink-0" />
            <div>
              <span className="text-[10px] text-sakura-plum/60 block">{t.cargoRateTitle}</span>
              <span className="font-bold">{formatPrice(settings.cargo_rate || 12000)} / 100g</span>
            </div>
          </div>
          <div className="flex items-center gap-2 p-2 rounded-xl bg-sakura-cream/80 dark:bg-sakura-darkcardsoft">
            <Clock className="w-4 h-4 text-sakura-rose shrink-0" />
            <div>
              <span className="text-[10px] text-sakura-plum/60 block">{t.deliveryTimeTitle}</span>
              <span className="font-bold">{settings.delivery_days || "10–15 kun"}</span>
            </div>
          </div>
          <div className="flex items-center gap-2 p-2 rounded-xl bg-sakura-cream/80 dark:bg-sakura-darkcardsoft">
            <Truck className="w-4 h-4 text-sakura-rose shrink-0" />
            <div>
              <span className="text-[10px] text-sakura-plum/60 block">{t.deliveryScopeTitle}</span>
              <span className="font-bold">{settings.delivery_scope || "O'zbekiston bo'ylab"}</span>
            </div>
          </div>
          <div className="flex items-center gap-2 p-2 rounded-xl bg-sakura-cream/80 dark:bg-sakura-darkcardsoft">
            <CreditCard className="w-4 h-4 text-sakura-rose shrink-0" />
            <div>
              <span className="text-[10px] text-sakura-plum/60 block">{t.prepaymentTitle}</span>
              <span className="font-bold">{settings.payment_terms || "100% oldindan to'lov"}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Floating Bottom Sticky Action Bar */}
      <div className="fixed bottom-0 left-0 right-0 z-40 p-3 bg-white/95 dark:bg-sakura-darkcard/95 backdrop-blur-md border-t border-sakura-pink/30 pb-safe shadow-sakura-lg">
        <div className="max-w-md mx-auto flex items-center gap-2.5">
          {/* Ask Now Button */}
          <button
            onClick={handleDirectAsk}
            className="flex-1 py-3 px-3 rounded-2xl bg-sakura-blush dark:bg-sakura-darkcardsoft text-sakura-darkrose dark:text-sakura-pink font-extrabold text-xs flex items-center justify-center gap-1.5 shadow-xs border border-sakura-pink/40 active:scale-95 transition-transform"
          >
            <Send className="w-4 h-4" />
            <span>{t.orderNow}</span>
          </button>

          {/* Add to Bag Button */}
          <button
            onClick={handleAddToCart}
            disabled={!product.in_stock}
            className={`flex-[1.5] py-3 px-4 rounded-2xl font-black text-sm flex items-center justify-center gap-2 shadow-sakura active:scale-95 transition-all text-white ${
              !product.in_stock
                ? 'bg-gray-400 cursor-not-allowed opacity-60'
                : justAdded
                ? 'bg-emerald-500 scale-98'
                : 'bg-gradient-to-r from-sakura-pink via-sakura-rose to-sakura-darkrose hover:opacity-95'
            }`}
          >
            {justAdded ? (
              <>
                <Check className="w-4 h-4" />
                <span>{t.addedToBag}</span>
              </>
            ) : (
              <>
                <ShoppingBag className="w-4 h-4" />
                <span>{product.in_stock ? t.addToBag : t.soldOut}</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
