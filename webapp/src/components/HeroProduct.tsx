import React from 'react';
import { Sparkles, ArrowRight } from 'lucide-react';
import { Product } from '../types';
import { formatPrice, getMediaUrl } from '../utils/format';
import { haptic } from '../utils/telegram';

interface HeroProductProps {
  product: Product;
  onSelect: (product: Product) => void;
  titleLabel: string;
}

export const HeroProduct: React.FC<HeroProductProps> = ({ product, onSelect, titleLabel }) => {
  const handleClick = () => {
    haptic.selection();
    onSelect(product);
  };

  const photoUrl = getMediaUrl(product.photos?.[0]);

  return (
    <div
      onClick={handleClick}
      className="relative mx-4 my-3 p-3.5 rounded-3xl bg-gradient-to-r from-sakura-blush via-white to-sakura-pink/30 dark:from-sakura-darkcard dark:via-sakura-darkcard dark:to-sakura-darkcardsoft border border-sakura-pink/40 shadow-sakura cursor-pointer active:scale-[0.99] transition-all overflow-hidden"
    >
      {/* Background cute petal glow */}
      <div className="absolute -top-10 -right-10 w-32 h-32 bg-sakura-pink/30 rounded-full blur-2xl pointer-events-none" />

      {/* Top Banner Tag */}
      <div className="flex items-center justify-between mb-2.5">
        <span className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-gradient-to-r from-sakura-rose to-sakura-darkrose text-white text-xs font-black tracking-wide shadow-sm">
          <Sparkles className="w-3.5 h-3.5 fill-white" />
          <span>{titleLabel}</span>
        </span>
        <span className="text-[11px] font-bold text-sakura-rose dark:text-sakura-pink uppercase">
          #{product.category}
        </span>
      </div>

      <div className="flex gap-3.5 items-center">
        {/* Photo */}
        <div className="w-24 h-24 sm:w-28 sm:h-28 rounded-2xl overflow-hidden shrink-0 bg-sakura-blush shadow-inner">
          <img src={photoUrl} alt={product.title} className="w-full h-full object-cover" />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <h4 className="text-sm sm:text-base font-extrabold text-sakura-plum dark:text-white line-clamp-2 leading-tight">
            {product.title}
          </h4>
          <p className="text-xs text-sakura-plum/70 dark:text-sakura-blush/70 line-clamp-1 mt-1">
            {product.description || "Aesthetic Xitoy brendi"}
          </p>

          <div className="mt-2.5 flex items-center justify-between">
            <div className="flex items-baseline gap-1.5">
              <span className="text-sm sm:text-base font-black text-sakura-rose dark:text-sakura-pink">
                {formatPrice(product.price)}
              </span>
              {product.old_price && (
                <span className="text-xs text-sakura-plum/40 line-through">
                  {formatPrice(product.old_price)}
                </span>
              )}
            </div>
            <span className="flex items-center gap-1 text-xs font-bold text-sakura-rose dark:text-sakura-pink bg-white/70 dark:bg-sakura-darkbg/70 px-2.5 py-1 rounded-xl shadow-xs">
              <span>Ko'rish</span>
              <ArrowRight className="w-3 h-3" />
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
