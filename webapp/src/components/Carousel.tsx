import React from 'react';
import { Product } from '../types';
import { ProductCard } from './ProductCard';

interface CarouselProps {
  title: string;
  products: Product[];
  wishlistIds: number[];
  onToggleWishlist: (productId: number) => void;
  onSelect: (product: Product) => void;
  soldOutLabel: string;
}

export const Carousel: React.FC<CarouselProps> = ({
  title,
  products,
  wishlistIds,
  onToggleWishlist,
  onSelect,
  soldOutLabel,
}) => {
  if (!products || products.length === 0) return null;

  return (
    <div className="my-3">
      <div className="px-4 mb-2 flex items-center justify-between">
        <h3 className="text-sm font-extrabold text-sakura-plum dark:text-sakura-pink flex items-center gap-1.5">
          <span>{title}</span>
        </h3>
      </div>

      <div className="flex space-x-3 overflow-x-auto px-4 pb-2 no-scrollbar snap-x">
        {products.map((product) => (
          <div key={product.id} className="w-[155px] sm:w-[175px] shrink-0 snap-start">
            <ProductCard
              product={product}
              isWishlisted={wishlistIds.includes(product.id)}
              onToggleWishlist={onToggleWishlist}
              onSelect={onSelect}
              soldOutLabel={soldOutLabel}
            />
          </div>
        ))}
      </div>
    </div>
  );
};
