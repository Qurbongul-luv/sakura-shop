import React from 'react';
import { Heart, Sparkles, Flame } from 'lucide-react';
import { Product } from '../types';
import { formatPrice, getMediaUrl } from '../utils/format';
import { haptic } from '../utils/telegram';

interface ProductCardProps {
  product: Product;
  isWishlisted: boolean;
  onToggleWishlist: (productId: number) => void;
  onSelect: (product: Product) => void;
  soldOutLabel: string;
}

export const ProductCard: React.FC<ProductCardProps> = ({
  product,
  isWishlisted,
  onToggleWishlist,
  onSelect,
  soldOutLabel,
}) => {
  const handleWishlistClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    haptic.impact('medium');
    onToggleWishlist(product.id);
  };

  const handleCardClick = () => {
    haptic.selection();
    onSelect(product);
  };

  const photoUrl = getMediaUrl(product.photos?.[0]);

  return (
    <div
      onClick={handleCardClick}
      className="group relative flex flex-col bg-white/90 dark:bg-sakura-darkcard/90 backdrop-blur-md rounded-3xl p-2.5 shadow-sakura-sm hover:shadow-sakura border border-sakura-pink/20 transition-all duration-300 active:scale-[0.98] cursor-pointer overflow-hidden"
    >
      {/* Product Image Container */}
      <div className="relative w-full aspect-square rounded-2xl overflow-hidden bg-sakura-blush/40 dark:bg-sakura-darkcardsoft">
        <img
          src={photoUrl}
          alt={product.title}
          loading="lazy"
          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
        />

        {/* Sold out overlay */}
        {!product.in_stock && (
          <div className="absolute inset-0 bg-sakura-darkbg/70 backdrop-blur-[2px] flex items-center justify-center">
            <span className="px-3 py-1 rounded-full bg-sakura-rose text-white text-xs font-extrabold tracking-wide shadow-md">
              ❌ {soldOutLabel}
            </span>
          </div>
        )}

        {/* Badges: New / Hit */}
        <div className="absolute top-2 left-2 flex flex-col gap-1 z-10">
          {product.is_hit && (
            <span className="flex items-center gap-0.5 px-2 py-0.5 rounded-full bg-amber-500/90 text-white text-[10px] font-bold backdrop-blur-sm shadow-sm">
              <Flame className="w-3 h-3 fill-white" />
              <span>HIT</span>
            </span>
          )}
          {product.is_new && (
            <span className="flex items-center gap-0.5 px-2 py-0.5 rounded-full bg-sakura-rose/90 text-white text-[10px] font-bold backdrop-blur-sm shadow-sm">
              <Sparkles className="w-3 h-3 fill-white" />
              <span>YANGI</span>
            </span>
          )}
        </div>

        {/* Heart Wishlist Button */}
        <button
          onClick={handleWishlistClick}
          className={`absolute top-2 right-2 p-2 rounded-full backdrop-blur-md shadow-sm transition-all duration-200 active:scale-125 z-10 ${
            isWishlisted
              ? 'bg-sakura-rose text-white scale-110 shadow-sakura animate-heart-pop'
              : 'bg-white/80 dark:bg-sakura-darkcard/80 text-sakura-plum/60 hover:text-sakura-rose'
          }`}
          title="Wishlist"
        >
          <Heart className={`w-4 h-4 ${isWishlisted ? 'fill-white stroke-white' : ''}`} />
        </button>
      </div>

      {/* Product Info */}
      <div className="mt-2.5 px-1 flex flex-col flex-1 justify-between">
        <div>
          <span className="text-[11px] font-semibold text-sakura-rose dark:text-sakura-pink block uppercase tracking-wider">
            #{product.category}
          </span>
          <h3 className="text-xs sm:text-sm font-bold text-sakura-plum dark:text-white line-clamp-2 mt-0.5 leading-snug">
            {product.title}
          </h3>
        </div>

        {/* Price & Old Price */}
        <div className="mt-2 flex items-baseline gap-1.5 flex-wrap">
          <span className="text-xs sm:text-sm font-black text-sakura-rose dark:text-sakura-pink">
            {formatPrice(product.price)}
          </span>
          {product.old_price && product.old_price > product.price && (
            <span className="text-[10px] sm:text-xs text-sakura-plum/40 line-through">
              {formatPrice(product.old_price)}
            </span>
          )}
        </div>
      </div>
    </div>
  );
};
